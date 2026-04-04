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
        existing = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = ? AND category IS NOT NULL LIMIT 1",
            (video_id,)
        ).fetchone()

        self.conn.execute(
            "UPDATE videos SET removed_at = ? WHERE video_id = ? AND removed_at IS NULL",
            (now, video_id)
        )

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
