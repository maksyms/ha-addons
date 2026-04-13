"""Fallback atom creation for URLs that fail server-side ingestion."""

from lib.atomic_client import AtomicAPIError


def is_content_parse_error(error: AtomicAPIError) -> bool:
    """Return True if the error is a content parsing failure (fallback-worthy).

    Atomic Server returns 500 for both fetch failures (HTTP 4xx/5xx from target)
    and content parse failures (readability, non-HTML). We only fall back on
    parse failures — fetch failures mean the page is unreachable.
    """
    if error.status_code != 500:
        return False
    msg = error.message
    return "Ingestion error:" in msg and "HTTP " not in msg


def format_fallback_atom(
    title: str,
    source: str = "",
    author: str = "",
    type: str = "",
    tags: list[str] | None = None,
    summary: str = "",
    notes: str = "",
) -> str:
    """Format a fallback atom from source metadata.

    Omits fields and sections that are empty.
    """
    lines = [f"# {title}"]

    # Metadata fields
    meta = []
    if source:
        meta.append(f"**Source:** {source}")
    if author:
        meta.append(f"**Author:** {author}")
    if type:
        meta.append(f"**Type:** {type}")
    if tags:
        meta.append(f"**Tags:** {', '.join(tags)}")

    if meta:
        lines.append("")
        lines.extend(meta)

    # Sections
    if summary:
        lines.append("")
        lines.append("## Summary")
        lines.append(summary)

    if notes:
        lines.append("")
        lines.append("## Notes")
        lines.append(notes)

    return "\n".join(lines)
