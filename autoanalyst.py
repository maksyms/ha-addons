#!/usr/bin/env python3
"""Telegram Tweet Auto-Analyst.

Monitors a Telegram 1-2-1 chat for x.com/twitter.com links,
fetches the tweet, sends it to Claude for critical analysis,
and posts the result back into the chat.
"""

import argparse
import asyncio
import collections
import html
import logging
import os
import re
import signal
import sys

import anthropic
import httpx
from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TELEGRAM_API_ID = int(os.environ.get("TELEGRAM_API_ID") or 0)
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
TELEGRAM_PEER_ID = int(os.environ.get("TELEGRAM_PEER_ID") or 0)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
ANALYZE_OWN = os.environ.get("ANALYZE_OWN", "").lower() in ("1", "true", "yes")
ANALYSIS_BACKEND = os.environ.get("ANALYSIS_BACKEND", "claude").lower()
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL = os.environ.get("PERPLEXITY_MODEL", "sonar-pro")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ---------------------------------------------------------------------------
# Tweet URL regex & dedup cache
# ---------------------------------------------------------------------------

TWEET_URL_RE = re.compile(
    r"https?://(?:(?:www\.|mobile\.)?(?:twitter\.com|x\.com))/(\w+)/status/(\d+)"
)

# LRU-style dedup: remember last 100 tweet IDs we already analysed
_seen_tweets: collections.OrderedDict[str, None] = collections.OrderedDict()
_SEEN_MAX = 100


def _mark_seen(tweet_id: str) -> bool:
    """Return True if already seen, otherwise mark as seen."""
    if tweet_id in _seen_tweets:
        return True
    _seen_tweets[tweet_id] = None
    if len(_seen_tweets) > _SEEN_MAX:
        _seen_tweets.popitem(last=False)
    return False


# ---------------------------------------------------------------------------
# Tweet fetching — primary (X API) and fallback (fxtwitter)
# ---------------------------------------------------------------------------


def _tweepy_client():
    import tweepy

    return tweepy.Client(bearer_token=X_BEARER_TOKEN)


async def fetch_tweet_xapi(tweet_id: str) -> dict | None:
    """Fetch tweet via X API v2 (tweepy). Returns dict or None on failure."""
    if not X_BEARER_TOKEN:
        return None
    log.info("Fetching tweet %s via X API…", tweet_id)
    try:
        client = _tweepy_client()
        resp = client.get_tweet(
            tweet_id,
            tweet_fields=["author_id", "created_at", "public_metrics", "text"],
            expansions=["author_id", "attachments.media_keys"],
            user_fields=["name", "username"],
            media_fields=["type", "variants"],
        )
        if not resp.data:
            return None

        tweet = resp.data
        author = None
        if resp.includes and "users" in resp.includes:
            author = resp.includes["users"][0]

        # Extract best MP4 video URL from media includes
        video_url = None
        if resp.includes and "media" in resp.includes:
            for media in resp.includes["media"]:
                if media.type == "video":
                    mp4s = [
                        v for v in (media.variants or [])
                        if v.get("content_type") == "video/mp4"
                        and v.get("bit_rate", 0) > 0
                    ]
                    if mp4s:
                        video_url = max(mp4s, key=lambda v: v["bit_rate"])["url"]
                    break

        metrics = tweet.public_metrics or {}
        log.info(
            "Fetched tweet %s via X API (by @%s, video=%s)",
            tweet_id, author.username if author else "?", bool(video_url),
        )
        return {
            "text": tweet.text,
            "author_name": author.name if author else "Unknown",
            "author_handle": author.username if author else "unknown",
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0),
            "created_at": str(tweet.created_at) if tweet.created_at else "",
            "video_url": video_url,
        }
    except Exception:
        log.exception("X API fetch failed for tweet %s", tweet_id)
        return None


async def fetch_tweet_fxtwitter(tweet_id: str) -> dict | None:
    """Fetch tweet via fxtwitter API (free, no auth)."""
    log.info("Fetching tweet %s via fxtwitter…", tweet_id)
    url = f"https://api.fxtwitter.com/i/status/{tweet_id}"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AutoAnalyst/1.0)"}
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        tweet = data.get("tweet", {})
        if not tweet:
            return None

        author = tweet.get("author", {})
        media = tweet.get("media", {})
        videos = media.get("videos", [])
        video_url = videos[0].get("url") if videos else None
        log.info("Fetched tweet %s via fxtwitter (by @%s, video=%s)", tweet_id, author.get("screen_name", "?"), bool(video_url))
        return {
            "text": tweet.get("text", ""),
            "author_name": author.get("name", "Unknown"),
            "author_handle": author.get("screen_name", "unknown"),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "created_at": tweet.get("created_at", ""),
            "community_note": tweet.get("community_note"),
            "video_url": video_url,
        }
    except Exception:
        log.exception("fxtwitter fetch failed for tweet %s", tweet_id)
        return None


async def fetch_tweet(tweet_id: str) -> dict | None:
    """Try X API first, fall back to fxtwitter.

    When X API succeeds, a supplementary fxtwitter call fills in
    community_note (not available via X API) and provides a video_url
    fallback if the X API media expansion didn't return one.
    """
    result = await fetch_tweet_xapi(tweet_id)
    if result:
        supplement = await fetch_tweet_fxtwitter(tweet_id)
        if supplement:
            if not result.get("video_url") and supplement.get("video_url"):
                result["video_url"] = supplement["video_url"]
            if supplement.get("community_note"):
                result["community_note"] = supplement["community_note"]
        return result
    log.info("X API unavailable for tweet %s, falling back to fxtwitter", tweet_id)
    result = await fetch_tweet_fxtwitter(tweet_id)
    if result is None:
        log.warning("All fetch methods failed for tweet %s", tweet_id)
    return result


# ---------------------------------------------------------------------------
# Video transcription (OpenAI Whisper)
# ---------------------------------------------------------------------------

_VIDEO_MAX_BYTES = 25 * 1024 * 1024  # 25 MB


async def _call_whisper_api(video_data: bytes) -> str | None:
    """Send video bytes to OpenAI Whisper API. Returns transcript or None."""
    log.info("Sending %d bytes to Whisper API…", len(video_data))
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    files={"file": ("video.mp4", video_data, "video/mp4")},
                    data={"model": "whisper-1"},
                )
                if resp.status_code == 429:
                    if attempt == 0:
                        log.warning("Whisper rate limited, retrying in 30s…")
                        await asyncio.sleep(30)
                        continue
                    log.warning("Whisper rate limited after retry")
                    return None
                resp.raise_for_status()
                text = resp.json().get("text")
                log.info("Whisper API returned transcript")
                return text
        except httpx.HTTPStatusError:
            log.exception("Whisper API HTTP error")
            return None
        except Exception:
            log.exception("Whisper API error")
            return None
    return None


async def transcribe_video(tweet: dict) -> None:
    """Download video and transcribe via Whisper. Mutates tweet dict in place."""
    video_url = tweet.get("video_url")
    if not video_url:
        log.debug("No video URL for tweet, skipping transcription")
        return

    if not OPENAI_API_KEY:
        log.info("Video found but OPENAI_API_KEY not configured, skipping transcription")
        tweet["video_note"] = "Video present but transcription not configured"
        return

    # Download MP4 with size limit
    log.info("Downloading video from %s…", video_url)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("GET", video_url) as resp:
                resp.raise_for_status()
                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > _VIDEO_MAX_BYTES:
                    log.info("Video too large for transcription (>25 MB), skipping")
                    tweet["video_note"] = "Video too large for transcription (>25 MB)"
                    return

                chunks = []
                total = 0
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    total += len(chunk)
                    if total > _VIDEO_MAX_BYTES:
                        log.info("Video too large for transcription (>25 MB), skipping")
                        tweet["video_note"] = "Video too large for transcription (>25 MB)"
                        return
                    chunks.append(chunk)

        video_data = b"".join(chunks)
    except Exception:
        log.exception("Failed to download video from %s", video_url)
        tweet["video_note"] = "Failed to download video for transcription"
        return

    log.info("Transcribing video (%d bytes)…", len(video_data))
    transcript = await _call_whisper_api(video_data)

    if transcript and transcript.strip():
        video_transcript = transcript.strip()
        tweet["video_transcript"] = video_transcript
        log.info("Video transcribed successfully (%d chars)", len(video_transcript))
    else:
        log.info("Video transcription returned empty (no speech detected)")
        tweet["video_note"] = "Video has no speech or transcription failed"


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a critical-thinking analyst. Given a tweet, you will:
- Identify explicit and implicit claims made in the tweet.
- Research these claims using internet for accuracy and validity.
- Flag any misleading, or false claims.
- Note rhetorical techniques used (appeal to emotion, false dichotomy, cherry-picking, etc.).
- Consider important missing context.
- If a community note is attached, incorporate it.
- If a video transcript is provided, analyze claims made in the video alongside the tweet text.
  Note that transcripts may contain errors.

Rules:
- Be concise: 3-5 sentences.
- Do not moralise or editorialize.
- Do not repeat or quote the tweet text.
- If the tweet is straightforward and factual with no issues, say so briefly.
"""


def _format_tweet_for_analysis(tweet: dict) -> str:
    parts = [f"Author: {tweet['author_name']} (@{tweet['author_handle']})"]
    if tweet.get("created_at"):
        parts.append(f"Date: {tweet['created_at']}")
    parts.append(f"\nTweet text:\n{tweet['text']}")
    if tweet.get("community_note"):
        parts.append(f"\nCommunity Note:\n{tweet['community_note']}")
    if tweet.get("video_transcript"):
        parts.append(f"\nVideo transcript:\n{tweet['video_transcript']}")
    elif tweet.get("video_note"):
        parts.append(f"\n[{tweet['video_note']}]")
    parts.append(
        f"\nEngagement: {tweet.get('likes', 0):,} likes | "
        f"{tweet.get('retweets', 0):,} RTs | "
        f"{tweet.get('replies', 0):,} replies"
    )
    return "\n".join(parts)


async def analyze_tweet_claude(tweet: dict) -> str:
    """Send tweet to Claude for critical analysis. Returns analysis text."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    user_content = _format_tweet_for_analysis(tweet)

    for attempt in range(2):
        try:
            message = await client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            text = message.content[0].text
            log.info("Claude analysis received (%d chars)", len(text))
            return text
        except anthropic.RateLimitError as exc:
            if attempt == 0:
                log.warning("Claude rate limited, retrying in 60s…")
                await asyncio.sleep(60)
            else:
                return f"⚠ Analysis unavailable: {exc}"
        except Exception as exc:
            log.exception("Claude API error")
            return f"⚠ Analysis unavailable: {exc}"
    return "⚠ Analysis unavailable."


async def analyze_tweet_perplexity(tweet: dict) -> str:
    """Send tweet to Perplexity for critical analysis. Returns analysis text."""
    user_content = _format_tweet_for_analysis(tweet)

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": PERPLEXITY_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_content},
                        ],
                        "max_tokens": 512,
                    },
                )
                if resp.status_code == 429:
                    raise httpx.HTTPStatusError(
                        "rate limited", request=resp.request, response=resp,
                    )
                resp.raise_for_status()
                data = resp.json()
            text = data["choices"][0]["message"]["content"]
            log.info("Perplexity analysis received (%d chars)", len(text))
            return text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                if attempt == 0:
                    log.warning("Perplexity rate limited, retrying in 60s…")
                    await asyncio.sleep(60)
                    continue
                return f"⚠ Analysis unavailable: {exc}"
            log.exception("Perplexity API error")
            return f"⚠ Analysis unavailable: {exc}"
        except Exception as exc:
            log.exception("Perplexity API error")
            return f"⚠ Analysis unavailable: {exc}"
    return "⚠ Analysis unavailable."


async def analyze_tweet(tweet: dict) -> str:
    """Dispatch tweet analysis to the configured backend."""
    log.info("Submitting tweet to %s for analysis…", ANALYSIS_BACKEND)
    if ANALYSIS_BACKEND == "perplexity":
        return await analyze_tweet_perplexity(tweet)
    return await analyze_tweet_claude(tweet)


# ---------------------------------------------------------------------------
# Response formatting (HTML for Telegram)
# ---------------------------------------------------------------------------


def format_response(tweet: dict, analysis: str) -> str:
    """Build HTML-formatted response for Telegram."""
    e = html.escape
    lines = [
        "<b>Tweet Analysis</b>",
        "",
        f"<b>By:</b> {e(tweet['author_name'])} (@{e(tweet['author_handle'])})",
        "",
        f"<i>\"{e(tweet['text'])}\"</i>",
        "",
    ]
    if tweet.get("video_transcript"):
        lines.append("<b>[Includes video transcript]</b>")
        lines.append("")
    elif tweet.get("video_note"):
        lines.append(f"<i>[{e(tweet['video_note'])}]</i>")
        lines.append("")
    lines += [
        f"<b>Analysis:</b>\n{e(analysis)}",
        "",
        f"<b>Engagement:</b> {tweet.get('likes', 0):,} likes"
        f" | {tweet.get('retweets', 0):,} RTs"
        f" | {tweet.get('replies', 0):,} replies",
    ]
    text = "\n".join(lines)
    # Telegram message limit
    if len(text) > 4096:
        log.debug("Response truncated from %d to 4096 chars", len(text))
        text = text[:4090] + "\n…"
    return text


# ---------------------------------------------------------------------------
# Telegram client & event handler
# ---------------------------------------------------------------------------


def build_client() -> TelegramClient:
    return TelegramClient("autoanalyst", TELEGRAM_API_ID, TELEGRAM_API_HASH)


async def list_chats():
    """Helper mode: list all dialogs with their IDs."""
    client = build_client()
    await client.start()
    print(f"\n{'ID':<16} {'Type':<10} {'Name'}")
    print("-" * 60)
    async for dialog in client.iter_dialogs():
        kind = "Channel" if dialog.is_channel else ("Group" if dialog.is_group else "User")
        print(f"{dialog.entity.id:<16} {kind:<10} {dialog.name}")
    await client.disconnect()


async def run():
    """Main event loop."""
    client = build_client()
    await client.start()

    me = await client.get_me()
    log.info("Logged in as %s (id=%s)", me.first_name, me.id)
    log.info("Monitoring peer %s for tweet links…", TELEGRAM_PEER_ID)

    @client.on(events.NewMessage(
        chats=TELEGRAM_PEER_ID,
        incoming=None if ANALYZE_OWN else True,
    ))
    async def handler(event):
        matches = TWEET_URL_RE.findall(event.raw_text or "")
        if not matches:
            return

        for _handle, tweet_id in matches:
            if _mark_seen(tweet_id):
                log.info("Skipping already-analysed tweet %s", tweet_id)
                continue

            log.info("Processing tweet %s", tweet_id)
            tweet = await fetch_tweet(tweet_id)

            if tweet is None:
                await event.respond("Could not fetch tweet content — it may be deleted or private.")
                continue

            await transcribe_video(tweet)
            analysis = await analyze_tweet(tweet)
            response = format_response(tweet, analysis)
            await event.respond(response, parse_mode="html")
            log.info("Analysis posted for tweet %s", tweet_id)

    # Graceful shutdown on SIGINT / SIGTERM
    stop_event = asyncio.Event()

    def _shutdown(sig, _frame):
        log.info("Received %s, shutting down…", signal.Signals(sig).name)
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    await stop_event.wait()
    await client.disconnect()
    log.info("Disconnected. Bye.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Telegram Tweet Auto-Analyst")
    parser.add_argument(
        "--list-chats",
        action="store_true",
        help="List all Telegram dialogs with their IDs, then exit.",
    )
    args = parser.parse_args()

    if args.list_chats:
        asyncio.run(list_chats())
        return

    # Validate required config
    missing = []
    if not TELEGRAM_API_ID:
        missing.append("TELEGRAM_API_ID")
    if not TELEGRAM_API_HASH:
        missing.append("TELEGRAM_API_HASH")
    if not TELEGRAM_PEER_ID:
        missing.append("TELEGRAM_PEER_ID")
    if ANALYSIS_BACKEND == "claude" and not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if ANALYSIS_BACKEND == "perplexity" and not PERPLEXITY_API_KEY:
        missing.append("PERPLEXITY_API_KEY")
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill in the values.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()
