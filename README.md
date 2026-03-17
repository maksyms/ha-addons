# Maksym's HA Add-ons

A Home Assistant custom add-on repository.

## Installation

1. In Home Assistant: **Settings → Add-ons → Add-on Store → three-dot menu → Repositories**
2. Add this repository URL: `https://github.com/maksyms/ha-addons`
3. Click **Add**, then refresh
4. Find the add-on you want and click **Install**

## Add-ons

### [Auto Analyst](autoanalyst/)

Monitors a Telegram 1-2-1 chat for tweet links, fetches the content, runs it through an LLM for critical analysis, and posts the result back. Uses Telethon (MTProto) to access private chats that the Bot API cannot reach.

- Two-tier tweet fetching (X API v2 + fxtwitter fallback)
- Video transcription via OpenAI Whisper
- Claude or Perplexity analysis backend

### [Claude Code EA](claudecode-ea/)

Telegram bot bridging to Claude Code via the Agent SDK. Wraps [Claudegram](https://github.com/NachoSEO/claudegram) — cloned at build time so each rebuild gets the latest upstream.

- AI-powered executive assistant over Telegram
- Streaming responses
- Optional dangerous mode for arbitrary command execution

## Repository Structure

```
├── repository.json          # HA add-on repository metadata
├── autoanalyst/             # Auto Analyst add-on
│   ├── config.yaml
│   ├── Dockerfile
│   ├── run.sh
│   └── autoanalyst.py
├── claudecode-ea/           # Claude Code EA add-on
│   ├── config.yaml
│   ├── Dockerfile
│   └── run.sh
```

## License

Private / unlicensed.
