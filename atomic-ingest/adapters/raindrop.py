"""Raindrop.io adapter — syncs bookmarks via ingest_url.

URL bookmarks: ingest_url for full content, enrich with notes/highlights.
Uploaded files/videos: create_atom with title + note.
"""

import logging
import os
import sys
import time
import requests
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.atomic_client import AtomicClient, AtomicAPIError
from lib.sync_state import SyncState
from lib.limit import get_limit
from lib import log
from lib.fallback_atom import is_content_parse_error, format_fallback_atom

RAINDROP_API_URL = "https://api.raindrop.io/rest/v1/raindrops/0"
PAGE_SIZE = 50
RATE_LIMIT_WAIT = 60


def classify_bookmark(bm: dict) -> str:
    """Classify bookmark: 'url_clean', 'url_annotated', or 'uploaded'."""
    link = bm.get("link", "").strip()
    note = bm.get("note", "").strip()
    highlights = bm.get("highlights", [])

    if not link:
        return "uploaded"
    if note or highlights:
        return "url_annotated"
    return "url_clean"


def format_notes_section(note: str, highlights: list[dict]) -> str:
    """Format Raindrop notes and highlights as a section."""
    note = note.strip()
    if not note and not highlights:
        return ""

    lines = ["\n\n## My Notes"]
    if note:
        lines.append(f"\n{note}")
    for hl in highlights:
        text = hl.get("text", "").strip()
        if text:
            lines.append(f"\n> {text}")

    return "\n".join(lines)


def _raindrop_get(url: str, token: str, params: dict) -> dict:
    """Make a Raindrop API GET request with rate limit handling."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, params=params)

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", RATE_LIMIT_WAIT))
        logging.getLogger("raindrop").warning(
            "Rate limited, waiting %ds", retry_after,
        )
        time.sleep(retry_after)
        resp = requests.get(url, headers=headers, params=params)

    resp.raise_for_status()
    return resp.json()


def sync_raindrop(client: AtomicClient, state: SyncState, token: str):
    """Sync Raindrop.io bookmarks."""
    logger = log.setup("raindrop")
    limit = get_limit("raindrop")
    if limit is not None:
        logger.info("Ingest limit: %d items", limit)

    adapter_state = state.get("raindrop")
    last_sync_date = adapter_state.get("last_sync_date")

    params: dict = {"perpage": PAGE_SIZE, "sort": "-created"}
    if last_sync_date:
        params["search"] = f"lastUpdate:>{last_sync_date}"

    page = 0
    processed = 0
    ingested = 0
    enriched = 0
    created = 0

    while True:
        params["page"] = page
        data = _raindrop_get(RAINDROP_API_URL, token, params)
        items = data.get("items", [])

        if not items:
            break

        logger.info("Page %d: %d items", page, len(items))

        for bm in items:
            if limit is not None and processed >= limit:
                logger.info("Ingest limit reached (%d), stopping", limit)
                break

            processed += 1
            kind = classify_bookmark(bm)
            link = bm.get("link", "").strip()
            title = bm.get("title", "Untitled")
            note = bm.get("note", "")
            highlights = bm.get("highlights", [])
            published_at = bm.get("created")

            if kind == "uploaded":
                content = f"# {title}"
                if note.strip():
                    content += f"\n\n{note.strip()}"
                source_url = f"https://app.raindrop.io/my/0/{bm.get('_id', '')}"
                client.create_atom(
                    content=content,
                    source_url=source_url,
                    published_at=published_at,
                )
                created += 1
                logger.info("Created atom: %s (uploaded)", title)

            elif kind == "url_clean":
                try:
                    client.ingest_url(url=link, published_at=published_at)
                    ingested += 1
                    logger.info("Ingested URL: %s", link)
                except AtomicAPIError as e:
                    if e.status_code == 409 or "already exists" in e.message.lower():
                        logger.debug("Already ingested: %s", link)
                    elif is_content_parse_error(e):
                        content = format_fallback_atom(
                            title=title,
                            source=bm.get("domain", ""),
                            type=bm.get("type", ""),
                            tags=[t for t in bm.get("tags", []) if t],
                            summary=bm.get("excerpt", "").strip(),
                        )
                        client.create_atom(
                            content=content,
                            source_url=link,
                            published_at=published_at,
                        )
                        created += 1
                        logger.info("Created fallback atom: %s", link)
                    else:
                        logger.warning("Failed to ingest %s: %s", link, e)

            elif kind == "url_annotated":
                try:
                    client.ingest_url(url=link, published_at=published_at)
                    ingested += 1
                    logger.info("Ingested URL: %s", link)
                except AtomicAPIError as e:
                    if e.status_code == 409 or "already exists" in e.message.lower():
                        logger.debug("Already ingested: %s", link)
                    elif is_content_parse_error(e):
                        content = format_fallback_atom(
                            title=title,
                            source=bm.get("domain", ""),
                            type=bm.get("type", ""),
                            tags=[t for t in bm.get("tags", []) if t],
                            summary=bm.get("excerpt", "").strip(),
                        )
                        client.create_atom(
                            content=content,
                            source_url=link,
                            published_at=published_at,
                        )
                        created += 1
                        logger.info("Created fallback atom: %s", link)
                    else:
                        logger.warning("Failed to ingest %s: %s", link, e)
                        continue

                # Enrich with notes/highlights
                section = format_notes_section(note, highlights)
                if section:
                    existing = client.get_atom_by_source_url(link)
                    if existing:
                        new_content = existing["content"] + section
                        client.update_atom(existing["id"], content=new_content)
                        enriched += 1
                        logger.info("Enriched atom: %s", link)

        if limit is not None and processed >= limit:
            break
        if len(items) < PAGE_SIZE:
            break
        page += 1

    # Only update sync state if not in limited mode
    if limit is None:
        adapter_state["last_sync_date"] = date.today().isoformat()
        state.save("raindrop", adapter_state)
    else:
        logger.info("Sync state not updated (ingest limit active)")

    logger.info(
        "Raindrop sync complete: %d processed, %d ingested, %d enriched, %d created",
        processed, ingested, enriched, created,
    )


def main():
    logger = log.setup("raindrop")

    token = os.environ.get("RAINDROP_TOKEN", "")
    if not token:
        logger.info("RAINDROP_TOKEN not set, skipping")
        return

    api_url = os.environ["ATOMIC_API_URL"]
    api_token = os.environ["ATOMIC_API_TOKEN"]
    client = AtomicClient(api_url, api_token)
    state = SyncState()

    logger.info("Starting Raindrop sync")
    sync_raindrop(client, state, token)
    logger.info("Raindrop sync complete")


if __name__ == "__main__":
    main()
