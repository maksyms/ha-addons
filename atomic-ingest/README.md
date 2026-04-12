# Atomic Ingest - HA Add-on

A Home Assistant add-on that automatically ingests data from multiple sources into [Atomic](https://github.com/kenforthewin/atomic) knowledge base via its REST API.

## Installation

1. In Home Assistant: **Settings > Add-ons > Add-on Store > three-dot menu > Repositories**
2. Add this repository URL: `https://github.com/maksyms/ha-addons`
3. Click **Add**, then refresh
4. Find **Atomic Ingest** in the store and click **Install**

## Adapters

| Adapter | Schedule | Source | Auth |
|---------|----------|--------|------|
| **Readwise** | Hourly (`:00`) | Highlights v2 export + Reader v3 list | `READWISE_API_TOKEN` |
| **Raindrop** | Hourly (`:30`) | Bookmarks via ingest_url, uploaded files via create_atom | `RAINDROP_TOKEN` |
| **Evernote** | Daily (3 AM) | `.enex` files from `/share/atomic-ingest/evernote/consume/` | None (file-based) |

### Readwise

One atom per book with blockquoted highlights and notes. Reader items use `ingest_url` for full content with highlight enrichment.

### Raindrop.io

URL bookmarks use `ingest_url` for full content. Uploaded files/videos create atoms directly. Notes and highlights are appended via update.

### Evernote

Scans a consume folder for `.enex` files, parses ENEX XML to Markdown, bulk creates atoms, then moves processed files to `processed/`.

## Configuration

### HA UI Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `atomic_api_url` | Yes | `""` | Atomic API URL (e.g., `http://23930cf1-atomic:8081`) |
| `atomic_api_token` | Yes | `""` | API token created in Atomic's web UI |
| `log_level` | No | `info` | `debug`, `info`, `warning`, or `error` |

### Environment File

Source credentials and schedule overrides go in `/addon_configs/atomic-ingest/.env` (mounted as `/config/.env` inside the container). See `.env.example`:

```env
# Source credentials
READWISE_API_TOKEN=
RAINDROP_TOKEN=

# Schedule overrides (cron expressions)
# READWISE_SCHEDULE="0 * * * *"    # default: hourly on the hour
# RAINDROP_SCHEDULE="30 * * * *"   # default: hourly at :30
# EVERNOTE_SCHEDULE="0 3 * * *"    # default: daily at 3am

# Debug: limit items processed per adapter run (remove for production)
# INGEST_LIMIT=5                   # global limit for all adapters
# READWISE_LIMIT=5                 # override for readwise only
# RAINDROP_LIMIT=5                 # override for raindrop only
# EVERNOTE_LIMIT=5                 # override for evernote only
```

## Architecture

Cron-based Python container. `run.sh` reads HA options, sources `.env`, dumps environment for cron, generates a crontab, and execs `cron -f` as PID 1. Each adapter runs as an independent cron job.

```
crond (PID 1)
  ├── readwise.py   (hourly)
  ├── raindrop.py   (hourly)
  └── evernote.py   (daily)
```

### Shared Libraries

| Module | Purpose |
|--------|---------|
| `lib/atomic_client.py` | Atomic REST API client (`ingest_url`, `create_atom`, `update_atom`, `bulk_create`) |
| `lib/sync_state.py` | Per-adapter JSON state persistence in `/data/` |
| `lib/folder_consumer.py` | Consume/processed folder pattern for file-based adapters |
| `lib/limit.py` | Framework-level ingest limit for debugging |

## Debugging

Set `INGEST_LIMIT=N` in `.env` to limit each adapter to N items per run. Useful for testing connectivity and verifying pipeline behavior without ingesting everything.

Per-adapter overrides (`READWISE_LIMIT`, `RAINDROP_LIMIT`, `EVERNOTE_LIMIT`) take precedence over the global limit.

When a limit is active:
- **Sync state is not updated** — the next unlimited run picks up from where the last real run left off
- **Evernote**: partially-processed files stay in `consume/` for re-processing (dedup prevents duplicates)

## Adding a New Adapter

1. Create `adapters/<name>.py` with a `main()` that reads env vars, imports from `lib/`, and syncs
2. Add credential env var to `.env.example`
3. Add `<NAME>_SCHEDULE` to `run.sh` crontab generation with a default
4. Add the env var export to `run.sh`'s env dump

## License

Private / unlicensed.
