# Auto Analyst

A Telegram userbot that monitors a private 1-2-1 chat for x.com / twitter.com links, fetches the tweet content, sends it to an LLM for critical analysis, and posts the result back into the chat.

Uses [Telethon](https://docs.telethon.dev/) (MTProto Client API) because the Telegram Bot API cannot access private 1-2-1 chats.

## Features

- Two-tier tweet fetching: X API v2 (primary) with fxtwitter fallback
- Video transcription via OpenAI Whisper
- Community notes included when available
- Choice of analysis backend: Claude or Perplexity
- In-memory dedup prevents re-analyzing the same tweet
- Graceful degradation when optional API keys are missing

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
```

Discover the peer ID for your target chat:

```bash
python autoanalyst.py --list-chats
```

Run the monitor:

```bash
python autoanalyst.py
```

## Configuration

All config is via `.env` (see `.env.example`).

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_API_ID` | Yes | — | From https://my.telegram.org |
| `TELEGRAM_API_HASH` | Yes | — | From https://my.telegram.org |
| `TELEGRAM_PEER_ID` | Yes | — | Other user's ID (use `--list-chats`) |
| `ANTHROPIC_API_KEY` | If claude backend | — | From https://console.anthropic.com |
| `X_BEARER_TOKEN` | No | — | X API v2; falls back to fxtwitter |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Model ID for analysis |
| `ANALYZE_OWN` | No | `false` | Also analyze your own tweet links |
| `ANALYSIS_BACKEND` | No | `claude` | `claude` or `perplexity` |
| `PERPLEXITY_API_KEY` | If perplexity backend | — | Perplexity API key |
| `PERPLEXITY_MODEL` | No | `sonar-pro` | Perplexity model ID |
| `OPENAI_API_KEY` | No | — | For Whisper video transcription |

## Running on Home Assistant OS

A pre-built add-on scaffold lives in `haos-addon/`. To deploy on a Raspberry Pi 4 (or similar) running HAOS:

1. Copy `haos-addon/`, `autoanalyst.py`, and `requirements.txt` into `/addons/autoanalyst/` on the HA instance (via Samba or SSH add-on). Optionally include your `.env` and/or `autoanalyst.session` to skip UI configuration and Telethon re-auth.

2. In the HA UI: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** — no extra repo needed for local add-ons.

3. Reload, find **Auto Analyst** under **Local add-ons**, and install.

4. If you didn't bundle a `.env`, fill in the API keys and peer ID in the add-on's **Configuration** tab.

5. Start the add-on. If this is the first run without a bundled session file, open the **Log** tab and complete Telethon's interactive auth. Subsequent restarts auto-connect using the persisted session.

## Architecture

Single-file design (`autoanalyst.py`). The pipeline is:

```
Incoming Telegram message
  → TWEET_URL_RE match
  → dedup check
  → fetch_tweet()      (X API → fxtwitter fallback)
  → transcribe_video() (Whisper, if video present)
  → analyze_tweet()    (Claude or Perplexity)
  → format_response()  (HTML for Telegram)
  → event.respond()
```

## License

Private / unlicensed.
