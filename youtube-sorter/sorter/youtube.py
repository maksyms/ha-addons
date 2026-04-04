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
