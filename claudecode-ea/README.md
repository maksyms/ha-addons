# Claude Code EA

A Home Assistant add-on that runs [Claudegram](https://github.com/NachoSEO/claudegram) — a Telegram bot bridging to Claude Code via the Agent SDK. Gives you an AI-powered executive assistant accessible through Telegram.

## How It Works

Claudegram is cloned from upstream at Docker build time, so each rebuild picks up the latest version automatically. The add-on installs the Claude Code CLI globally (required by the Agent SDK) and runs the Claudegram Node.js process.

## Configuration

Configure via the **Configuration** tab in the HA UI, or place a `.env` file in `/share/claudecode-ea/`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from [@BotFather](https://t.me/BotFather) |
| `ALLOWED_USER_IDS` | Yes | — | Comma-separated Telegram user IDs |
| `ANTHROPIC_API_KEY` | No | — | From https://console.anthropic.com (omit for Claude Max) |
| `DANGEROUS_MODE` | No | `false` | Allow Claude to execute arbitrary commands |
| `STREAMING_MODE` | No | `streaming` | `streaming` (live-updating) or `wait` (send when complete) |
| `BOT_NAME` | No | `Claudegram` | Custom name for the bot |

## First Run

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and note the token
2. Get your Telegram user ID (e.g. via [@userinfobot](https://t.me/userinfobot))
3. Set `TELEGRAM_BOT_TOKEN`, `ALLOWED_USER_IDS`, and `ANTHROPIC_API_KEY` in the add-on config
4. Start the add-on and message your bot

## Env File Staging

Place a `.env` file in `/share/claudecode-ea/` on the HA host. On first start, the add-on copies it to persistent storage. This is useful when migrating or setting up from a file rather than the UI.
