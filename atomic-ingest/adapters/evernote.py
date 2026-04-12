"""Evernote adapter — parses .enex files from consume folder, creates atoms.

Scans /share/atomic-ingest/evernote/consume/ for .enex files.
Parses ENEX XML, converts HTML to Markdown, bulk creates atoms.
Moves processed files to /share/atomic-ingest/evernote/processed/.
"""

import os
import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime

from lxml import etree
from markdownify import markdownify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.atomic_client import AtomicClient
from lib.folder_consumer import consume
from lib.limit import get_limit
from lib import log

CONSUME_DIR = Path("/share/atomic-ingest/evernote/consume")
PROCESSED_DIR = Path("/share/atomic-ingest/evernote/processed")

def parse_enex(enex_path: Path) -> list[dict]:
    """Parse an ENEX file and return note dicts.

    Each dict has: title, content_html, created, source_url (optional).
    """
    tree = etree.parse(str(enex_path))
    notes = []

    for note_el in tree.findall(".//note"):
        title = note_el.findtext("title", "Untitled")

        # Content is CDATA-wrapped ENML (HTML-like)
        content_raw = note_el.findtext("content", "")
        # Strip the ENML doctype and en-note wrapper
        content_html = _extract_enml_body(content_raw)

        # Parse Evernote date format: 20260411T120000Z -> ISO 8601
        created_raw = note_el.findtext("created", "")
        created = _parse_evernote_date(created_raw)

        # Source URL from note attributes
        attrs_el = note_el.find("note-attributes")
        source_url = None
        if attrs_el is not None:
            source_url = attrs_el.findtext("source-url")

        notes.append({
            "title": title,
            "content_html": content_html,
            "created": created,
            "source_url": source_url,
        })

    return notes


def _extract_enml_body(content: str) -> str:
    """Extract body content from ENML, stripping doctype and en-note tags."""
    # Remove XML declaration and doctype
    content = re.sub(r'<\?xml[^>]*\?>', '', content)
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
    # Remove en-note wrapper
    content = re.sub(r'</?en-note[^>]*>', '', content)
    return content.strip()


def _parse_evernote_date(date_str: str) -> str | None:
    """Convert Evernote date (20260411T120000Z) to ISO 8601."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str.strip(), "%Y%m%dT%H%M%SZ")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def format_note_atom(note: dict) -> str:
    """Format an Evernote note as atom content (Markdown)."""
    title = note["title"]
    html = note.get("content_html", "")

    if not html.strip():
        return f"# {title}"

    md = markdownify(html, heading_style="ATX", strip=["img"]).strip()
    return f"# {title}\n\n{md}"


def _note_source_url(note: dict, enex_filename: str) -> str:
    """Generate a stable source URL for dedup.

    Uses the Evernote source-url if available, otherwise generates
    a deterministic URI from the note title and created date.
    """
    if note.get("source_url"):
        return note["source_url"]

    # Deterministic fallback: hash of title + created + filename
    key = f"{note['title']}|{note.get('created', '')}|{enex_filename}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:12]
    return f"evernote:///import/{digest}"


def main():
    logger = log.setup("evernote")
    limit = get_limit("evernote")
    if limit is not None:
        logger.info("Ingest limit: %d notes", limit)

    api_url = os.environ["ATOMIC_API_URL"]
    api_token = os.environ["ATOMIC_API_TOKEN"]
    client = AtomicClient(api_url, api_token)

    total_processed = 0
    files_found = False
    for enex_path, mark_done in consume(CONSUME_DIR, PROCESSED_DIR, "*.enex"):
        if limit is not None and total_processed >= limit:
            logger.info("Ingest limit reached (%d), stopping", limit)
            break

        files_found = True
        logger.info("Processing %s", enex_path.name)

        notes = parse_enex(enex_path)
        logger.info("Parsed %d notes from %s", len(notes), enex_path.name)

        # Build atom dicts for bulk create
        all_atoms = []
        for note in notes:
            content = format_note_atom(note)
            source_url = _note_source_url(note, enex_path.name)
            atom = {"content": content, "source_url": source_url}
            if note.get("created"):
                atom["published_at"] = note["created"]
            all_atoms.append(atom)

        # Apply limit
        if limit is not None:
            remaining = limit - total_processed
            atoms = all_atoms[:remaining]
        else:
            atoms = all_atoms

        # Bulk create in chunks
        if atoms:
            result = client.create_atoms_bulk(atoms)
            total_processed += len(atoms)
            logger.info(
                "%s: %d created, %d skipped",
                enex_path.name, result["count"], result["skipped"],
            )

        if len(atoms) == len(all_atoms):
            mark_done()
            logger.info("Moved %s to processed", enex_path.name)
        else:
            logger.info(
                "%s partially processed (%d/%d notes), not moved",
                enex_path.name, len(atoms), len(all_atoms),
            )

    if not files_found:
        logger.debug("No .enex files found in consume folder")


if __name__ == "__main__":
    main()
