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

TELEGRAM_API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
TELEGRAM_PEER_ID = int(os.environ.get("TELEGRAM_PEER_ID", 0))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

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
    try:
        client = _tweepy_client()
        resp = client.get_tweet(
            tweet_id,
            tweet_fields=["author_id", "created_at", "public_metrics", "text"],
            expansions=["author_id"],
            user_fields=["name", "username"],
        )
        if not resp.data:
            return None

        tweet = resp.data
        author = None
        if resp.includes and "users" in resp.includes:
            author = resp.includes["users"][0]

        metrics = tweet.public_metrics or {}
        return {
            "text": tweet.text,
            "author_name": author.name if author else "Unknown",
            "author_handle": author.username if author else "unknown",
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0),
            "created_at": str(tweet.created_at) if tweet.created_at else "",
        }
    except Exception:
        log.exception("X API fetch failed for tweet %s", tweet_id)
        return None


async def fetch_tweet_fxtwitter(tweet_id: str) -> dict | None:
    """Fetch tweet via fxtwitter API (free, no auth)."""
    url = f"https://api.fxtwitter.com/i/status/{tweet_id}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        tweet = data.get("tweet", {})
        if not tweet:
            return None

        author = tweet.get("author", {})
        return {
            "text": tweet.get("text", ""),
            "author_name": author.get("name", "Unknown"),
            "author_handle": author.get("screen_name", "unknown"),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "created_at": tweet.get("created_at", ""),
            "community_note": tweet.get("community_note"),
        }
    except Exception:
        log.exception("fxtwitter fetch failed for tweet %s", tweet_id)
        return None


async def fetch_tweet(tweet_id: str) -> dict | None:
    """Try X API first, fall back to fxtwitter."""
    result = await fetch_tweet_xapi(tweet_id)
    if result:
        return result
    return await fetch_tweet_fxtwitter(tweet_id)


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a critical-thinking analyst. Given a tweet, you will:
- Identify explicit and implicit claims made in the tweet.
- Flag any unsupported, misleading, or false claims.
- Note rhetorical techniques used (appeal to emotion, false dichotomy, cherry-picking, etc.).
- Consider important missing context.
- If a community note is attached, incorporate it.

Rules:
- Be concise: 3-6 sentences.
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
    parts.append(
        f"\nEngagement: {tweet.get('likes', 0):,} likes | "
        f"{tweet.get('retweets', 0):,} RTs | "
        f"{tweet.get('replies', 0):,} replies"
    )
    return "\n".join(parts)


async def analyze_tweet(tweet: dict) -> str:
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
            return message.content[0].text
        except anthropic.RateLimitError:
            if attempt == 0:
                log.warning("Claude rate limited, retrying in 60s…")
                await asyncio.sleep(60)
            else:
                return "⚠ Analysis unavailable (rate limited). Try again later."
        except Exception:
            log.exception("Claude API error")
            return "⚠ Analysis unavailable due to an API error."
    return "⚠ Analysis unavailable."


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
        f"<b>Analysis:</b>\n{e(analysis)}",
        "",
        f"<b>Engagement:</b> {tweet.get('likes', 0):,} likes"
        f" | {tweet.get('retweets', 0):,} RTs"
        f" | {tweet.get('replies', 0):,} replies",
    ]
    text = "\n".join(lines)
    # Telegram message limit
    if len(text) > 4096:
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

    @client.on(events.NewMessage(chats=TELEGRAM_PEER_ID, incoming=True))
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
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill in the values.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()
