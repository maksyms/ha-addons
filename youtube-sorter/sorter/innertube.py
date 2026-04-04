"""Innertube API client for YouTube playlist mutations and watch progress.

This module provides a client for YouTube's internal innertube API, used for
operations that the official API doesn't support well or requires OAuth2.

Based on yt-dlp's reverse engineering work, particularly the SAPISID auth
mechanism from yt_dlp/extractor/youtube/_base.py.

WARNING: The innertube API is undocumented and may change without notice.
Endpoint paths and request/response shapes are based on observation and may
need updates as YouTube's internal API evolves.
"""

import hashlib
import http.cookiejar
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Innertube API base URL
INNERTUBE_API_URL = "https://www.youtube.com/youtubei/v1"

# Client info - matches yt-dlp's 'web' client
# See: yt-dlp/yt_dlp/extractor/youtube/_base.py INNERTUBE_CLIENTS['web']
INNERTUBE_CLIENT = {
    "clientName": "WEB",
    "clientVersion": "2.20260114.08.00",
}


class InnertubeClient:
    """Client for YouTube's internal innertube API.

    Handles authentication via SAPISID cookies (same as used by browser)
    and provides methods for playlist mutations and watch progress queries.
    """

    def __init__(self, cookies_path: str):
        """Initialize the innertube client.

        Args:
            cookies_path: Path to Netscape-format cookies file
        """
        self.cookies_path = cookies_path
        self._cookies: dict[str, str] = {}
        self._load_cookies()

    def _load_cookies(self) -> None:
        """Load Netscape-format cookies file into a dict.

        Raises:
            FileNotFoundError: If cookies file doesn't exist
            http.cookiejar.LoadError: If cookies file is malformed
        """
        try:
            jar = http.cookiejar.MozillaCookieJar(self.cookies_path)
            jar.load(ignore_discard=True, ignore_expires=True)
            self._cookies = {c.name: c.value for c in jar}
            logger.debug(f"Loaded {len(self._cookies)} cookies from {self.cookies_path}")
        except FileNotFoundError:
            logger.error(f"Cookies file not found: {self.cookies_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            raise

    def _sapisidhash(self) -> str | None:
        """Generate SAPISIDHASH authorization header from cookies.

        Based on yt-dlp's _make_sid_authorization() and _get_sid_cookies().
        See: yt-dlp/yt_dlp/extractor/youtube/_base.py lines 708-722, 728-742

        Returns:
            Authorization header value like "SAPISIDHASH 1234567890_abc123..."
            or None if no SAPISID cookie found
        """
        # Try SAPISID first, fallback to __Secure-3PAPISID
        # This matches yt-dlp's logic which notes:
        # "Sometimes SAPISID cookie isn't present but __Secure-3PAPISID is.
        #  YouTube also falls back to __Secure-3PAPISID if SAPISID is missing."
        sapisid = self._cookies.get("SAPISID") or self._cookies.get("__Secure-3PAPISID")
        if not sapisid:
            logger.warning("No SAPISID or __Secure-3PAPISID cookie found - API calls may fail")
            return None

        # Generate hash: SHA1(timestamp + " " + sapisid + " " + origin)
        timestamp = str(round(time.time()))
        origin = "https://www.youtube.com"
        hash_input = f"{timestamp} {sapisid} {origin}"
        sha1 = hashlib.sha1(hash_input.encode()).hexdigest()

        # Format: "SAPISIDHASH timestamp_hash"
        return f"SAPISIDHASH {timestamp}_{sha1}"

    def _make_headers(self) -> dict[str, str]:
        """Generate headers for innertube API requests.

        Returns:
            Headers dict with Content-Type, X-Origin, auth, etc.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Origin": "https://www.youtube.com",
            "X-Youtube-Client-Name": "1",  # WEB client
            "X-Youtube-Client-Version": INNERTUBE_CLIENT["clientVersion"],
        }

        auth = self._sapisidhash()
        if auth:
            headers["Authorization"] = auth

        return headers

    def _make_cookie_header(self) -> str:
        """Generate Cookie header from loaded cookies.

        Returns:
            Cookie header value like "NAME1=value1; NAME2=value2"
        """
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    def _request(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        """Make an innertube API request.

        Args:
            endpoint: API endpoint path (e.g., "browse", "browse/edit_playlist")
            body: Request body (context will be added automatically)

        Returns:
            Response JSON as dict

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            json.JSONDecodeError: If response is not valid JSON
        """
        # Add context if not present (matches yt-dlp's _call_api)
        body.setdefault("context", {"client": INNERTUBE_CLIENT})

        headers = self._make_headers()
        headers["Cookie"] = self._make_cookie_header()

        url = f"{INNERTUBE_API_URL}/{endpoint}"
        logger.debug(f"POST {url}")

        try:
            response = httpx.post(url, json=body, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code} for {endpoint}: {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"Request failed for {endpoint}: {e}")
            raise

    def get_watch_progress(self, video_ids: list[str]) -> dict[str, float]:
        """Get watch progress for a list of videos.

        NOTE: This endpoint is not well-documented and may be fragile.
        Based on spec mention of "innertube browse endpoint (same internal API
        that renders the red progress bar)". Actual implementation may need
        adjustment based on testing.

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            Dict mapping video_id -> progress percentage (0-100),
            or -1 if progress unknown/unavailable
        """
        # TODO: This is a placeholder. The actual endpoint for watch progress
        # needs to be discovered through browser network inspection or
        # by examining YouTube's web client JavaScript.
        # Possible endpoints: browse (with specific continuation tokens),
        # or a dedicated endpoint for watch history/progress.
        logger.warning("get_watch_progress() not yet fully implemented - returning unknown for all")
        return {vid: -1.0 for vid in video_ids}

    def remove_from_playlist(
        self, playlist_id: str, video_id: str, set_video_id: str | None = None
    ) -> dict[str, Any]:
        """Remove a video from a playlist.

        NOTE: Endpoint path needs validation against actual YouTube behavior.
        Based on spec mention of "playlist/edit action".

        Args:
            playlist_id: YouTube playlist ID
            video_id: YouTube video ID to remove
            set_video_id: Optional setVideoId (playlist-specific video identifier)

        Returns:
            API response dict

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        # Spec mentions "innertube playlist/edit action"
        # Actual endpoint may be "browse/edit_playlist" or similar
        body = {
            "playlistId": playlist_id,
            "actions": [
                {
                    "action": "ACTION_REMOVE_VIDEO_BY_VIDEO_ID",
                    "removedVideoId": video_id,
                }
            ],
        }

        # setVideoId is often needed for playlist operations
        if set_video_id:
            body["actions"][0]["setVideoId"] = set_video_id

        logger.info(f"Removing video {video_id} from playlist {playlist_id}")
        return self._request("browse/edit_playlist", body)

    def add_to_playlist(self, playlist_id: str, video_id: str) -> dict[str, Any]:
        """Add a video to a playlist.

        Args:
            playlist_id: YouTube playlist ID
            video_id: YouTube video ID to add

        Returns:
            API response dict

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        body = {
            "playlistId": playlist_id,
            "actions": [
                {
                    "action": "ACTION_ADD_VIDEO",
                    "addedVideoId": video_id,
                }
            ],
        }

        logger.info(f"Adding video {video_id} to playlist {playlist_id}")
        return self._request("browse/edit_playlist", body)

    def clear_playlist(
        self, playlist_id: str, video_ids_and_set_ids: list[tuple[str, str]]
    ) -> dict[str, Any]:
        """Remove all videos from a playlist (for sublist refresh).

        Args:
            playlist_id: YouTube playlist ID
            video_ids_and_set_ids: List of (video_id, set_video_id) tuples

        Returns:
            API response dict

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        actions = [
            {
                "action": "ACTION_REMOVE_VIDEO_BY_VIDEO_ID",
                "removedVideoId": video_id,
                "setVideoId": set_video_id,
            }
            for video_id, set_video_id in video_ids_and_set_ids
        ]

        body = {
            "playlistId": playlist_id,
            "actions": actions,
        }

        logger.info(f"Clearing {len(actions)} videos from playlist {playlist_id}")
        return self._request("browse/edit_playlist", body)

    def reorder_playlist(
        self, playlist_id: str, ordered_set_video_ids: list[str]
    ) -> dict[str, Any]:
        """Reorder a playlist by moving videos.

        NOTE: This is complex and may require multiple API calls or a different
        approach. YouTube's internal API for reordering is not well-documented.

        Args:
            playlist_id: YouTube playlist ID
            ordered_set_video_ids: List of setVideoIds in desired order

        Returns:
            API response dict

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            NotImplementedError: If reordering proves too complex for initial version
        """
        # Reordering typically requires moving videos one-by-one or in batches
        # using ACTION_MOVE_VIDEO_BEFORE or ACTION_MOVE_VIDEO_AFTER
        # This is a simplified placeholder
        logger.warning("reorder_playlist() not fully implemented - may need iteration")
        raise NotImplementedError(
            "Playlist reordering via innertube not yet implemented. "
            "This requires careful sequencing of MOVE actions."
        )

    def create_playlist(self, title: str, privacy: str = "PRIVATE") -> str:
        """Create a new playlist.

        Args:
            title: Playlist title
            privacy: Privacy setting (PRIVATE, UNLISTED, PUBLIC)

        Returns:
            New playlist ID

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            KeyError: If response doesn't contain expected playlist ID
        """
        body = {
            "title": title,
            "privacyStatus": privacy,
        }

        logger.info(f"Creating playlist: {title} ({privacy})")
        response = self._request("playlist/create", body)

        # Response should contain playlistId - exact path needs validation
        playlist_id = response.get("playlistId")
        if not playlist_id:
            logger.error(f"No playlistId in response: {response}")
            raise KeyError("playlistId not found in create_playlist response")

        logger.info(f"Created playlist {playlist_id}")
        return playlist_id
