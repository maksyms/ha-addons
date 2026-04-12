# Atomic Ingest HA Add-on — Design Spec

## Overview

Home Assistant add-on that aggregates data from multiple sources into an Atomic knowledge base via its REST API. Phase 1 covers the add-on infrastructure and three source adapters: Readwise (highlights + Reader), Raindrop.io, and Evernote.

## Scope

- Add-on skeleton: Dockerfile, config.yaml, run.sh, cron-based scheduler
- Shared library: Atomic API client, sync state, folder consumer, logging
- Adapters: Readwise, Raindrop, Evernote
- CI/CD workflow

Out of scope: Phase 2+ adapters (Telegram, YouTube, GitHub, etc.), HA notifications, non-aarch64 architectures.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  atomic-ingest container (python:3.12-slim)         │
│                                                     │
│  run.sh (PID 1)                                     │
│    ├── reads /data/options.json (HA UI options)     │
│    ├── loads .env from /config/                     │
│    ├── dumps env vars to /app/env.sh                │
│    ├── generates crontab (schedules from .env)      │
│    └── execs crond -f                               │
│                                                     │
│  /app/                                              │
│    ├── adapters/                                    │
│    │   ├── readwise.py      (cron: hourly)          │
│    │   ├── raindrop.py      (cron: hourly)          │
│    │   └── evernote.py      (cron: daily)           │
│    └── lib/                                         │
│        ├── atomic_client.py (Atomic REST API)       │
│        ├── sync_state.py    (JSON state in /data/)  │
│        ├── folder_consumer.py (consume/processed)   │
│        └── log.py           (structured logging)    │
│                                                     │
│  /data/ (HA-managed persistent volume)              │
│    ├── options.json                                 │
│    └── sync_state.json                              │
│                                                     │
│  /config/ (HA addon_config, read-only)              │
│    └── .env (source credentials, schedules)         │
│                                                     │
│  /share/atomic-ingest/                              │
│    └── evernote/                                    │
│        ├── consume/   (drop .enex files here)       │
│        └── processed/ (moved after ingestion)       │
└──────────────┬──────────────────────────────────────┘
               │ internal HA Docker network
               ▼
┌──────────────────────┐
│  Atomic container    │
│  (API on :8081)      │
└──────────────────────┘
```

### Process model

`crond` is PID 1. It spawns adapter scripts on schedule. No long-running daemon, no watchdog. The Evernote folder scan is just another cron job. HA Supervisor restarts the container if crond dies.

### Cron doesn't inherit environment

`run.sh` dumps all relevant env vars to `/app/env.sh`. Each crontab line sources it before running the adapter: `. /app/env.sh && python /app/adapters/readwise.py`.

## config.yaml

```yaml
name: Atomic Ingest
description: >-
  Automated data ingestion into Atomic knowledge base.
  Readwise, Raindrop.io, Evernote, and more.
version: "1.0.0"
slug: atomic-ingest
url: "https://github.com/maksyms/ha-addons"
arch:
  - aarch64
init: false
startup: application
boot: auto

options:
  atomic_api_url: ""
  atomic_api_token: ""
  log_level: "info"
schema:
  atomic_api_url: url
  atomic_api_token: password
  log_level: "list(debug|info|warning|error)"

map:
  - data:rw
  - share:rw
  - addon_config:ro
```

Three HA UI options only. All source-specific credentials and schedule overrides live in `/config/.env`.

No healthcheck — there's no long-running process to monitor. crond spawns scripts and they exit.

## Dockerfile

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lib/ lib/
COPY adapters/ adapters/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
```

## run.sh

Responsibilities:

1. Read `atomic_api_url`, `atomic_api_token`, `log_level` from `/data/options.json`
2. Source `/config/.env` if it exists (source credentials, schedule overrides)
3. Export all env vars and dump to `/app/env.sh` so cron jobs can source them
4. Create `/share/atomic-ingest/evernote/consume/` and `processed/` dirs if missing
5. Generate crontab from schedule env vars with defaults:
   - Readwise: `READWISE_SCHEDULE` default `"0 * * * *"` (hourly)
   - Raindrop: `RAINDROP_SCHEDULE` default `"30 * * * *"` (hourly, offset)
   - Evernote: `EVERNOTE_SCHEDULE` default `"0 3 * * *"` (daily 3am)
6. Install crontab, exec `crond -f`

Each crontab entry: `. /app/env.sh && python /app/adapters/<name>.py >> /proc/1/fd/1 2>&1`

Stdout/stderr redirected to PID 1's stdout so HA captures all logs.

## Shared Library

### `lib/atomic_client.py`

Comprehensive Atomic REST API client. Ingestion-related methods have real implementations; all other methods are stubs with `raise NotImplementedError`.

```python
class AtomicClient:
    def __init__(self, base_url: str, api_token: str):
        ...

    # --- Ingestion (implemented) ---

    def create_atom(self, content, source_url=None, published_at=None, tag_ids=None) -> dict:
        """POST /api/atoms with skip_if_source_exists=true."""

    def create_atoms_bulk(self, atoms: list[dict]) -> dict:
        """POST /api/atoms/bulk. Auto-chunks at 1000."""

    def get_atom(self, atom_id: str) -> dict:
        """GET /api/atoms/{id}."""

    def update_atom(self, atom_id: str, content: str, source_url=None,
                    published_at=None, tag_ids=None) -> dict:
        """PUT /api/atoms/{id}."""

    def get_atom_by_source_url(self, url: str) -> dict | None:
        """GET /api/atoms/by-source-url?url=. Returns None if 404."""

    def list_atoms(self, limit=50, offset=0, tag_id=None, source=None,
                   source_value=None, sort_by=None, sort_order=None) -> dict:
        """GET /api/atoms with query params."""

    def ingest_url(self, url: str, tag_ids=None, title_hint=None,
                   published_at=None) -> dict:
        """POST /api/ingest/url. Server-side fetch + extract."""

    def ingest_urls(self, urls: list[dict]) -> dict:
        """POST /api/ingest/urls. Batch URL ingestion."""

    def health(self) -> dict:
        """GET /health (no auth)."""

    # --- Search (stub) ---

    def search(self, query, mode="hybrid", limit=20, threshold=None) -> list:
        raise NotImplementedError

    # --- Tags (stub) ---

    def list_tags(self, min_count=None) -> list:
        raise NotImplementedError

    def create_tag(self, name, parent_id=None) -> dict:
        raise NotImplementedError

    # --- Feeds (stub) ---

    def list_feeds(self) -> list:
        raise NotImplementedError

    def create_feed(self, **kwargs) -> dict:
        raise NotImplementedError

    # --- Embeddings (stub) ---

    def get_embedding_status(self) -> dict:
        raise NotImplementedError

    def process_pending(self):
        raise NotImplementedError

    def retry_embedding(self, atom_id: str):
        raise NotImplementedError

    # --- Databases (stub) ---

    def list_databases(self) -> list:
        raise NotImplementedError

    def get_database_stats(self, db_id: str) -> dict:
        raise NotImplementedError
```

**Error handling:**
- Retries on 5xx and network errors: 3 attempts with exponential backoff
- Raises on 4xx (bad request, auth failure) — adapter decides how to handle
- All creates set `skip_if_source_exists: true` by default

### `lib/sync_state.py`

Flexible cursor-based state per adapter, stored in `/data/sync_state.json`.

```python
class SyncState:
    def __init__(self, path: str = "/data/sync_state.json"):
        ...

    def get(self, adapter_name: str) -> dict:
        """Returns adapter's state dict, or {} if no prior state."""

    def save(self, adapter_name: str, state: dict):
        """Merges and persists state. Call mid-sync after each page for crash safety."""
```

File-level locking prevents concurrent cron jobs from corrupting the JSON. `save()` is designed to be called after each page/batch of results, so if an adapter crashes mid-sync, the next run resumes from where it left off.

Example state:
```json
{
  "readwise": {
    "highlights_updated_after": "2026-04-11T03:00:00Z",
    "highlights_cursor": null,
    "reader_updated_after": "2026-04-11T03:00:00Z",
    "reader_cursor": null
  },
  "raindrop": {
    "last_sync_date": "2026-04-11"
  }
}
```

### `lib/folder_consumer.py`

Consume/processed folder pattern for file-based imports.

```python
def consume(consume_dir: Path, processed_dir: Path,
            glob_pattern: str) -> Iterator[tuple[Path, Callable]]:
    """Yields (file_path, mark_done) for each file matching pattern.
    Calling mark_done() moves the file to processed_dir."""
```

### `lib/log.py`

```python
def setup(adapter_name: str) -> logging.Logger:
    """Configures logging with adapter name prefix, level from LOG_LEVEL env var.
    Logs to stdout (HA captures container stdout)."""
```

## Adapters

### `adapters/readwise.py` — single script, two phases

**Auth:** `Authorization: Token {READWISE_API_TOKEN}` header.

**Phase 1 — Readwise Highlights (v2):**
- Endpoint: `GET https://readwise.io/api/v2/export/` with `updatedAfter` from sync state
- Cursor-based pagination: `pageCursor` / `nextPageCursor`
- Groups highlights by book — one atom per book
- Atom content: `# {book_title}\n\nby {author}\n\n> {highlight_text}\n\n> {highlight_text}\n...`
- `source_url`: Readwise book URL
- `published_at`: `last_highlight_at`
- Uses `create_atom` (not `ingest_url` — content is highlights, not a web page)
- **Update handling:** on subsequent syncs, `updatedAfter` returns books with new highlights. For each book, check `get_atom_by_source_url` first — if atom exists, rebuild content with all highlights and `update_atom`; if not, `create_atom`. This ensures new highlights are appended to existing book atoms.
- Saves `highlights_cursor` to sync state after each page (crash-safe resume)

**Phase 2 — Readwise Reader (v3):**
- Endpoint: `GET https://readwise.io/api/v3/list/` with `updatedAfter` from sync state
- Same cursor-based pagination
- For each document:
  1. `ingest_url(source_url)` — Atomic fetches full article content
  2. If document has highlights/notes: `get_atom_by_source_url(source_url)` then `update_atom(id, content + highlights_section)` to append `## My Highlights` with annotations
- `published_at`: `published_date`
- Saves `reader_cursor` to sync state after each page

**Rate limits:** 20 req/min. Respect `Retry-After` header on 429.

**Sync state:**
```json
{
  "highlights_updated_after": "2026-04-11T03:00:00Z",
  "highlights_cursor": null,
  "reader_updated_after": "2026-04-11T03:00:00Z",
  "reader_cursor": null
}
```

### `adapters/raindrop.py`

**Auth:** `Authorization: Bearer {RAINDROP_TOKEN}` header. Test token from app.raindrop.io/settings/integrations (never expires).

**Endpoint:** `GET https://api.raindrop.io/rest/v1/raindrops/0` with `search=lastUpdate:>YYYY-MM-DD`, paginated (50/page, 0-indexed).

**Three cases per bookmark:**

1. **URL bookmark without annotations:** `ingest_url(link)` — Atomic fetches and extracts full content.

2. **URL bookmark with notes/highlights:** `ingest_url(link)`, then `get_atom_by_source_url(link)` + `update_atom(id, content + notes_section)` to append `## My Notes` with Raindrop notes and highlights.

3. **Uploaded file/video** (no fetchable external URL): `create_atom` directly with `# {title}\n\n{note}`. `source_url` = Raindrop's own link to the item (for dedup).

**Rate limits:** 120 req/min.

**Sync state:**
```json
{
  "last_sync_date": "2026-04-11"
}
```

Day-level granularity matches API capability. Dedup for overlapping days handled by `skip_if_source_exists` and `ingest_url`'s built-in rejection.

### `adapters/evernote.py`

**Trigger:** Daily cron scans `/share/atomic-ingest/evernote/consume/` for `.enex` files.

**Processing:**
1. Uses `folder_consumer.consume()` to iterate `.enex` files
2. Parses ENEX XML with `lxml` — ENEX is XML with HTML note bodies and base64 resources
3. Converts note HTML to Markdown via `markdownify`
4. Each note becomes one atom:
   - Content: `# {note_title}\n\n{note_content_as_markdown}`
   - `source_url`: `evernote:///{note_guid}` (for dedup across re-imports)
   - `published_at`: note's `created` date
5. Bulk creates in batches of 1000 via `create_atoms_bulk`
6. After all notes from a file are ingested, `mark_done()` moves file to `processed/`

**No sync state needed** — the consume/processed pattern is the state.

**Dependencies:** `lxml`, `markdownify`

## .env Example

File at `/addon_configs/atomic-ingest/.env` (mounted read-only at `/config/.env`):

```bash
# Source credentials
READWISE_API_TOKEN=
RAINDROP_TOKEN=

# Schedule overrides (cron expressions)
# READWISE_SCHEDULE="0 * * * *"    # default: hourly on the hour
# RAINDROP_SCHEDULE="30 * * * *"   # default: hourly at :30
# EVERNOTE_SCHEDULE="0 3 * * *"    # default: daily at 3am
```

Adapters with missing credentials are skipped (cron entry still exists, script checks for token and exits cleanly if absent).

## requirements.txt

```
requests
lxml
markdownify
```

No APScheduler (using system cron), no heavy frameworks.

## CI/CD

**File:** `.github/workflows/deploy-atomic-ingest.yml`

Same pattern as other add-ons:
- Trigger: push to `master` with path filter `atomic-ingest/**`
- Steps: checkout, extract version from config.yaml, bump patch, generate CHANGELOG.md from git log, commit with `[skip ci]`
- No `workflow_dispatch` or force deploy

## File Inventory

### New files in `atomic-ingest/`

| File | Purpose |
|------|---------|
| `config.yaml` | HA add-on manifest |
| `Dockerfile` | python:3.12-slim + cron + jq |
| `run.sh` | Entrypoint — env setup, crontab generation, exec crond |
| `requirements.txt` | Python dependencies |
| `CHANGELOG.md` | Empty initially, auto-populated by CI |
| `icon.png` | Add-on icon |
| `logo.png` | Add-on logo |
| `lib/__init__.py` | Package init |
| `lib/atomic_client.py` | Atomic REST API client |
| `lib/sync_state.py` | Per-adapter sync state in /data/ |
| `lib/folder_consumer.py` | Consume/processed folder pattern |
| `lib/log.py` | Logging setup |
| `adapters/readwise.py` | Readwise highlights + Reader adapter |
| `adapters/raindrop.py` | Raindrop.io bookmarks adapter |
| `adapters/evernote.py` | Evernote ENEX import adapter |

### New files elsewhere

| File | Purpose |
|------|---------|
| `.github/workflows/deploy-atomic-ingest.yml` | CI/CD workflow |

### Updated files

| File | Change |
|------|--------|
| `CLAUDE.md` | Add atomic-ingest section |
