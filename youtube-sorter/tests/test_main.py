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
    assert db.get_video("v1", "PL1")["category"] == "Claude & AI"
    assert db.get_video("v2", "PL1")["category"] == "Science"


@patch("sorter.main.get_playlist_videos")
@patch("sorter.main.InnertubeClient")
@patch("sorter.main.classify_videos")
def test_already_classified_videos_skip_ai(mock_classify, mock_innertube_class, mock_get_playlist):
    config = make_config()
    db = Database(":memory:")
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

    # Desired order: Claude & AI (v3) -> Science (v1) -> Other (v2)
    assert stats["videos_reordered"] > 0
    mock_innertube.reorder_playlist.assert_called()
