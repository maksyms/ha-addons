"""Framework-level ingest limit for debugging."""

import os


def get_limit(adapter_name: str) -> int | None:
    """Return the ingest limit, or None for unlimited.

    Checks <ADAPTER>_LIMIT first, then INGEST_LIMIT global fallback.
    """
    specific = os.environ.get(f"{adapter_name.upper()}_LIMIT", "").strip()
    if specific:
        return int(specific)
    global_val = os.environ.get("INGEST_LIMIT", "").strip()
    if global_val:
        return int(global_val)
    return None
