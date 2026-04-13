"""Readwise adapter — syncs Highlights (v2 export) and Reader (v3 list).

Highlights: one atom per book, blockquoted highlights with notes.
Reader: ingest_url for full content, append highlights section if present.
"""

import os
import sys
import time
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.atomic_client import AtomicClient, AtomicAPIError
from lib.sync_state import SyncState
from lib.limit import get_limit
from lib import log
from lib.fallback_atom import is_content_parse_error, format_fallback_atom

READWISE_EXPORT_URL = "https://readwise.io/api/v2/export/"
READWISE_READER_URL = "https://readwise.io/api/v3/list/"
RATE_LIMIT_WAIT = 60  # seconds to wait on 429


def format_highlights_atom(book: dict) -> str:
    """Format a book's highlights as atom content."""
    title = book.get("title", "Untitled")
    author = book.get("author")
    highlights = book.get("highlights", [])

    lines = [f"# {title}"]
    if author:
        lines.append(f"\nby {author}")

    for hl in highlights:
        text = hl.get("text", "").strip()
        note = hl.get("note", "").strip()
        if text:
            lines.append(f"\n> {text}")
            if note:
                lines.append(f"\n{note}")

    return "\n".join(lines)


def format_highlights_section(highlights: list[dict]) -> str:
    """Format highlights as a section to append to an existing atom."""
    if not highlights:
        return ""

    lines = ["\n\n## My Highlights"]
    for hl in highlights:
        text = hl.get("text", "").strip()
        note = hl.get("note", "").strip()
        if text:
            lines.append(f"\n> {text}")
            if note:
                lines.append(f"\n{note}")

    return "\n".join(lines)


def _readwise_get(url: str, token: str, params: dict | None = None) -> dict:
    """Make a Readwise API GET request with rate limit handling."""
    headers = {"Authorization": f"Token {token}"}
    resp = requests.get(url, headers=headers, params=params or {})

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", RATE_LIMIT_WAIT))
        time.sleep(retry_after)
        resp = requests.get(url, headers=headers, params=params or {})

    resp.raise_for_status()
    return resp.json()


def sync_highlights(client: AtomicClient, state: SyncState, token: str, limit: int | None = None) -> int:
    """Sync Readwise Highlights (v2 export API). Returns processed count."""
    logger = log.setup("readwise.highlights")
    adapter_state = state.get("readwise")
    updated_after = adapter_state.get("highlights_updated_after")
    cursor = adapter_state.get("highlights_cursor")

    params = {}
    if updated_after:
        params["updatedAfter"] = updated_after
    if cursor:
        params["pageCursor"] = cursor

    processed = 0
    created = 0
    updated = 0

    while True:
        data = _readwise_get(READWISE_EXPORT_URL, token, params)
        books = data.get("results", [])

        for book in books:
            if limit is not None and processed >= limit:
                logger.info("Ingest limit reached (%d), stopping", limit)
                break

            processed += 1
            source_url = book.get("source_url", "")
            content = format_highlights_atom(book)

            existing = client.get_atom_by_source_url(source_url) if source_url else None
            if existing:
                client.update_atom(
                    existing["id"],
                    content=content,
                    source_url=source_url,
                    published_at=book.get("last_highlight_at"),
                )
                updated += 1
            else:
                client.create_atom(
                    content=content,
                    source_url=source_url,
                    published_at=book.get("last_highlight_at"),
                )
                created += 1

        if limit is not None and processed >= limit:
            break

        next_cursor = data.get("nextPageCursor")
        if limit is None:
            adapter_state["highlights_cursor"] = next_cursor
            state.save("readwise", adapter_state)

        if not next_cursor:
            break
        params["pageCursor"] = next_cursor

    # Only finalize sync state if not in limited mode
    if limit is None:
        from datetime import datetime, timezone
        adapter_state["highlights_updated_after"] = datetime.now(timezone.utc).isoformat()
        adapter_state["highlights_cursor"] = None
        state.save("readwise", adapter_state)

    logger.info("Highlights sync complete: %d created, %d updated", created, updated)
    return processed


def sync_reader(client: AtomicClient, state: SyncState, token: str, limit: int | None = None) -> int:
    """Sync Readwise Reader (v3 list API). Returns processed count."""
    logger = log.setup("readwise.reader")
    adapter_state = state.get("readwise")
    updated_after = adapter_state.get("reader_updated_after")
    cursor = adapter_state.get("reader_cursor")

    params = {}
    if updated_after:
        params["updatedAfter"] = updated_after
    if cursor:
        params["pageCursor"] = cursor

    processed = 0
    ingested = 0
    enriched = 0

    while True:
        data = _readwise_get(READWISE_READER_URL, token, params)
        results = data.get("results", [])

        for doc in results:
            if limit is not None and processed >= limit:
                logger.info("Ingest limit reached (%d), stopping", limit)
                break

            source_url = doc.get("source_url") or doc.get("url", "")
            if not source_url:
                continue

            processed += 1
            published_at = doc.get("published_date")

            # Ingest the URL — Atomic fetches full content
            try:
                client.ingest_url(url=source_url, published_at=published_at)
                ingested += 1
            except AtomicAPIError as e:
                if e.status_code == 409 or "already exists" in e.message.lower():
                    logger.debug("URL already ingested: %s", source_url)
                elif is_content_parse_error(e):
                    content = format_fallback_atom(
                        title=doc.get("title", "Untitled"),
                        source=doc.get("site_name", ""),
                        author=doc.get("author", ""),
                        summary=doc.get("summary", "").strip(),
                    )
                    client.create_atom(
                        content=content,
                        source_url=source_url,
                        published_at=published_at,
                    )
                    ingested += 1
                    logger.info("Created fallback atom: %s", source_url)
                else:
                    logger.warning("Failed to ingest %s: %s", source_url, e)
                    continue

            # Enrich with highlights if present
            highlights = doc.get("highlights", [])
            notes = doc.get("notes", "").strip()
            hl_items = []
            if highlights:
                hl_items = [{"text": h.get("text", ""), "note": h.get("note", "")} for h in highlights]
            if notes:
                hl_items.append({"text": notes, "note": ""})

            if hl_items:
                existing = client.get_atom_by_source_url(source_url)
                if existing:
                    section = format_highlights_section(hl_items)
                    new_content = existing["content"] + section
                    client.update_atom(existing["id"], content=new_content)
                    enriched += 1

        if limit is not None and processed >= limit:
            break

        next_cursor = data.get("nextPageCursor")
        if limit is None:
            adapter_state["reader_cursor"] = next_cursor
            state.save("readwise", adapter_state)

        if not next_cursor:
            break
        params["pageCursor"] = next_cursor

    # Only finalize sync state if not in limited mode
    if limit is None:
        from datetime import datetime, timezone
        adapter_state["reader_updated_after"] = datetime.now(timezone.utc).isoformat()
        adapter_state["reader_cursor"] = None
        state.save("readwise", adapter_state)

    logger.info("Reader sync complete: %d ingested, %d enriched with highlights", ingested, enriched)
    return processed


def main():
    logger = log.setup("readwise")

    token = os.environ.get("READWISE_API_TOKEN", "")
    if not token:
        logger.info("READWISE_API_TOKEN not set, skipping")
        return

    api_url = os.environ["ATOMIC_API_URL"]
    api_token = os.environ["ATOMIC_API_TOKEN"]
    client = AtomicClient(api_url, api_token)
    state = SyncState()

    limit = get_limit("readwise")
    if limit is not None:
        logger.info("Ingest limit: %d items", limit)

    logger.info("Starting Readwise sync")
    h_count = sync_highlights(client, state, token, limit=limit)

    remaining = None
    if limit is not None:
        remaining = limit - h_count
        if remaining <= 0:
            logger.info("Ingest limit reached after highlights, skipping Reader sync")
            logger.info("Readwise sync complete")
            return

    sync_reader(client, state, token, limit=remaining)
    logger.info("Readwise sync complete")


if __name__ == "__main__":
    main()
