from unittest.mock import patch, MagicMock
from sorter.youtube import get_playlist_videos, PlaylistVideo


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
    assert videos[0].playlist_title == "My Test Playlist"
