# Rebuild Plan: Telegram Tweet Auto-Analyst

A step-by-step plan for recreating this utility from scratch using Claude Code.

## Overview

A single-file Telegram "userbot" that monitors a private 1-2-1 chat for tweet links, fetches the tweet, optionally transcribes video, sends everything to an LLM for critical analysis, and posts the result back. Uses Telethon (MTProto Client API) because the Telegram Bot API cannot access private 1-2-1 chats.

## Prerequisites

- Python 3.11+
- Telegram API credentials from https://my.telegram.org
- Anthropic API key from https://console.anthropic.com
- (Optional) X API Bearer Token (Basic tier)
- (Optional) OpenAI API key for Whisper video transcription
- (Optional) Perplexity API key as an alternative analysis backend

---

## Step 1: Project scaffolding

Create the project directory with:

- `requirements.txt` with dependencies: `telethon>=1.36`, `anthropic>=0.39`, `tweepy>=4.14`, `python-dotenv>=1.0`, `httpx>=0.27`
- `.env.example` with all configuration variables (see Configuration section below)
- `.gitignore` ignoring `.env`, `.venv/`, `__pycache__/`, `*.session`
- `CLAUDE.md` describing the project for Claude Code (architecture, commands, constraints)
- `autoanalyst.py` as the single implementation file

Prompt:

> Create a Python project scaffolding for a Telegram userbot called "autoanalyst". Create requirements.txt with telethon>=1.36, anthropic>=0.39, tweepy>=4.14, python-dotenv>=1.0, httpx>=0.27. Create .env.example with variables: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PEER_ID, ANTHROPIC_API_KEY, X_BEARER_TOKEN (optional), CLAUDE_MODEL (default claude-sonnet-4-20250514), ANALYZE_OWN (default false), ANALYSIS_BACKEND (default claude), PERPLEXITY_API_KEY, PERPLEXITY_MODEL (default sonar-pro), OPENAI_API_KEY (optional). Create a .gitignore for Python, including .env and *.session files. Create an empty autoanalyst.py.

## Step 2: Configuration loading and logging setup

In `autoanalyst.py`, set up:

- Imports: `argparse`, `asyncio`, `collections`, `html`, `logging`, `os`, `re`, `signal`, `sys`, `anthropic`, `httpx`, `dotenv`, `telethon`
- `load_dotenv()` call
- `logging.basicConfig` at INFO level with `%(asctime)s [%(levelname)s] %(message)s` format
- Module logger: `log = logging.getLogger(__name__)`
- All config read from env vars with sensible defaults
- `ANALYZE_OWN` parsed as boolean from string

Prompt:

> In autoanalyst.py, add imports for argparse, asyncio, collections, html, logging, os, re, signal, sys, anthropic, httpx, dotenv (load_dotenv), and telethon (TelegramClient, events). Call load_dotenv(). Set up logging.basicConfig at INFO level with format "%(asctime)s [%(levelname)s] %(message)s" and a module logger. Read all config from environment: TELEGRAM_API_ID (int), TELEGRAM_API_HASH (str), TELEGRAM_PEER_ID (int), ANTHROPIC_API_KEY, X_BEARER_TOKEN, CLAUDE_MODEL (default "claude-sonnet-4-20250514"), ANALYZE_OWN (boolean from string, default false), ANALYSIS_BACKEND (default "claude", lowercased), PERPLEXITY_API_KEY, PERPLEXITY_MODEL (default "sonar-pro"), OPENAI_API_KEY.

## Step 3: Tweet URL regex and dedup cache

Add:

- `TWEET_URL_RE` regex matching `https?://` followed by optional `www.` or `mobile.` prefix, then `twitter.com` or `x.com`, then `/<handle>/status/<id>`. Two capture groups: handle and tweet ID.
- In-memory LRU dedup using `collections.OrderedDict`, capped at 100 entries
- `_mark_seen(tweet_id)` function that returns True if already seen, otherwise marks as seen

Prompt:

> Add a TWEET_URL_RE regex that matches tweet URLs from twitter.com and x.com (including www. and mobile. subdomains), capturing the handle and tweet ID. Pattern: `r"https?://(?:(?:www\.|mobile\.)?(?:twitter\.com|x\.com))/(\w+)/status/(\d+)"`. Add an LRU dedup cache using OrderedDict capped at 100 entries, and a _mark_seen(tweet_id) function that returns True if already processed.

## Step 4: Tweet fetching — X API (primary)

Implement `fetch_tweet_xapi(tweet_id)`:

- Async function returning `dict | None`
- Early return `None` if `X_BEARER_TOKEN` is not set
- Use tweepy.Client (imported lazily inside a helper `_tweepy_client()`) to call `get_tweet` with fields: `author_id`, `created_at`, `public_metrics`, `text`; expansions: `author_id`; user_fields: `name`, `username`
- Return dict with keys: `text`, `author_name`, `author_handle`, `likes`, `retweets`, `replies`, `created_at`
- Catch all exceptions, log with `log.exception`, return None
- Add `log.info` calls for attempt and success

Prompt:

> Add an async function fetch_tweet_xapi(tweet_id) that fetches a tweet via X API v2 using tweepy. Create a _tweepy_client() helper that lazily imports tweepy and returns tweepy.Client(bearer_token=X_BEARER_TOKEN). The function should return None if X_BEARER_TOKEN is empty. Otherwise call client.get_tweet with tweet_fields=["author_id", "created_at", "public_metrics", "text"], expansions=["author_id"], user_fields=["name", "username"]. Return a dict with text, author_name, author_handle, likes, retweets, replies, created_at. Log the attempt and success with log.info including tweet_id. Catch all exceptions with log.exception, return None.

## Step 5: Tweet fetching — fxtwitter (fallback)

Implement `fetch_tweet_fxtwitter(tweet_id)`:

- Async function returning `dict | None`
- GET `https://api.fxtwitter.com/i/status/{tweet_id}` via `httpx.AsyncClient(timeout=15)`
- Parse response JSON, extract tweet, author, media/videos
- Return dict with same keys as xapi plus `community_note` and `video_url`
- Log attempt and success (including video presence)
- Catch all exceptions, log, return None

Prompt:

> Add an async function fetch_tweet_fxtwitter(tweet_id) that fetches a tweet via the fxtwitter API. GET https://api.fxtwitter.com/i/status/{tweet_id} using httpx.AsyncClient(timeout=15). Parse the JSON response to extract tweet text, author info, likes/retweets/replies, created_at, community_note, and video_url (from media.videos[0].url if present). Return a dict with these fields. Log attempt and success. Catch all exceptions, log.exception, return None.

## Step 6: Tweet fetching — dispatcher

Implement `fetch_tweet(tweet_id)`:

- Try `fetch_tweet_xapi` first
- If it returns a result, return it
- Log fallback, try `fetch_tweet_fxtwitter`
- If both fail, `log.warning` and return None

Prompt:

> Add an async function fetch_tweet(tweet_id) that tries fetch_tweet_xapi first, returns its result if not None. Otherwise log.info a fallback message and try fetch_tweet_fxtwitter. If that also returns None, log.warning that all methods failed. Return the result.

## Step 7: Video transcription — Whisper API caller

Implement `_call_whisper_api(video_data: bytes)`:

- POST to `https://api.openai.com/v1/audio/transcriptions` with Bearer token
- Send as multipart: file=("video.mp4", video_data, "video/mp4"), model="whisper-1"
- 300s timeout
- Retry once on 429 (wait 30s)
- Return `resp.json().get("text")` on success, None on failure
- Log byte count on attempt, success on return

Prompt:

> Add an async function _call_whisper_api(video_data: bytes) that sends video bytes to the OpenAI Whisper API at https://api.openai.com/v1/audio/transcriptions. Use httpx.AsyncClient(timeout=300). Post with Authorization Bearer header, multipart file upload as ("video.mp4", video_data, "video/mp4"), model="whisper-1". Retry once on HTTP 429 after 30s sleep. Log the byte count on attempt and success. Return the transcript text or None on any failure.

## Step 8: Video transcription — download and orchestrate

Implement `transcribe_video(tweet: dict)`:

- Mutates `tweet` dict in place (adds `video_transcript` or `video_note`)
- Early return if no `video_url` (debug log)
- Early return if no `OPENAI_API_KEY` (info log, set video_note)
- Download video via `httpx.AsyncClient(timeout=60)` streaming GET
- Size limit: `_VIDEO_MAX_BYTES = 25 * 1024 * 1024` — check both Content-Length header and accumulated bytes during download
- Log "too large" and set video_note if over limit
- Call `_call_whisper_api` with downloaded bytes
- Set `video_transcript` on success, `video_note` on empty/failed transcript

Prompt:

> Add _VIDEO_MAX_BYTES = 25 * 1024 * 1024. Add an async function transcribe_video(tweet: dict) that mutates the tweet dict in place. If no video_url key, log.debug and return. If no OPENAI_API_KEY, log.info "not configured", set tweet["video_note"] and return. Download the video via httpx streaming GET (timeout=60), checking Content-Length header and accumulated bytes against the 25MB limit (log.info and set video_note if too large). On download success, call _call_whisper_api. If transcript is non-empty, set tweet["video_transcript"]; otherwise log.info empty transcript and set tweet["video_note"].

## Step 9: Analysis — system prompt and tweet formatter

Add:

- `SYSTEM_PROMPT` constant: instructs the model to identify claims, flag misleading content, note rhetorical techniques, consider missing context, incorporate community notes and video transcripts. Rules: 3-6 sentences, no moralizing, no quoting the tweet, say "straightforward" if no issues.
- `_format_tweet_for_analysis(tweet: dict)` helper that assembles author, date, tweet text, community note, video transcript/note, and engagement stats into a plain text string.

Prompt:

> Add a SYSTEM_PROMPT string that instructs a critical-thinking analyst to: identify claims, flag misleading/false claims, note rhetorical techniques, consider missing context, incorporate community notes and video transcripts. Rules: 3-6 sentences, no moralizing, no quoting tweet text, say so briefly if straightforward. Add a _format_tweet_for_analysis(tweet) helper that builds a plain-text string with author, date, tweet text, community note (if present), video transcript or video note (if present), and engagement stats.

## Step 10: Analysis — Claude backend

Implement `analyze_tweet_claude(tweet: dict)`:

- Create `anthropic.AsyncAnthropic` client
- Call `messages.create` with `CLAUDE_MODEL`, max_tokens=512, system prompt, user content from formatter
- Retry once on `RateLimitError` after 60s sleep
- Return analysis text on success, error string on failure
- Log success with character count

Prompt:

> Add an async function analyze_tweet_claude(tweet) that creates an anthropic.AsyncAnthropic client, calls messages.create with the CLAUDE_MODEL, max_tokens=512, SYSTEM_PROMPT as system, and formatted tweet as user message. Retry once on anthropic.RateLimitError after 60s. Log.info success with char count. Return the text, or an error string starting with "⚠ Analysis unavailable:" on failure.

## Step 11: Analysis — Perplexity backend

Implement `analyze_tweet_perplexity(tweet: dict)`:

- POST to `https://api.perplexity.ai/chat/completions` via httpx
- Headers: Authorization Bearer, Content-Type application/json
- Body: model=PERPLEXITY_MODEL, messages (system + user), max_tokens=512
- Retry once on 429 after 60s
- Return `choices[0].message.content`
- Log success with character count

Prompt:

> Add an async function analyze_tweet_perplexity(tweet) that POSTs to https://api.perplexity.ai/chat/completions via httpx.AsyncClient(timeout=60). Use Bearer auth with PERPLEXITY_API_KEY. Send model=PERPLEXITY_MODEL, system and user messages, max_tokens=512. On 429 raise HTTPStatusError, retry once after 60s. Log.info success with char count. Return the content text, or error string on failure.

## Step 12: Analysis — dispatcher

Implement `analyze_tweet(tweet: dict)`:

- Log which backend is being used
- Dispatch to `analyze_tweet_perplexity` if `ANALYSIS_BACKEND == "perplexity"`, otherwise `analyze_tweet_claude`

Prompt:

> Add an async function analyze_tweet(tweet) that logs the ANALYSIS_BACKEND being used, then dispatches to analyze_tweet_perplexity if backend is "perplexity", otherwise analyze_tweet_claude.

## Step 13: Response formatting

Implement `format_response(tweet: dict, analysis: str)`:

- Build HTML-formatted string for Telegram using `html.escape` on all user content
- Structure: bold "Tweet Analysis" header, author line, italicized quoted tweet text, video transcript/note indicator, bold "Analysis:" with escaped analysis text, engagement stats
- Truncate to 4096 chars (Telegram limit) — cut at 4090 and append `\n…`
- Debug log if truncation happens

Prompt:

> Add a format_response(tweet, analysis) function that builds an HTML string for Telegram. Use html.escape on all user content. Structure: "<b>Tweet Analysis</b>", author line, italicized quoted tweet text, video transcript indicator or video note if present, "<b>Analysis:</b>" with escaped analysis, engagement stats. If the result exceeds 4096 chars, log.debug and truncate to 4090 chars plus "\n…".

## Step 14: Telegram client, event handler, and main loop

Implement:

- `build_client()` returning `TelegramClient("autoanalyst", TELEGRAM_API_ID, TELEGRAM_API_HASH)`
- `list_chats()` async helper that connects, iterates dialogs, prints ID/Type/Name table
- `run()` async main loop:
  - Start client, log identity
  - Register `@client.on(events.NewMessage(...))` handler for `TELEGRAM_PEER_ID`, with `incoming=None if ANALYZE_OWN else True`
  - Handler: find all tweet URL matches, skip seen IDs, fetch tweet, transcribe video, analyze, format, respond with `parse_mode="html"`
  - Graceful shutdown via `asyncio.Event` + SIGINT/SIGTERM handlers
- `main()` entry point:
  - argparse with `--list-chats` flag
  - Validate required env vars based on backend choice
  - Run with `asyncio.run()`

Prompt:

> Add build_client() returning TelegramClient("autoanalyst", TELEGRAM_API_ID, TELEGRAM_API_HASH). Add async list_chats() that connects, iterates dialogs, prints a table of ID/Type/Name. Add async run() as the main loop: start client, log login info, register a NewMessage handler for TELEGRAM_PEER_ID (incoming=None if ANALYZE_OWN else True). The handler finds all TWEET_URL_RE matches, skips seen tweet IDs via _mark_seen, then for each new tweet: fetch_tweet, transcribe_video, analyze_tweet, format_response, event.respond with parse_mode="html", log completion. Add graceful shutdown via asyncio.Event with SIGINT/SIGTERM signal handlers. Add main() with argparse (--list-chats flag), validation of required env vars (TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PEER_ID, plus ANTHROPIC_API_KEY if backend is claude, or PERPLEXITY_API_KEY if backend is perplexity), and asyncio.run(run()). Add if __name__ == "__main__": main().

## Step 15: Create CLAUDE.md

Write the `CLAUDE.md` file documenting the project for future Claude Code sessions.

Prompt:

> Create a CLAUDE.md with: a description of the project (Telegram userbot monitoring a 1-2-1 chat for tweet links, fetches content, sends to Claude for analysis, posts back), setup and run commands, architecture description (single-file, pipeline flow, two-tier fetching), key constraints (HTML parse mode, html.escape, 4096 char limit, incoming-only messages, OrderedDict dedup, rate limit retry), and configuration notes.

---

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_API_ID` | Yes | — | From https://my.telegram.org |
| `TELEGRAM_API_HASH` | Yes | — | From https://my.telegram.org |
| `TELEGRAM_PEER_ID` | Yes | — | Other user's ID (use `--list-chats`) |
| `ANTHROPIC_API_KEY` | If claude backend | — | From https://console.anthropic.com |
| `X_BEARER_TOKEN` | No | — | X API v2; falls back to fxtwitter |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Model ID for analysis |
| `ANALYZE_OWN` | No | `false` | Also analyze own tweet links |
| `ANALYSIS_BACKEND` | No | `claude` | `claude` or `perplexity` |
| `PERPLEXITY_API_KEY` | If perplexity backend | — | Perplexity API key |
| `PERPLEXITY_MODEL` | No | `sonar-pro` | Perplexity model ID |
| `OPENAI_API_KEY` | No | — | For Whisper video transcription |

## Key Design Constraints

These must be preserved in any rebuild:

1. **HTML parse mode** — Telegram responses use HTML, not Markdown. All user content must go through `html.escape()`.
2. **4096 char limit** — Telegram messages are truncated at 4096 characters.
3. **Incoming-only filtering** — Only messages from `TELEGRAM_PEER_ID` are processed (unless `ANALYZE_OWN` is set).
4. **In-memory dedup** — `OrderedDict` with 100-entry cap prevents re-analyzing the same tweet.
5. **Graceful degradation** — Missing `X_BEARER_TOKEN` falls back to fxtwitter. Missing `OPENAI_API_KEY` skips transcription. Rate limits retry once then fail gracefully.
6. **Single file** — The entire implementation lives in `autoanalyst.py`.
