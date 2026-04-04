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
    v = db.get_video("v1", "_removed")
    assert v["category"] == "Science"


def test_sublists():
    db = make_db()
    assert db.get_sublist_id("PL1", "Science") is None
    db.save_sublist("PL1", "Science", "PL_sub1", "My Playlist - Science")
    assert db.get_sublist_id("PL1", "Science") == "PL_sub1"
    # Update existing
    db.save_sublist("PL1", "Science", "PL_sub2", "My Playlist - Science v2")
    assert db.get_sublist_id("PL1", "Science") == "PL_sub2"
