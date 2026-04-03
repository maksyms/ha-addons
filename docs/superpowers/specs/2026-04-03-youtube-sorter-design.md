# YouTube Sorter — Design Spec

## Overview

Home Assistant add-on that automatically manages YouTube playlists: removes watched videos, classifies remaining videos by category using AI, and reorders playlists by category priority and date.

## Requirements

1. Videos watched to 90%+ (configurable threshold) in any configured playlist are removed from all configured playlists
2. Videos are classified into a global, ordered list of categories using Anthropic Sonnet 4.6 (title + description + tags)
3. Playlists are reordered by category priority (category list order), then by date (added or published, ascending or descending) — all global settings
4. Optionally, sublists named `"<playlist name> - <category>"` are created/updated
5. SQLite database caches classifications to avoid redundant AI calls
6. Read-only web UI renders the database as a table with Dracula colour scheme

## Approach

**yt-dlp as backbone.** Use yt-dlp for all YouTube read operations (playlist metadata, video info) and cookie-based auth. Custom innertube API client for write operations (remove, reorder, create playlists) and watch progress detection, using the same cookies.

Fallback: if innertube watch progress proves too fragile, a manual "mark as watched" mechanism can be added later.

## Add-on Structure

```
youtube-sorter/
├── config.yaml          # HA add-on manifest
├── Dockerfile           # Python 3.12, yt-dlp, deps
├── run.sh               # Entrypoint: load env, start scheduler + web server
├── requirements.txt
├── sorter/
│   ├── __init__.py
│   ├── main.py          # Orchestrator: schedule + on-demand trigger
│   ├── youtube.py       # yt-dlp reads + innertube writes
│   ├── classifier.py    # Anthropic API classification
│   ├── database.py      # SQLite operations
│   └── web.py           # Flask read-only web UI
├── static/
│   └── index.html       # Database table view (Dracula theme)
├── CHANGELOG.md
├── icon.png
└── logo.png
```

## Configuration

Via HA UI options in `config.yaml`:

| Option | Required | Default | Description |
|---|---|---|---|
| `youtube_cookies` | No | `/share/youtube-sorter/cookies.txt` | Path to Netscape-format cookies file |
| `playlist_ids` | Yes | — | List of YouTube playlist IDs to process |
| `anthropic_api_key` | Yes | — | Anthropic API key for classification |
| `categories` | Yes | — | Ordered list of category names (order = sort priority) |
| `schedule_cron` | No | `0 */6 * * *` | Cron expression for scheduled runs |
| `date_sort_field` | No | `date_added` | `date_added` or `date_published` |
| `date_sort_order` | No | `desc` | `asc` or `desc` |
| `watch_threshold` | No | `90` | Percentage threshold for "watched" |
| `create_sublists` | No | `false` | Create/update per-category sublists |

Cookies placed at `/share/youtube-sorter/cookies.txt`.

## YouTube Interaction Layer (`youtube.py`)

### Reading (yt-dlp)

- `get_playlist_videos(playlist_id, cookies_path)` — returns list of video metadata (id, title, description, tags, position, date published, date added)
- `get_watch_progress(video_ids, cookies_path)` — fetches watch progress via innertube `browse` endpoint (same internal API that renders the red progress bar). Falls back to "unknown" if unavailable.

### Writing (custom innertube client)

- `remove_from_playlist(playlist_id, video_id, cookies_path)` — removes a video
- `reorder_playlist(playlist_id, ordered_video_ids, cookies_path)` — sets playlist order by moving videos via innertube `playlist/edit` action
- `add_to_playlist(playlist_id, video_id, cookies_path)` — for populating sublists
- `create_playlist(title, privacy="private")` — creates a new playlist for sublists (private by default)

### Cookie Handling

- Reads Netscape-format cookies file (standard browser export, same format yt-dlp accepts)
- Extracts innertube session tokens (SAPISID, etc.) from cookies for write operations
- Logs a clear warning when cookies expire so the user knows to re-export

### Rate Limiting

- Sequential processing with delays between write operations
- Configurable backoff on 429 responses

## Classification (`classifier.py`)

The classifier is a thin layer responsible only for AI classification calls. The orchestrator (`main.py`) owns the diff logic.

### Prompt Design

- System prompt defines the categories with exact names
- User prompt provides video metadata (title, description, tags)
- JSON output: `{"category": "<exact category name>", "confidence": 0.0-1.0}`
- Confidence below 0.5 assigned to "Other"

### Batching

- 10-20 videos per API call to reduce cost and latency
- Single prompt lists all videos, returns JSON array of classifications
- Falls back to one-at-a-time if batch response fails to parse

### Cost

- Sonnet 4.6: ~$3/M input tokens, ~$15/M output tokens
- A batch of 20 videos ≈ 2-4K input tokens ≈ ~$0.01 per batch

### Extensibility

- Classifier accepts a `metadata` dict per video — adding a `transcript` field later requires only populating it upstream and adjusting the prompt

## Database (`database.py`)

SQLite at `/data/youtube_sorter.db` (persisted across add-on rebuilds).

### Schema

```sql
CREATE TABLE videos (
    video_id TEXT NOT NULL,
    playlist_id TEXT NOT NULL,  -- '_removed' for removed videos
    title TEXT,
    description TEXT,
    tags TEXT,                   -- JSON array
    category TEXT,
    confidence REAL,
    date_published TEXT,         -- ISO 8601
    date_added TEXT,             -- ISO 8601
    classified_at TEXT,          -- ISO 8601
    removed_at TEXT,             -- ISO 8601, NULL if active
    PRIMARY KEY (video_id, playlist_id)
);

CREATE TABLE run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    playlists_processed INTEGER,
    videos_classified INTEGER,
    videos_removed INTEGER,
    videos_reordered INTEGER,
    errors TEXT,                  -- JSON array of error messages, NULL if none
    status TEXT                   -- 'success', 'error', 'partial'
);
```

### Removal Behavior

When a video is detected as watched (>= threshold) in any playlist:
1. Remove it from all configured playlists via YouTube API
2. Set `removed_at` on all existing rows for that video
3. Insert a row with `playlist_id = '_removed'` (preserving classification)

This prevents re-classification if the video reappears and provides historical record.

## Web UI (`web.py` + `static/index.html`)

Single-file Flask app serving one static HTML page and a JSON API.

### Endpoints

- `GET /` — serves `index.html`
- `GET /api/videos` — returns all videos as JSON
- `GET /api/trigger` — triggers an on-demand run (returns immediately, runs async)

### `index.html`

- Inline CSS with Dracula colour scheme (`#282a36` background, `#f8f8f2` foreground, purple/pink/green accents)
- Plain `<table>` populated by `fetch('/api/videos')`
- `<select>` dropdowns for playlist and category filtering (client-side JS `.filter()`)
- "Run Now" button hitting `/api/trigger`
- Run log section at the bottom
- No build step, no dependencies, no templates

## Scheduling & Orchestration (`main.py`)

### Startup

- `run.sh` starts the Flask web server and scheduler in the same Python process
- Scheduler uses APScheduler with cron trigger from `schedule_cron` config
- `/api/trigger` queues the same job for immediate execution

### Single Run Flow

1. Load config (playlists, categories, thresholds)
2. Fetch all configured playlists via yt-dlp
3. Check watch progress for all videos across all playlists
4. Remove watched videos (>= threshold) from all playlists, mark as `_removed` in DB
5. For each playlist:
   a. Compare videos against DB — identify unclassified ones
   b. Batch-classify new videos via Anthropic API
   c. Store classifications in DB
   d. Compute desired order (category priority, then date sort)
   e. Compare current order to desired — reorder if different
   f. If `create_sublists` enabled: create/update sublists
6. Log run to `run_log`

### Concurrency

- Lock prevents overlapping runs (schedule + manual trigger)
- Web UI remains responsive during runs

### Error Handling

- Single playlist failure: log error, continue with next playlist
- YouTube auth failure: log "cookies expired" message, skip the run
