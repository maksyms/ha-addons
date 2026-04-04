# YouTube Sorter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an HA add-on that removes watched YouTube videos from playlists, classifies remaining videos by category using AI, and reorders playlists by category priority and date.

**Architecture:** Python add-on using yt-dlp for YouTube reads and cookie-based innertube API for writes. SQLite for classification cache. Flask for read-only web UI with Dracula theme. APScheduler for cron + on-demand triggers.

**Tech Stack:** Python 3.12, yt-dlp, Flask, APScheduler, anthropic SDK, SQLite3, httpx (innertube client)

**Spec:** `docs/superpowers/specs/2026-04-03-youtube-sorter-design.md`

---

### File Structure

All new files in `youtube-sorter/`.

| File | Purpose |
|------|---------|
| `youtube-sorter/config.yaml` | HA add-on manifest with options schema |
| `youtube-sorter/Dockerfile` | Alpine + Python 3.12, yt-dlp, pip deps |
| `youtube-sorter/run.sh` | Env loading, launch Python app |
| `youtube-sorter/requirements.txt` | Python dependencies |
| `youtube-sorter/sorter/__init__.py` | Package init |
| `youtube-sorter/sorter/config.py` | Config loading from env/options.json |
| `youtube-sorter/sorter/database.py` | SQLite schema, CRUD operations |
| `youtube-sorter/sorter/youtube.py` | yt-dlp reads + innertube writes |
| `youtube-sorter/sorter/innertube.py` | Innertube API client (auth, watch progress, playlist mutations) |
| `youtube-sorter/sorter/classifier.py` | Anthropic API classification |
| `youtube-sorter/sorter/main.py` | Orchestrator: run logic, scheduler, Flask integration |
| `youtube-sorter/sorter/web.py` | Flask app with API endpoints |
| `youtube-sorter/static/index.html` | Read-only DB table view (Dracula theme) |
| `youtube-sorter/tests/__init__.py` | Test package |
| `youtube-sorter/tests/test_database.py` | Database unit tests |
| `youtube-sorter/tests/test_classifier.py` | Classifier unit tests (mocked Anthropic) |
| `youtube-sorter/tests/test_youtube.py` | YouTube layer unit tests (mocked yt-dlp) |
| `youtube-sorter/tests/test_main.py` | Orchestrator unit tests (mocked deps) |
| `youtube-sorter/tests/test_web.py` | Flask endpoint tests |
| `youtube-sorter/CHANGELOG.md` | Initial changelog |
| `.github/workflows/deploy-youtube-sorter.yml` | CI/CD workflow |

---

### Task 1: Scaffold Add-on

**Files:**
- Create: `youtube-sorter/config.yaml`
- Create: `youtube-sorter/Dockerfile`
- Create: `youtube-sorter/run.sh`
- Create: `youtube-sorter/requirements.txt`
- Create: `youtube-sorter/sorter/__init__.py`
- Create: `youtube-sorter/sorter/config.py`
- Create: `youtube-sorter/CHANGELOG.md`

- [ ] **Step 1: Create config.yaml**

```yaml
name: YouTube Sorter
description: >-
  Manages YouTube playlists: removes watched videos, classifies
  remaining by category using AI, reorders by priority and date.
version: "1.0.0"
slug: youtube-sorter
url: "https://github.com/maksyms/ha-addons"
arch:
  - aarch64
  - amd64
init: false
startup: application
boot: auto
ingress: true
ingress_port: 5000
panel_icon: mdi:youtube
map:
  - share:rw
options:
  youtube_cookies: "/share/youtube-sorter/cookies.txt"
  playlist_ids:
    - ""
  anthropic_api_key: ""
  categories:
    - "Claude & AI"
    - "Investing & Wealth"
    - "Health & Biohacking"
    - "Men's Fashion"
    - "Sailing & Outdoors"
    - "History & Geopolitics"
    - "Software Engineering"
    - "Science"
    - "Relationships"
    - "Other"
  schedule_cron: "0 */6 * * *"
  date_sort_field: "date_added"
  date_sort_order: "desc"
  watch_threshold: 90
  create_sublists: false
schema:
  youtube_cookies: str?
  playlist_ids:
    - str
  anthropic_api_key: str
  categories:
    - str
  schedule_cron: str?
  date_sort_field: str?
  date_sort_order: str?
  watch_threshold: int?
  create_sublists: bool?
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip jq

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY sorter/ ./sorter/
COPY static/ ./static/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
```

- [ ] **Step 3: Create requirements.txt**

```
yt-dlp>=2025.3.31
flask>=3.1
apscheduler>=3.11
anthropic>=0.52
httpx>=0.28
```

- [ ] **Step 4: Create run.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Import .env from /share/youtube-sorter/ if present
if [ -f /share/youtube-sorter/.env ]; then
    cp /share/youtube-sorter/.env /data/.env
fi

if [ -f /data/.env ]; then
    set -a
    source /data/.env
    set +a
else
    # Fall back to add-on UI options: export each as an env var
    CONFIG=/data/options.json
    for key in $(jq -r 'keys[]' "$CONFIG"); do
        value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
        # Skip arrays/objects — handled by config.py reading options.json directly
        if [ "$value" != "null" ] && ! echo "$value" | jq -e 'type == "array" or type == "object"' >/dev/null 2>&1; then
            export "$key=$value"
        fi
    done
fi

cd /data
exec python3 -m sorter.main --options /data/options.json --db /data/youtube_sorter.db
```

- [ ] **Step 5: Create sorter/__init__.py**

```python
"""YouTube Sorter — HA add-on for playlist management."""
```

- [ ] **Step 6: Create sorter/config.py**

```python
"""Configuration loading from HA options.json and environment variables."""

import json
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    youtube_cookies: str = "/share/youtube-sorter/cookies.txt"
    playlist_ids: list[str] = field(default_factory=list)
    anthropic_api_key: str = ""
    categories: list[str] = field(default_factory=list)
    schedule_cron: str = "0 */6 * * *"
    date_sort_field: str = "date_added"
    date_sort_order: str = "desc"
    watch_threshold: int = 90
    create_sublists: bool = False
    db_path: str = "/data/youtube_sorter.db"


def load_config(options_path: str, db_path: str) -> Config:
    """Load config from options.json, with env var overrides for scalars."""
    config = Config(db_path=db_path)

    if os.path.exists(options_path):
        with open(options_path) as f:
            opts = json.load(f)
        config.playlist_ids = [p for p in opts.get("playlist_ids", []) if p]
        config.categories = [c for c in opts.get("categories", []) if c]
        config.anthropic_api_key = opts.get("anthropic_api_key", "")
        config.youtube_cookies = opts.get("youtube_cookies", config.youtube_cookies)
        config.schedule_cron = opts.get("schedule_cron", config.schedule_cron)
        config.date_sort_field = opts.get("date_sort_field", config.date_sort_field)
        config.date_sort_order = opts.get("date_sort_order", config.date_sort_order)
        config.watch_threshold = opts.get("watch_threshold", config.watch_threshold)
        config.create_sublists = opts.get("create_sublists", config.create_sublists)

    # Env var overrides for scalars
    for env_key in ["youtube_cookies", "anthropic_api_key", "schedule_cron",
                    "date_sort_field", "date_sort_order"]:
        val = os.environ.get(env_key.upper()) or os.environ.get(env_key)
        if val:
            setattr(config, env_key, val)

    wt = os.environ.get("WATCH_THRESHOLD") or os.environ.get("watch_threshold")
    if wt:
        config.watch_threshold = int(wt)

    return config
```

- [ ] **Step 7: Create CHANGELOG.md**

```markdown
## 1.0.0
- Initial release
```

- [ ] **Step 8: Commit scaffold**

```bash
git add youtube-sorter/
git commit -m "feat(youtube-sorter): scaffold add-on structure"
```

---

### Task 2: Database Layer (TDD)

**Files:**
- Create: `youtube-sorter/sorter/database.py`
- Create: `youtube-sorter/tests/__init__.py`
- Create: `youtube-sorter/tests/test_database.py`

- [ ] **Step 1: Write failing tests for database**

```python
# youtube-sorter/tests/test_database.py
import sqlite3
from sorter.database import Database


def make_db():
    """Create an in-memory database for testing."""
    return Database(":memory:")


def test_init_creates_tables():
    db = make_db()
    cursor = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "run_log" in tables
    assert "videos" in tables


def test_upsert_and_get_video():
    db = make_db()
    db.upsert_video(
        video_id="abc123",
        playlist_id="PL_test",
        title="Test Video",
        description="A test",
        tags='["python", "test"]',
        category="Science",
        confidence=0.95,
        date_published="2025-01-01T00:00:00Z",
        date_added="2025-06-01T00:00:00Z",
    )
    video = db.get_video("abc123", "PL_test")
    assert video is not None
    assert video["title"] == "Test Video"
    assert video["category"] == "Science"
    assert video["confidence"] == 0.95
    assert video["removed_at"] is None


def test_get_video_not_found():
    db = make_db()
    assert db.get_video("nonexistent", "PL_test") is None


def test_get_classified_video_ids():
    db = make_db()
    db.upsert_video("v1", "PL1", "T1", "", "[]", "Science", 0.9, "", "")
    db.upsert_video("v2", "PL1", "T2", "", "[]", "Other", 0.4, "", "")
    ids = db.get_classified_video_ids("PL1")
    assert ids == {"v1", "v2"}


def test_mark_removed():
    db = make_db()
    db.upsert_video("v1", "PL1", "T1", "", "[]", "Science", 0.9, "", "")
    db.upsert_video("v1", "PL2", "T1", "", "[]", "Science", 0.9, "", "")
    db.mark_removed("v1")

    # Original rows have removed_at set
    v1_pl1 = db.get_video("v1", "PL1")
    assert v1_pl1["removed_at"] is not None

    v1_pl2 = db.get_video("v1", "PL2")
    assert v1_pl2["removed_at"] is not None

    # A _removed row exists
    v1_removed = db.get_video("v1", "_removed")
    assert v1_removed is not None
    assert v1_removed["category"] == "Science"


def test_get_all_videos():
    db = make_db()
    db.upsert_video("v1", "PL1", "T1", "", "[]", "Science", 0.9, "", "")
    db.upsert_video("v2", "PL1", "T2", "", "[]", "Other", 0.4, "", "")
    videos = db.get_all_videos()
    assert len(videos) == 2


def test_log_run():
    db = make_db()
    run_id = db.log_run_start()
    assert run_id > 0
    db.log_run_end(run_id, playlists_processed=2, videos_classified=5,
                   videos_removed=1, videos_reordered=3, status="success")
    runs = db.get_recent_runs(limit=5)
    assert len(runs) == 1
    assert runs[0]["playlists_processed"] == 2
    assert runs[0]["status"] == "success"


def test_get_classification_for_video():
    """If a video exists in _removed, we can still get its category."""
    db = make_db()
    db.upsert_video("v1", "PL1", "T1", "", "[]", "Science", 0.9, "", "")
    db.mark_removed("v1")
    # The video should be findable via _removed
    v = db.get_video("v1", "_removed")
    assert v["category"] == "Science"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd youtube-sorter && python -m pytest tests/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sorter.database'`

- [ ] **Step 3: Implement database.py**

```python
# youtube-sorter/sorter/database.py
"""SQLite database for video classification cache and run logs."""

import json
import sqlite3
from datetime import datetime, timezone


class Database:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT NOT NULL,
                playlist_id TEXT NOT NULL,
                title TEXT,
                description TEXT,
                tags TEXT,
                category TEXT,
                confidence REAL,
                date_published TEXT,
                date_added TEXT,
                classified_at TEXT,
                removed_at TEXT,
                PRIMARY KEY (video_id, playlist_id)
            );
            CREATE TABLE IF NOT EXISTS sublists (
                playlist_id TEXT NOT NULL,
                category TEXT NOT NULL,
                sublist_id TEXT NOT NULL,
                sublist_title TEXT,
                PRIMARY KEY (playlist_id, category)
            );
            CREATE TABLE IF NOT EXISTS run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                finished_at TEXT,
                playlists_processed INTEGER,
                videos_classified INTEGER,
                videos_removed INTEGER,
                videos_reordered INTEGER,
                errors TEXT,
                status TEXT
            );
        """)

    def upsert_video(self, video_id: str, playlist_id: str, title: str,
                     description: str, tags: str, category: str,
                     confidence: float, date_published: str,
                     date_added: str):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO videos
                (video_id, playlist_id, title, description, tags, category,
                 confidence, date_published, date_added, classified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id, playlist_id) DO UPDATE SET
                title=excluded.title,
                description=excluded.description,
                tags=excluded.tags,
                category=excluded.category,
                confidence=excluded.confidence,
                date_published=excluded.date_published,
                date_added=excluded.date_added,
                classified_at=excluded.classified_at
        """, (video_id, playlist_id, title, description, tags, category,
              confidence, date_published, date_added, now))
        self.conn.commit()

    def get_video(self, video_id: str, playlist_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = ? AND playlist_id = ?",
            (video_id, playlist_id)
        ).fetchone()
        return dict(row) if row else None

    def get_classified_video_ids(self, playlist_id: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT video_id FROM videos WHERE playlist_id = ? AND removed_at IS NULL",
            (playlist_id,)
        ).fetchall()
        return {row["video_id"] for row in rows}

    def get_any_classification(self, video_id: str) -> dict | None:
        """Get classification for a video from any playlist (including _removed)."""
        row = self.conn.execute(
            "SELECT category, confidence FROM videos WHERE video_id = ? AND category IS NOT NULL LIMIT 1",
            (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def mark_removed(self, video_id: str):
        now = datetime.now(timezone.utc).isoformat()
        # Get existing classification from any row
        existing = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = ? AND category IS NOT NULL LIMIT 1",
            (video_id,)
        ).fetchone()

        # Mark all existing rows as removed
        self.conn.execute(
            "UPDATE videos SET removed_at = ? WHERE video_id = ? AND removed_at IS NULL",
            (now, video_id)
        )

        # Insert _removed row if we have classification data
        if existing:
            e = dict(existing)
            self.conn.execute("""
                INSERT OR REPLACE INTO videos
                    (video_id, playlist_id, title, description, tags, category,
                     confidence, date_published, date_added, classified_at, removed_at)
                VALUES (?, '_removed', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (video_id, e["title"], e["description"], e["tags"],
                  e["category"], e["confidence"], e["date_published"],
                  e["date_added"], e["classified_at"], now))

        self.conn.commit()

    def get_all_videos(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM videos ORDER BY playlist_id, category, date_added").fetchall()
        return [dict(r) for r in rows]

    def log_run_start(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "INSERT INTO run_log (started_at, status) VALUES (?, 'running')",
            (now,)
        )
        self.conn.commit()
        return cursor.lastrowid

    def log_run_end(self, run_id: int, playlists_processed: int = 0,
                    videos_classified: int = 0, videos_removed: int = 0,
                    videos_reordered: int = 0, errors: list[str] | None = None,
                    status: str = "success"):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            UPDATE run_log SET
                finished_at = ?, playlists_processed = ?,
                videos_classified = ?, videos_removed = ?,
                videos_reordered = ?, errors = ?, status = ?
            WHERE id = ?
        """, (now, playlists_processed, videos_classified, videos_removed,
              videos_reordered, json.dumps(errors) if errors else None,
              status, run_id))
        self.conn.commit()

    def get_recent_runs(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM run_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sublist_id(self, playlist_id: str, category: str) -> str | None:
        row = self.conn.execute(
            "SELECT sublist_id FROM sublists WHERE playlist_id = ? AND category = ?",
            (playlist_id, category)
        ).fetchone()
        return row["sublist_id"] if row else None

    def save_sublist(self, playlist_id: str, category: str,
                     sublist_id: str, sublist_title: str):
        self.conn.execute("""
            INSERT OR REPLACE INTO sublists (playlist_id, category, sublist_id, sublist_title)
            VALUES (?, ?, ?, ?)
        """, (playlist_id, category, sublist_id, sublist_title))
        self.conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd youtube-sorter && python -m pytest tests/test_database.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add youtube-sorter/sorter/database.py youtube-sorter/tests/
git commit -m "feat(youtube-sorter): add database layer with tests"
```

---

### Task 3: YouTube Read Layer (TDD)

**Files:**
- Create: `youtube-sorter/sorter/youtube.py`
- Create: `youtube-sorter/tests/test_youtube.py`

- [ ] **Step 1: Write failing tests**

```python
# youtube-sorter/tests/test_youtube.py
from unittest.mock import patch, MagicMock
from sorter.youtube import get_playlist_videos, PlaylistVideo


# Simulates what yt-dlp returns for a playlist extraction
FAKE_YTDLP_PLAYLIST = {
    "entries": [
        {
            "id": "dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up",
            "description": "The official video for Rick Astley",
            "tags": ["rick astley", "never gonna give you up"],
            "upload_date": "20091025",
            "playlist_index": 1,
        },
        {
            "id": "9bZkp7q19f0",
            "title": "PSY - GANGNAM STYLE",
            "description": "Official music video",
            "tags": ["psy", "gangnam"],
            "upload_date": "20120715",
            "playlist_index": 2,
        },
    ],
    "title": "My Test Playlist",
}


@patch("sorter.youtube.yt_dlp.YoutubeDL")
def test_get_playlist_videos(mock_ydl_class):
    mock_ydl = MagicMock()
    mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = FAKE_YTDLP_PLAYLIST

    videos = get_playlist_videos("PLtest123", "/tmp/cookies.txt")

    assert len(videos) == 2
    assert videos[0].video_id == "dQw4w9WgXcQ"
    assert videos[0].title == "Rick Astley - Never Gonna Give You Up"
    assert videos[0].tags == ["rick astley", "never gonna give you up"]
    assert videos[0].date_published == "2009-10-25"
    assert videos[0].position == 1
    assert videos[1].video_id == "9bZkp7q19f0"


@patch("sorter.youtube.yt_dlp.YoutubeDL")
def test_get_playlist_videos_skips_none_entries(mock_ydl_class):
    """yt-dlp sometimes returns None entries for unavailable videos."""
    data = {
        "entries": [
            None,
            {
                "id": "abc",
                "title": "Valid",
                "description": "",
                "tags": None,
                "upload_date": "20250101",
                "playlist_index": 2,
            },
        ],
        "title": "Test",
    }
    mock_ydl = MagicMock()
    mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = data

    videos = get_playlist_videos("PLtest", "/tmp/cookies.txt")
    assert len(videos) == 1
    assert videos[0].video_id == "abc"
    assert videos[0].tags == []


@patch("sorter.youtube.yt_dlp.YoutubeDL")
def test_get_playlist_videos_returns_playlist_title(mock_ydl_class):
    mock_ydl = MagicMock()
    mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = FAKE_YTDLP_PLAYLIST

    videos = get_playlist_videos("PLtest", "/tmp/cookies.txt")
    # playlist_title is stored on each video for convenience
    assert videos[0].playlist_title == "My Test Playlist"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd youtube-sorter && python -m pytest tests/test_youtube.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sorter.youtube'`

- [ ] **Step 3: Implement youtube.py (read operations)**

```python
# youtube-sorter/sorter/youtube.py
"""YouTube interaction layer — yt-dlp for reads, innertube for writes."""

import logging
from dataclasses import dataclass, field

import yt_dlp

logger = logging.getLogger(__name__)


@dataclass
class PlaylistVideo:
    video_id: str
    title: str
    description: str
    tags: list[str]
    date_published: str  # YYYY-MM-DD
    date_added: str  # YYYY-MM-DD or empty if unavailable
    position: int
    playlist_title: str = ""


def _parse_upload_date(raw: str | None) -> str:
    """Convert yt-dlp's YYYYMMDD to YYYY-MM-DD."""
    if not raw or len(raw) != 8:
        return ""
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def get_playlist_videos(playlist_id: str, cookies_path: str) -> list[PlaylistVideo]:
    """Fetch all videos in a playlist using yt-dlp."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "cookiefile": cookies_path,
        "skip_download": True,
        "ignoreerrors": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/playlist?list={playlist_id}",
            download=False,
        )

    if not info or "entries" not in info:
        logger.warning("No entries found for playlist %s", playlist_id)
        return []

    playlist_title = info.get("title", "")
    videos = []
    for entry in info["entries"]:
        if entry is None:
            continue
        videos.append(PlaylistVideo(
            video_id=entry["id"],
            title=entry.get("title", ""),
            description=entry.get("description", ""),
            tags=entry.get("tags") or [],
            date_published=_parse_upload_date(entry.get("upload_date")),
            date_added="",  # Not available via yt-dlp; innertube needed
            position=entry.get("playlist_index", 0),
            playlist_title=playlist_title,
        ))

    return videos
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd youtube-sorter && python -m pytest tests/test_youtube.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add youtube-sorter/sorter/youtube.py youtube-sorter/tests/test_youtube.py
git commit -m "feat(youtube-sorter): add YouTube read layer with yt-dlp"
```

---

### Task 4: Innertube Client (Research + Implement)

**Files:**
- Create: `youtube-sorter/sorter/innertube.py`

This task requires reverse-engineering YouTube's internal innertube API. The implementation will be informed by yt-dlp's source code (specifically `yt_dlp/extractor/youtube.py`) which already handles innertube auth and requests.

- [ ] **Step 1: Research innertube auth from yt-dlp source**

Clone yt-dlp and study the innertube authentication mechanism:

```bash
cd /tmp && git clone --depth 1 https://github.com/yt-dlp/yt-dlp.git
```

Key areas to study in `/tmp/yt-dlp/yt_dlp/extractor/youtube.py`:
- `_generate_sapisidhash_header()` — SAPISID cookie → auth header
- `_call_api()` — innertube request structure
- `_extract_response()` — response parsing
- Search for `playlist/edit` or `browse` actions related to playlist mutation

Document findings before implementing.

- [ ] **Step 2: Implement innertube.py**

```python
# youtube-sorter/sorter/innertube.py
"""Innertube API client for YouTube playlist mutations and watch progress."""

import hashlib
import http.cookiejar
import json
import logging
import math
import time

import httpx

logger = logging.getLogger(__name__)

INNERTUBE_API_URL = "https://www.youtube.com/youtubei/v1"
INNERTUBE_CLIENT = {
    "clientName": "WEB",
    "clientVersion": "2.20250401.01.00",
}


class InnertubeClient:
    def __init__(self, cookies_path: str):
        self.cookies_path = cookies_path
        self._cookies: dict[str, str] = {}
        self._load_cookies()

    def _load_cookies(self):
        """Load Netscape-format cookies file into a dict."""
        jar = http.cookiejar.MozillaCookieJar(self.cookies_path)
        jar.load(ignore_discard=True, ignore_expires=True)
        self._cookies = {c.name: c.value for c in jar}

    def _sapisidhash(self) -> str | None:
        """Generate SAPISIDHASH authorization header from cookies."""
        sapisid = self._cookies.get("SAPISID") or self._cookies.get("__Secure-3PAPISID")
        if not sapisid:
            return None
        timestamp = str(math.floor(time.time()))
        hash_input = f"{timestamp} {sapisid} https://www.youtube.com"
        sha1 = hashlib.sha1(hash_input.encode()).hexdigest()
        return f"SAPISIDHASH {timestamp}_{sha1}"

    def _make_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Origin": "https://www.youtube.com",
            "X-Youtube-Client-Name": "1",
            "X-Youtube-Client-Version": INNERTUBE_CLIENT["clientVersion"],
        }
        auth = self._sapisidhash()
        if auth:
            headers["Authorization"] = auth
        return headers

    def _make_cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    def _request(self, endpoint: str, body: dict) -> dict:
        """Make an innertube API request."""
        body.setdefault("context", {"client": INNERTUBE_CLIENT})
        headers = self._make_headers()
        headers["Cookie"] = self._make_cookie_header()

        url = f"{INNERTUBE_API_URL}/{endpoint}"
        response = httpx.post(url, json=body, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_watch_progress(self, video_ids: list[str]) -> dict[str, float]:
        """Fetch watch progress for videos. Returns {video_id: percentage}.

        Uses the browse endpoint to get playback resume data.
        Videos without progress data return -1 (unknown).
        """
        progress = {}
        # Process in small batches to avoid hitting limits
        # Note: the exact innertube endpoint/shape will be refined during research (Step 1).
        # The browse endpoint for watch history includes overlay data with progress bars.
        for vid in video_ids:
            try:
                data = self._request("player", {
                    "videoId": vid,
                })
                # playbackTracking > videostatsPlaybackUrl contains resume point info
                # This will be refined based on actual API response shape
                playback = data.get("playbackTracking", {})
                duration = data.get("videoDetails", {}).get("lengthSeconds")
                # Note: actual progress may need to come from a different endpoint
                # (e.g., browse with watch history). This is a starting point.
                progress[vid] = -1  # Default unknown until we find the right field
            except Exception as e:
                logger.debug("Could not get watch progress for %s: %s", vid, e)
                progress[vid] = -1
        return progress

    def remove_from_playlist(self, playlist_id: str, video_id: str,
                             set_video_id: str | None = None) -> bool:
        """Remove a video from a playlist.

        set_video_id is the playlist-specific item ID (different from video_id).
        If not provided, we'll need to look it up first.
        """
        try:
            # The playlist/edit action uses setVideoId (playlist item ID),
            # not the video ID. This needs to be obtained from playlist data.
            body = {
                "actions": [{
                    "action": "ACTION_REMOVE_VIDEO",
                    "removedVideoId": video_id,
                    "setVideoId": set_video_id,
                }],
                "playlistId": playlist_id,
            }
            self._request("browse/edit_playlist", body)
            return True
        except Exception as e:
            logger.error("Failed to remove %s from %s: %s", video_id, playlist_id, e)
            return False

    def add_to_playlist(self, playlist_id: str, video_id: str) -> bool:
        """Add a video to a playlist."""
        try:
            body = {
                "actions": [{
                    "action": "ACTION_ADD_VIDEO",
                    "addedVideoId": video_id,
                }],
                "playlistId": playlist_id,
            }
            self._request("browse/edit_playlist", body)
            return True
        except Exception as e:
            logger.error("Failed to add %s to %s: %s", video_id, playlist_id, e)
            return False

    def clear_playlist(self, playlist_id: str, video_ids_and_set_ids: list[tuple[str, str]]) -> bool:
        """Remove all videos from a playlist (for sublist refresh)."""
        for video_id, set_video_id in video_ids_and_set_ids:
            if not self.remove_from_playlist(playlist_id, video_id, set_video_id):
                return False
            time.sleep(0.3)  # Rate limit
        return True

    def reorder_playlist(self, playlist_id: str,
                         ordered_set_video_ids: list[str]) -> bool:
        """Reorder a playlist by moving items sequentially.

        ordered_set_video_ids: list of setVideoId values in desired order.
        Uses ACTION_MOVE_VIDEO_AFTER to place each item after the previous.
        """
        try:
            for i in range(1, len(ordered_set_video_ids)):
                body = {
                    "actions": [{
                        "action": "ACTION_MOVE_VIDEO_AFTER",
                        "setVideoId": ordered_set_video_ids[i],
                        "movedSetVideoIdSuccessorId": ordered_set_video_ids[i - 1],
                    }],
                    "playlistId": playlist_id,
                }
                self._request("browse/edit_playlist", body)
                time.sleep(0.3)
            return True
        except Exception as e:
            logger.error("Failed to reorder playlist %s: %s", playlist_id, e)
            return False

    def create_playlist(self, title: str, privacy: str = "PRIVATE") -> str | None:
        """Create a new playlist. Returns the playlist ID or None on failure."""
        try:
            body = {
                "title": title,
                "privacyStatus": privacy,
            }
            resp = self._request("playlist/create", body)
            return resp.get("playlistId")
        except Exception as e:
            logger.error("Failed to create playlist '%s': %s", title, e)
            return None
```

**Note:** The exact innertube endpoint paths and request/response shapes (`browse/edit_playlist`, `playlist/create`, action names) will be refined during the research step. The structure above is based on known patterns from yt-dlp's source and community documentation, but the actual field names (e.g., `setVideoId`, `ACTION_MOVE_VIDEO_AFTER`) must be verified against live API responses. Mark this file as needing validation during integration testing (Task 8).

- [ ] **Step 3: Commit**

```bash
git add youtube-sorter/sorter/innertube.py
git commit -m "feat(youtube-sorter): add innertube client for playlist mutations"
```

---

### Task 5: Classifier (TDD)

**Files:**
- Create: `youtube-sorter/sorter/classifier.py`
- Create: `youtube-sorter/tests/test_classifier.py`

- [ ] **Step 1: Write failing tests**

```python
# youtube-sorter/tests/test_classifier.py
import json
from unittest.mock import patch, MagicMock
from sorter.classifier import classify_videos, VideoMetadata


def make_video(vid: str, title: str, desc: str = "", tags: list[str] | None = None):
    return VideoMetadata(video_id=vid, title=title, description=desc, tags=tags or [])


CATEGORIES = ["Claude & AI", "Science", "Other"]


def fake_anthropic_response(content_text: str):
    """Build a mock Anthropic API response."""
    msg = MagicMock()
    block = MagicMock()
    block.text = content_text
    msg.content = [block]
    msg.stop_reason = "end_turn"
    return msg


@patch("sorter.classifier.anthropic.Anthropic")
def test_classify_single_video(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = fake_anthropic_response(
        json.dumps([{"video_id": "v1", "category": "Science", "confidence": 0.92}])
    )

    videos = [make_video("v1", "Quantum Computing Explained")]
    results = classify_videos(videos, CATEGORIES, api_key="test-key")

    assert len(results) == 1
    assert results["v1"].category == "Science"
    assert results["v1"].confidence == 0.92


@patch("sorter.classifier.anthropic.Anthropic")
def test_classify_batch(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = fake_anthropic_response(
        json.dumps([
            {"video_id": "v1", "category": "Claude & AI", "confidence": 0.95},
            {"video_id": "v2", "category": "Science", "confidence": 0.88},
        ])
    )

    videos = [
        make_video("v1", "Claude 4 Release Notes"),
        make_video("v2", "CRISPR Gene Editing"),
    ]
    results = classify_videos(videos, CATEGORIES, api_key="test-key")

    assert len(results) == 2
    assert results["v1"].category == "Claude & AI"
    assert results["v2"].category == "Science"


@patch("sorter.classifier.anthropic.Anthropic")
def test_low_confidence_falls_back_to_other(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = fake_anthropic_response(
        json.dumps([{"video_id": "v1", "category": "Science", "confidence": 0.3}])
    )

    videos = [make_video("v1", "Random vlog about nothing")]
    results = classify_videos(videos, CATEGORIES, api_key="test-key")

    assert results["v1"].category == "Other"


@patch("sorter.classifier.anthropic.Anthropic")
def test_invalid_category_falls_back_to_other(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = fake_anthropic_response(
        json.dumps([{"video_id": "v1", "category": "Cooking", "confidence": 0.9}])
    )

    videos = [make_video("v1", "Gordon Ramsay recipe")]
    results = classify_videos(videos, CATEGORIES, api_key="test-key")

    assert results["v1"].category == "Other"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd youtube-sorter && python -m pytest tests/test_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sorter.classifier'`

- [ ] **Step 3: Implement classifier.py**

```python
# youtube-sorter/sorter/classifier.py
"""Video classification using Anthropic API."""

import json
import logging
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)

BATCH_SIZE = 15
CONFIDENCE_THRESHOLD = 0.5
MODEL = "claude-sonnet-4-6-20250514"


@dataclass
class VideoMetadata:
    video_id: str
    title: str
    description: str = ""
    tags: list[str] | None = None


@dataclass
class Classification:
    category: str
    confidence: float


def _build_system_prompt(categories: list[str]) -> str:
    cat_list = "\n".join(f"- {c}" for c in categories)
    return f"""You are a video classifier. Classify each video into exactly one of these categories:

{cat_list}

Respond with a JSON array. Each element must have:
- "video_id": the video ID provided
- "category": one of the exact category names above
- "confidence": a float from 0.0 to 1.0

If you are unsure, use a low confidence score. Only output valid JSON, no other text."""


def _build_user_prompt(videos: list[VideoMetadata]) -> str:
    items = []
    for v in videos:
        entry = f"Video ID: {v.video_id}\nTitle: {v.title}"
        if v.description:
            # Truncate long descriptions
            desc = v.description[:500]
            entry += f"\nDescription: {desc}"
        if v.tags:
            entry += f"\nTags: {', '.join(v.tags[:20])}"
        items.append(entry)
    return "\n\n---\n\n".join(items)


def _parse_response(text: str, categories: list[str],
                    videos: list[VideoMetadata]) -> dict[str, Classification]:
    """Parse the AI response, falling back to 'Other' for invalid entries."""
    valid_categories = set(categories)
    # Ensure 'Other' is always valid
    if "Other" not in valid_categories:
        valid_categories.add("Other")

    results = {}
    try:
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse classifier response as JSON: %s", text[:200])
        # Fall back: assign all to Other
        for v in videos:
            results[v.video_id] = Classification(category="Other", confidence=0.0)
        return results

    parsed = {item["video_id"]: item for item in data if "video_id" in item}
    for v in videos:
        item = parsed.get(v.video_id)
        if not item:
            results[v.video_id] = Classification(category="Other", confidence=0.0)
            continue

        category = item.get("category", "Other")
        confidence = float(item.get("confidence", 0.0))

        if category not in valid_categories or confidence < CONFIDENCE_THRESHOLD:
            category = "Other"

        results[v.video_id] = Classification(category=category, confidence=confidence)

    return results


def classify_videos(videos: list[VideoMetadata], categories: list[str],
                    api_key: str, model: str = MODEL) -> dict[str, Classification]:
    """Classify videos into categories. Batches automatically."""
    if not videos:
        return {}

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _build_system_prompt(categories)
    all_results: dict[str, Classification] = {}

    for i in range(0, len(videos), BATCH_SIZE):
        batch = videos[i:i + BATCH_SIZE]
        user_prompt = _build_user_prompt(batch)

        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text
            batch_results = _parse_response(text, categories, batch)
            all_results.update(batch_results)
        except Exception as e:
            logger.error("Classification API call failed: %s", e)
            # Fall back to one-at-a-time for this batch
            for v in batch:
                try:
                    single_prompt = _build_user_prompt([v])
                    resp = client.messages.create(
                        model=model,
                        max_tokens=256,
                        system=system_prompt,
                        messages=[{"role": "user", "content": single_prompt}],
                    )
                    single_results = _parse_response(resp.content[0].text, categories, [v])
                    all_results.update(single_results)
                except Exception as e2:
                    logger.error("Single classification failed for %s: %s", v.video_id, e2)
                    all_results[v.video_id] = Classification(category="Other", confidence=0.0)

    return all_results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd youtube-sorter && python -m pytest tests/test_classifier.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add youtube-sorter/sorter/classifier.py youtube-sorter/tests/test_classifier.py
git commit -m "feat(youtube-sorter): add AI classifier with batching"
```

---

### Task 6: Orchestrator (TDD)

**Files:**
- Create: `youtube-sorter/sorter/main.py`
- Create: `youtube-sorter/tests/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
# youtube-sorter/tests/test_main.py
import json
from unittest.mock import patch, MagicMock, call
from sorter.main import run_sort
from sorter.config import Config
from sorter.database import Database
from sorter.youtube import PlaylistVideo
from sorter.classifier import Classification


def make_config(**overrides):
    defaults = dict(
        youtube_cookies="/tmp/cookies.txt",
        playlist_ids=["PL1"],
        anthropic_api_key="test-key",
        categories=["Claude & AI", "Science", "Other"],
        schedule_cron="0 */6 * * *",
        date_sort_field="date_published",
        date_sort_order="desc",
        watch_threshold=90,
        create_sublists=False,
        db_path=":memory:",
    )
    defaults.update(overrides)
    return Config(**defaults)


def make_playlist_video(vid: str, title: str, pos: int, date_pub: str = "2025-01-01"):
    return PlaylistVideo(
        video_id=vid, title=title, description="", tags=[],
        date_published=date_pub, date_added="", position=pos,
        playlist_title="Test Playlist",
    )


@patch("sorter.main.get_playlist_videos")
@patch("sorter.main.InnertubeClient")
@patch("sorter.main.classify_videos")
def test_new_videos_get_classified(mock_classify, mock_innertube_class, mock_get_playlist):
    config = make_config()
    db = Database(":memory:")
    mock_innertube = MagicMock()
    mock_innertube_class.return_value = mock_innertube
    mock_innertube.get_watch_progress.return_value = {"v1": 10, "v2": 5}

    mock_get_playlist.return_value = [
        make_playlist_video("v1", "AI Video", 1),
        make_playlist_video("v2", "Science Video", 2),
    ]
    mock_classify.return_value = {
        "v1": Classification("Claude & AI", 0.95),
        "v2": Classification("Science", 0.88),
    }

    stats = run_sort(config, db)

    assert stats["videos_classified"] == 2
    assert mock_classify.called
    # Verify DB has the classifications
    assert db.get_video("v1", "PL1")["category"] == "Claude & AI"
    assert db.get_video("v2", "PL1")["category"] == "Science"


@patch("sorter.main.get_playlist_videos")
@patch("sorter.main.InnertubeClient")
@patch("sorter.main.classify_videos")
def test_already_classified_videos_skip_ai(mock_classify, mock_innertube_class, mock_get_playlist):
    config = make_config()
    db = Database(":memory:")
    # Pre-populate DB
    db.upsert_video("v1", "PL1", "AI Video", "", "[]", "Claude & AI", 0.95, "2025-01-01", "")

    mock_innertube = MagicMock()
    mock_innertube_class.return_value = mock_innertube
    mock_innertube.get_watch_progress.return_value = {"v1": 10, "v2": 5}

    mock_get_playlist.return_value = [
        make_playlist_video("v1", "AI Video", 1),
        make_playlist_video("v2", "Science Video", 2),
    ]
    mock_classify.return_value = {
        "v2": Classification("Science", 0.88),
    }

    stats = run_sort(config, db)

    # Only v2 should have been sent to classifier
    assert stats["videos_classified"] == 1
    classify_call_videos = mock_classify.call_args[0][0]
    assert len(classify_call_videos) == 1
    assert classify_call_videos[0].video_id == "v2"


@patch("sorter.main.get_playlist_videos")
@patch("sorter.main.InnertubeClient")
@patch("sorter.main.classify_videos")
def test_watched_videos_get_removed(mock_classify, mock_innertube_class, mock_get_playlist):
    config = make_config()
    db = Database(":memory:")
    db.upsert_video("v1", "PL1", "Watched Video", "", "[]", "Science", 0.9, "", "")

    mock_innertube = MagicMock()
    mock_innertube_class.return_value = mock_innertube
    # v1 is 95% watched — above the 90% threshold
    mock_innertube.get_watch_progress.return_value = {"v1": 95, "v2": 10}
    mock_innertube.remove_from_playlist.return_value = True

    mock_get_playlist.return_value = [
        make_playlist_video("v1", "Watched Video", 1),
        make_playlist_video("v2", "Unwatched Video", 2),
    ]
    mock_classify.return_value = {
        "v2": Classification("Science", 0.88),
    }

    stats = run_sort(config, db)

    assert stats["videos_removed"] == 1
    mock_innertube.remove_from_playlist.assert_called()
    # v1 should be marked removed in DB
    assert db.get_video("v1", "_removed") is not None


@patch("sorter.main.get_playlist_videos")
@patch("sorter.main.InnertubeClient")
@patch("sorter.main.classify_videos")
def test_playlist_gets_reordered(mock_classify, mock_innertube_class, mock_get_playlist):
    """Videos should be sorted by category priority then date."""
    config = make_config(date_sort_order="desc")
    db = Database(":memory:")

    mock_innertube = MagicMock()
    mock_innertube_class.return_value = mock_innertube
    mock_innertube.get_watch_progress.return_value = {"v1": 0, "v2": 0, "v3": 0}
    mock_innertube.reorder_playlist.return_value = True

    mock_get_playlist.return_value = [
        # Currently ordered: Science, Other, Claude & AI
        make_playlist_video("v1", "Science", 1, "2025-03-01"),
        make_playlist_video("v2", "Other", 2, "2025-02-01"),
        make_playlist_video("v3", "AI", 3, "2025-01-01"),
    ]
    mock_classify.return_value = {
        "v1": Classification("Science", 0.9),
        "v2": Classification("Other", 0.8),
        "v3": Classification("Claude & AI", 0.95),
    }

    stats = run_sort(config, db)

    # Desired order: Claude & AI (v3) → Science (v1) → Other (v2)
    assert stats["videos_reordered"] > 0
    mock_innertube.reorder_playlist.assert_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd youtube-sorter && python -m pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sorter.main'`

- [ ] **Step 3: Implement main.py**

```python
# youtube-sorter/sorter/main.py
"""Orchestrator: scheduling, run logic, and app entry point."""

import argparse
import json
import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from sorter.config import Config, load_config
from sorter.database import Database
from sorter.youtube import get_playlist_videos, PlaylistVideo
from sorter.innertube import InnertubeClient
from sorter.classifier import classify_videos, VideoMetadata, Classification

logger = logging.getLogger(__name__)
_run_lock = threading.Lock()


def _compute_desired_order(
    videos: list[PlaylistVideo],
    classifications: dict[str, str],  # video_id -> category
    categories: list[str],
    date_sort_field: str,
    date_sort_order: str,
) -> list[str]:
    """Compute the desired video order. Returns list of video_ids."""
    cat_priority = {cat: i for i, cat in enumerate(categories)}
    # Videos not in any known category go last
    max_priority = len(categories)

    reverse_date = date_sort_order == "desc"

    def sort_key(v: PlaylistVideo):
        cat = classifications.get(v.video_id, "Other")
        priority = cat_priority.get(cat, max_priority)
        date = v.date_published if date_sort_field == "date_published" else v.date_added
        return (priority, date if not reverse_date else "")

    # For descending date, we need to reverse within each category group
    # Sort by category priority ascending, then date descending
    def sort_key_full(v: PlaylistVideo):
        cat = classifications.get(v.video_id, "Other")
        priority = cat_priority.get(cat, max_priority)
        date = v.date_published if date_sort_field == "date_published" else v.date_added
        # Negate by inverting string for descending (works for ISO dates)
        return (priority, date)

    sorted_videos = sorted(videos, key=sort_key_full,
                           reverse=False)  # priority ascending

    # Within each category group, sort by date
    from itertools import groupby
    result = []
    for _, group in groupby(sorted_videos,
                            key=lambda v: cat_priority.get(
                                classifications.get(v.video_id, "Other"),
                                max_priority)):
        group_list = list(group)
        group_list.sort(
            key=lambda v: (v.date_published if date_sort_field == "date_published"
                           else v.date_added),
            reverse=reverse_date,
        )
        result.extend(group_list)

    return [v.video_id for v in result]


def run_sort(config: Config, db: Database) -> dict:
    """Execute one full sort run. Returns stats dict."""
    stats = {
        "playlists_processed": 0,
        "videos_classified": 0,
        "videos_removed": 0,
        "videos_reordered": 0,
        "errors": [],
    }

    innertube = InnertubeClient(config.youtube_cookies)

    # Step 1: Fetch all playlists
    all_playlist_videos: dict[str, list[PlaylistVideo]] = {}
    for pl_id in config.playlist_ids:
        try:
            videos = get_playlist_videos(pl_id, config.youtube_cookies)
            all_playlist_videos[pl_id] = videos
            logger.info("Fetched %d videos from playlist %s", len(videos), pl_id)
        except Exception as e:
            logger.error("Failed to fetch playlist %s: %s", pl_id, e)
            stats["errors"].append(f"Fetch failed for {pl_id}: {e}")

    # Step 2: Check watch progress across all videos
    all_video_ids = set()
    for videos in all_playlist_videos.values():
        all_video_ids.update(v.video_id for v in videos)

    watch_progress = innertube.get_watch_progress(list(all_video_ids))

    # Step 3: Remove watched videos from all playlists
    watched_ids = {
        vid for vid, pct in watch_progress.items()
        if pct >= 0 and pct >= config.watch_threshold
    }

    for vid in watched_ids:
        for pl_id, videos in all_playlist_videos.items():
            matching = [v for v in videos if v.video_id == vid]
            for v in matching:
                innertube.remove_from_playlist(pl_id, vid)
                stats["videos_removed"] += 1
        db.mark_removed(vid)

    # Step 4: Process each playlist
    for pl_id, videos in all_playlist_videos.items():
        try:
            # Filter out watched videos
            remaining = [v for v in videos if v.video_id not in watched_ids]

            # Find unclassified videos
            classified_ids = db.get_classified_video_ids(pl_id)
            unclassified = []
            for v in remaining:
                if v.video_id not in classified_ids:
                    # Check if classified in another playlist or _removed
                    existing = db.get_any_classification(v.video_id)
                    if existing:
                        # Reuse existing classification
                        db.upsert_video(
                            v.video_id, pl_id, v.title, v.description,
                            json.dumps(v.tags), existing["category"],
                            existing["confidence"], v.date_published, v.date_added,
                        )
                    else:
                        unclassified.append(v)

            # Classify new videos
            if unclassified:
                to_classify = [
                    VideoMetadata(
                        video_id=v.video_id, title=v.title,
                        description=v.description, tags=v.tags,
                    )
                    for v in unclassified
                ]
                results = classify_videos(to_classify, config.categories,
                                          api_key=config.anthropic_api_key)

                for v in unclassified:
                    cls = results.get(v.video_id, Classification("Other", 0.0))
                    db.upsert_video(
                        v.video_id, pl_id, v.title, v.description,
                        json.dumps(v.tags), cls.category, cls.confidence,
                        v.date_published, v.date_added,
                    )
                stats["videos_classified"] += len(unclassified)

            # Compute desired order
            classifications = {}
            for v in remaining:
                row = db.get_video(v.video_id, pl_id)
                if row:
                    classifications[v.video_id] = row["category"]

            desired_order = _compute_desired_order(
                remaining, classifications, config.categories,
                config.date_sort_field, config.date_sort_order,
            )
            current_order = [v.video_id for v in remaining]

            if desired_order != current_order:
                innertube.reorder_playlist(pl_id, desired_order)
                stats["videos_reordered"] += len(desired_order)

            # Handle sublists
            if config.create_sublists and remaining:
                _update_sublists(config, db, innertube, pl_id, remaining,
                                 classifications, videos[0].playlist_title if videos else pl_id)

            stats["playlists_processed"] += 1

        except Exception as e:
            logger.error("Failed to process playlist %s: %s", pl_id, e)
            stats["errors"].append(f"Process failed for {pl_id}: {e}")

    return stats


def _update_sublists(config: Config, db: Database, innertube: InnertubeClient,
                     playlist_id: str, videos: list[PlaylistVideo],
                     classifications: dict[str, str], playlist_title: str):
    """Create/update sublists for each category."""
    from itertools import groupby

    # Group videos by category
    by_category: dict[str, list[PlaylistVideo]] = {}
    for v in videos:
        cat = classifications.get(v.video_id, "Other")
        by_category.setdefault(cat, []).append(v)

    for cat, cat_videos in by_category.items():
        sublist_title = f"{playlist_title} - {cat}"

        # Look up existing sublist or create new one
        sublist_id = db.get_sublist_id(playlist_id, cat)
        if not sublist_id:
            sublist_id = innertube.create_playlist(sublist_title)
            if not sublist_id:
                logger.error("Could not create sublist '%s'", sublist_title)
                continue
            db.save_sublist(playlist_id, cat, sublist_id, sublist_title)

        # Clear existing items, then repopulate in correct order
        existing = get_playlist_videos(sublist_id, config.youtube_cookies)
        if existing:
            for v in existing:
                innertube.remove_from_playlist(sublist_id, v.video_id)

        for v in cat_videos:
            innertube.add_to_playlist(sublist_id, v.video_id)


def trigger_run(config: Config, db: Database):
    """Thread-safe run trigger."""
    if not _run_lock.acquire(blocking=False):
        logger.warning("Run already in progress, skipping")
        return
    try:
        run_id = db.log_run_start()
        try:
            stats = run_sort(config, db)
            status = "success" if not stats["errors"] else "partial"
            db.log_run_end(
                run_id,
                playlists_processed=stats["playlists_processed"],
                videos_classified=stats["videos_classified"],
                videos_removed=stats["videos_removed"],
                videos_reordered=stats["videos_reordered"],
                errors=stats["errors"] or None,
                status=status,
            )
        except Exception as e:
            logger.exception("Run failed: %s", e)
            db.log_run_end(run_id, errors=[str(e)], status="error")
    finally:
        _run_lock.release()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--options", default="/data/options.json")
    parser.add_argument("--db", default="/data/youtube_sorter.db")
    args = parser.parse_args()

    config = load_config(args.options, args.db)
    db = Database(config.db_path)

    # Import web app here to avoid circular imports
    from sorter.web import create_app
    app = create_app(config, db)

    # Set up scheduler
    scheduler = BackgroundScheduler()
    cron_parts = config.schedule_cron.split()
    if len(cron_parts) == 5:
        trigger = CronTrigger(
            minute=cron_parts[0], hour=cron_parts[1],
            day=cron_parts[2], month=cron_parts[3],
            day_of_week=cron_parts[4],
        )
        scheduler.add_job(trigger_run, trigger, args=[config, db])
        scheduler.start()
        logger.info("Scheduler started with cron: %s", config.schedule_cron)

    # Store trigger function on app for the /api/trigger endpoint
    app.config["trigger_fn"] = lambda: trigger_run(config, db)

    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd youtube-sorter && python -m pytest tests/test_main.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add youtube-sorter/sorter/main.py youtube-sorter/tests/test_main.py
git commit -m "feat(youtube-sorter): add orchestrator with scheduling"
```

---

### Task 7: Web UI

**Files:**
- Create: `youtube-sorter/sorter/web.py`
- Create: `youtube-sorter/static/index.html`
- Create: `youtube-sorter/tests/test_web.py`

- [ ] **Step 1: Write failing tests**

```python
# youtube-sorter/tests/test_web.py
import json
from sorter.web import create_app
from sorter.config import Config
from sorter.database import Database


def make_test_app():
    config = Config(db_path=":memory:")
    db = Database(":memory:")
    app = create_app(config, db)
    app.config["trigger_fn"] = lambda: None
    app.config["TESTING"] = True
    return app, db


def test_index_serves_html():
    app, _ = make_test_app()
    with app.test_client() as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"YouTube Sorter" in resp.data


def test_api_videos_returns_json():
    app, db = make_test_app()
    db.upsert_video("v1", "PL1", "Test", "", "[]", "Science", 0.9, "", "")
    with app.test_client() as client:
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["videos"]) == 1
        assert data["videos"][0]["video_id"] == "v1"


def test_api_runs_returns_json():
    app, db = make_test_app()
    run_id = db.log_run_start()
    db.log_run_end(run_id, status="success")
    with app.test_client() as client:
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["runs"]) == 1


def test_api_trigger_returns_accepted():
    app, _ = make_test_app()
    with app.test_client() as client:
        resp = client.post("/api/trigger")
        assert resp.status_code == 202
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd youtube-sorter && python -m pytest tests/test_web.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sorter.web'`

- [ ] **Step 3: Implement web.py**

```python
# youtube-sorter/sorter/web.py
"""Flask web UI — read-only database view and trigger endpoint."""

import os
import threading

from flask import Flask, jsonify, send_from_directory

from sorter.config import Config
from sorter.database import Database


def create_app(config: Config, db: Database) -> Flask:
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    app = Flask(__name__, static_folder=static_dir)

    @app.route("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.route("/api/videos")
    def api_videos():
        videos = db.get_all_videos()
        return jsonify({"videos": videos})

    @app.route("/api/runs")
    def api_runs():
        runs = db.get_recent_runs()
        return jsonify({"runs": runs})

    @app.route("/api/trigger", methods=["POST"])
    def api_trigger():
        trigger_fn = app.config.get("trigger_fn")
        if trigger_fn:
            threading.Thread(target=trigger_fn, daemon=True).start()
        return jsonify({"status": "accepted"}), 202

    return app
```

- [ ] **Step 4: Create static/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YouTube Sorter</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #282a36; color: #f8f8f2;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    font-size: 14px; padding: 20px;
  }
  h1 { color: #bd93f9; margin-bottom: 16px; }
  h2 { color: #ff79c6; margin: 24px 0 12px; font-size: 16px; }
  .controls { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }
  select, button, input {
    background: #44475a; color: #f8f8f2; border: 1px solid #6272a4;
    padding: 6px 12px; border-radius: 4px; font-size: 13px;
  }
  button { cursor: pointer; background: #6272a4; }
  button:hover { background: #bd93f9; color: #282a36; }
  input { min-width: 200px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th { background: #44475a; color: #bd93f9; text-align: left; padding: 8px 10px;
       position: sticky; top: 0; font-size: 12px; text-transform: uppercase; }
  td { padding: 6px 10px; border-bottom: 1px solid #44475a; }
  tr:hover { background: #44475a; }
  tr.removed { opacity: 0.5; text-decoration: line-through; }
  a { color: #8be9fd; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .cat { display: inline-block; padding: 2px 8px; border-radius: 3px;
         font-size: 12px; background: #6272a4; }
  .status-success { color: #50fa7b; }
  .status-error { color: #ff5555; }
  .status-partial { color: #ffb86c; }
  .status-running { color: #f1fa8c; }
  #msg { color: #50fa7b; margin-left: 12px; font-size: 13px; }
</style>
</head>
<body>
<h1>YouTube Sorter</h1>

<div class="controls">
  <select id="filterPlaylist"><option value="">All playlists</option></select>
  <select id="filterCategory"><option value="">All categories</option></select>
  <input id="filterSearch" type="text" placeholder="Search titles...">
  <button id="btnRun">Run Now</button>
  <span id="msg"></span>
</div>

<table>
<thead>
  <tr>
    <th>Title</th><th>Category</th><th>Playlist</th>
    <th>Published</th><th>Added</th><th>Classified</th>
  </tr>
</thead>
<tbody id="videoBody"></tbody>
</table>

<h2>Recent Runs</h2>
<table>
<thead>
  <tr>
    <th>Started</th><th>Finished</th><th>Playlists</th>
    <th>Classified</th><th>Removed</th><th>Reordered</th><th>Status</th>
  </tr>
</thead>
<tbody id="runBody"></tbody>
</table>

<script>
let allVideos = [];

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

function fmtDate(s) {
  if (!s) return '';
  return s.replace('T', ' ').slice(0, 16);
}

function renderVideos() {
  const pl = document.getElementById('filterPlaylist').value;
  const cat = document.getElementById('filterCategory').value;
  const q = document.getElementById('filterSearch').value.toLowerCase();
  const filtered = allVideos.filter(v =>
    (!pl || v.playlist_id === pl) &&
    (!cat || v.category === cat) &&
    (!q || (v.title || '').toLowerCase().includes(q))
  );
  document.getElementById('videoBody').innerHTML = filtered.map(v => {
    const cls = v.removed_at ? ' class="removed"' : '';
    const url = `https://www.youtube.com/watch?v=${esc(v.video_id)}`;
    return `<tr${cls}>
      <td><a href="${url}" target="_blank">${esc(v.title)}</a></td>
      <td><span class="cat">${esc(v.category)}</span></td>
      <td>${esc(v.playlist_id)}</td>
      <td>${fmtDate(v.date_published)}</td>
      <td>${fmtDate(v.date_added)}</td>
      <td>${fmtDate(v.classified_at)}</td>
    </tr>`;
  }).join('');
}

async function loadVideos() {
  const resp = await fetch('/api/videos');
  const data = await resp.json();
  allVideos = data.videos;

  const playlists = [...new Set(allVideos.map(v => v.playlist_id))].sort();
  const categories = [...new Set(allVideos.map(v => v.category))].sort();
  const plSel = document.getElementById('filterPlaylist');
  playlists.forEach(p => { const o = document.createElement('option'); o.value = p; o.textContent = p; plSel.appendChild(o); });
  const catSel = document.getElementById('filterCategory');
  categories.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; catSel.appendChild(o); });

  renderVideos();
}

async function loadRuns() {
  const resp = await fetch('/api/runs');
  const data = await resp.json();
  document.getElementById('runBody').innerHTML = data.runs.map(r =>
    `<tr>
      <td>${fmtDate(r.started_at)}</td>
      <td>${fmtDate(r.finished_at)}</td>
      <td>${r.playlists_processed ?? ''}</td>
      <td>${r.videos_classified ?? ''}</td>
      <td>${r.videos_removed ?? ''}</td>
      <td>${r.videos_reordered ?? ''}</td>
      <td><span class="status-${r.status}">${r.status}</span></td>
    </tr>`
  ).join('');
}

document.getElementById('filterPlaylist').addEventListener('change', renderVideos);
document.getElementById('filterCategory').addEventListener('change', renderVideos);
document.getElementById('filterSearch').addEventListener('input', renderVideos);
document.getElementById('btnRun').addEventListener('click', async () => {
  const msg = document.getElementById('msg');
  msg.textContent = 'Starting...';
  await fetch('/api/trigger', { method: 'POST' });
  msg.textContent = 'Run triggered!';
  setTimeout(() => { msg.textContent = ''; }, 3000);
});

loadVideos();
loadRuns();
</script>
</body>
</html>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd youtube-sorter && python -m pytest tests/test_web.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add youtube-sorter/sorter/web.py youtube-sorter/static/index.html youtube-sorter/tests/test_web.py
git commit -m "feat(youtube-sorter): add web UI with Dracula theme"
```

---

### Task 8: CI/CD Workflow

**Files:**
- Create: `.github/workflows/deploy-youtube-sorter.yml`

- [ ] **Step 1: Create the workflow**

```yaml
# .github/workflows/deploy-youtube-sorter.yml
name: Deploy YouTube Sorter Add-on

on:
  push:
    branches: [master]
    paths:
      - 'youtube-sorter/**'
  workflow_dispatch:
    inputs:
      force_deploy:
        description: 'Force deploy via SCP + rebuild'
        required: false
        type: boolean
        default: false

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0

      - name: Bump addon version
        run: |
          cd youtube-sorter
          current=$(grep '^version:' config.yaml | sed 's/version: *"\(.*\)"/\1/')
          IFS='.' read -r major minor patch <<< "$current"
          new_version="${major}.${minor}.$((patch + 1))"
          sed -i "s/^version: \"${current}\"/version: \"${new_version}\"/" config.yaml
          echo "VERSION=${new_version}" >> "$GITHUB_ENV"
          echo "PREV_VERSION=${current}" >> "$GITHUB_ENV"
          echo "Bumped version: ${current} → ${new_version}"

      - name: Generate changelog
        run: |
          PREV_COMMIT=$(git log --oneline --grep="Bump HAOS addon version to ${PREV_VERSION}" --format="%H" -1)
          if [ -n "$PREV_COMMIT" ]; then
            CHANGES=$(git log --oneline "${PREV_COMMIT}..HEAD" --no-decorate \
              | grep -v "\[skip ci\]" \
              | sed 's/^[a-f0-9]* /- /')
          else
            CHANGES=$(git log --oneline -10 --no-decorate \
              | grep -v "\[skip ci\]" \
              | sed 's/^[a-f0-9]* /- /')
          fi
          CHANGELOG="youtube-sorter/CHANGELOG.md"
          NEW_ENTRY="## ${VERSION}"$'\n'"${CHANGES}"
          if [ -f "$CHANGELOG" ]; then
            echo -e "${NEW_ENTRY}\n\n$(cat "$CHANGELOG")" > "$CHANGELOG"
          else
            echo "$NEW_ENTRY" > "$CHANGELOG"
          fi

      - name: Commit version bump and changelog
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add youtube-sorter/config.yaml youtube-sorter/CHANGELOG.md
          git commit -m "Bump HAOS addon version to ${VERSION} [skip ci]"
          git pull --rebase
          git push

      - name: Set up SSH
        if: github.event_name == 'workflow_dispatch' && inputs.force_deploy
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.HA_SSH_KEY }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          ssh-keyscan -p ${{ secrets.HA_SSH_PORT }} ${{ secrets.HA_SSH_HOST }} >> ~/.ssh/known_hosts 2>/dev/null

      - name: Force deploy to Home Assistant via SCP
        if: github.event_name == 'workflow_dispatch' && inputs.force_deploy
        run: |
          SSH_CMD="ssh -i ~/.ssh/deploy_key -p ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new"
          TARGET="${{ secrets.HA_SSH_USER }}@${{ secrets.HA_SSH_HOST }}"
          REMOTE_DIR="/addons/youtube-sorter"
          $SSH_CMD "$TARGET" "mkdir -p ${REMOTE_DIR}/sorter ${REMOTE_DIR}/static"
          scp -r -i ~/.ssh/deploy_key -P ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new \
            youtube-sorter/config.yaml \
            youtube-sorter/Dockerfile \
            youtube-sorter/run.sh \
            youtube-sorter/requirements.txt \
            youtube-sorter/CHANGELOG.md \
            "${TARGET}:${REMOTE_DIR}/"
          scp -r -i ~/.ssh/deploy_key -P ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new \
            youtube-sorter/sorter/ "${TARGET}:${REMOTE_DIR}/"
          scp -r -i ~/.ssh/deploy_key -P ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new \
            youtube-sorter/static/ "${TARGET}:${REMOTE_DIR}/"
          echo "Deployed version ${VERSION} to ${TARGET}:${REMOTE_DIR}"

      - name: Rebuild and restart add-on
        if: github.event_name == 'workflow_dispatch' && inputs.force_deploy
        run: |
          SSH_CMD="ssh -i ~/.ssh/deploy_key -p ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new"
          TARGET="${{ secrets.HA_SSH_USER }}@${{ secrets.HA_SSH_HOST }}"
          $SSH_CMD "$TARGET" "ha apps rebuild local_youtube-sorter"
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy-youtube-sorter.yml
git commit -m "ci(youtube-sorter): add deploy workflow"
```

---

### Task 9: Integration Testing & Validation

**Files:**
- All files from previous tasks

- [ ] **Step 1: Run the full test suite**

```bash
cd youtube-sorter && pip install -r requirements.txt pytest && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 2: Verify Docker build**

```bash
cd youtube-sorter && docker build -t youtube-sorter-test .
```

Expected: Build completes without errors.

- [ ] **Step 3: Smoke test the web UI locally**

```bash
cd youtube-sorter && python -c "
from sorter.config import Config
from sorter.database import Database
from sorter.web import create_app

db = Database('/tmp/test_yt_sorter.db')
db.upsert_video('dQw4w9WgXcQ', 'PL_test', 'Never Gonna Give You Up', 'Rick Astley', '[\"music\"]', 'Other', 0.9, '2009-10-25', '2025-01-01')
db.upsert_video('abc123', 'PL_test', 'Claude 4 Deep Dive', 'Exploring Claude', '[\"ai\"]', 'Claude & AI', 0.95, '2025-06-01', '2025-06-02')

config = Config(db_path='/tmp/test_yt_sorter.db')
app = create_app(config, db)
app.config['trigger_fn'] = lambda: None
print('Starting test server on http://localhost:5000')
app.run(port=5000, debug=False)
"
```

Open `http://localhost:5000` and verify:
- Dracula theme renders correctly
- Table shows 2 test videos
- Filters work
- "Run Now" button responds

- [ ] **Step 4: Validate innertube research findings**

Using a real cookies file, test the innertube client against a sacrificial playlist:

```bash
cd youtube-sorter && python -c "
from sorter.innertube import InnertubeClient
client = InnertubeClient('/path/to/cookies.txt')
# Test auth
progress = client.get_watch_progress(['dQw4w9WgXcQ'])
print('Watch progress:', progress)
"
```

Document any needed adjustments to endpoint paths or request shapes in `innertube.py`.

- [ ] **Step 5: Final commit with any fixes**

```bash
git add -A youtube-sorter/
git commit -m "fix(youtube-sorter): integration test fixes"
```
