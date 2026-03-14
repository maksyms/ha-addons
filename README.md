# Auto Analyst - HA Add-on Repository

A Home Assistant add-on repository containing the Auto Analyst add-on.

## Installation

1. In Home Assistant: **Settings → Add-ons → Add-on Store → three-dot menu → Repositories**
2. Add this repository URL: `https://github.com/maksyms/ha-addons`
3. Click **Add**, then refresh
4. Find **Auto Analyst** in the store and click **Install**

## Auto Analyst

A Telegram userbot that monitors a private 1-2-1 chat for x.com / twitter.com links, fetches the tweet content, sends it to an LLM for critical analysis, and posts the result back into the chat.

Uses [Telethon](https://docs.telethon.dev/) (MTProto Client API) because the Telegram Bot API cannot access private 1-2-1 chats.

### Features

- Two-tier tweet fetching: X API v2 (primary) with fxtwitter fallback
- Video transcription via OpenAI Whisper
- Community notes included when available
- Choice of analysis backend: Claude or Perplexity
- In-memory dedup prevents re-analyzing the same tweet
- Graceful degradation when optional API keys are missing

### Configuration

After installing the add-on, configure it via the **Configuration** tab in the HA UI, or bundle a `.env` file in the add-on directory.

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

### First Run

If this is the first run without a bundled session file, open the add-on's **Log** tab and complete Telethon's interactive auth. Subsequent restarts auto-connect using the persisted session.

### Manual Deploy (Force)

For direct deployment bypassing the add-on store update mechanism, trigger the GitHub Actions workflow manually with `force_deploy: true`. This uses SCP + SSH to deploy files directly to the HA instance.

## Architecture

Single-file design (`autoanalyst/autoanalyst.py`). The pipeline is:

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
