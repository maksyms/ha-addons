# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Telegram "userbot" that monitors a 1-2-1 private chat for x.com/twitter.com links, fetches the tweet content, sends it to Claude for critical analysis, and posts the result back into the chat. Uses Telethon (MTProto Client API) because the Telegram Bot API cannot access private 1-2-1 chats.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in credentials

# Discover Telegram peer ID (interactive auth on first run)
python autoanalyst.py --list-chats

# Run the monitor
python autoanalyst.py

# Test regex standalone
python3 -c "from autoanalyst import TWEET_URL_RE; print(TWEET_URL_RE.findall('https://x.com/user/status/123'))"
```

## Architecture

Single-file design (`autoanalyst.py`, ~250 lines). The pipeline is:

```
Incoming Telegram message → TWEET_URL_RE match → dedup check → fetch_tweet() → transcribe_video() → analyze_tweet() → format_response() → event.respond()
```

**Tweet fetching is two-tier:** `fetch_tweet_xapi()` (X API v2 via tweepy, requires `X_BEARER_TOKEN`) is tried first; `fetch_tweet_fxtwitter()` (free, no auth, via httpx) is the fallback. If both fail, a failure message is sent.

**Key constraints:**
- Telegram messages use HTML parse mode (not Markdown) — special chars in tweets break Markdown
- All user-content in responses must go through `html.escape()`
- Telegram message limit is 4096 chars — responses are truncated
- Only incoming messages from `TELEGRAM_PEER_ID` are processed (not the user's own messages)
- Dedup cache is in-memory `OrderedDict`, last 100 tweet IDs
- Claude rate limit: one retry after 60s, then graceful failure

## Configuration

All config is via `.env` (see `.env.example`). `X_BEARER_TOKEN` is optional — without it, only fxtwitter is used. `OPENAI_API_KEY` is optional — without it, video transcription is skipped and analysis proceeds on tweet text only.
