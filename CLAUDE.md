# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Home Assistant custom add-on repository (`repository.json` at root) containing two add-ons:

1. **autoanalyst/** — Telegram userbot that monitors a private chat for tweet links, fetches content, sends it to Claude for critical analysis, and posts back. Uses Telethon (MTProto).
2. **claudecode-ea/** — Telegram bot bridging to Claude Code via Agent SDK. Wraps [Claudegram](https://github.com/NachoSEO/claudegram) as an HA add-on.

## Repository Structure

```
├── repository.json              # HA add-on repository metadata
├── autoanalyst/                 # Tweet analysis userbot add-on
│   ├── config.yaml
│   ├── Dockerfile
│   ├── run.sh
│   ├── CHANGELOG.md
│   ├── autoanalyst.py           # Main application (~250 lines)
│   ├── requirements.txt
│   └── .env.example
├── claudecode-ea/               # Claude Code Telegram bot add-on
│   ├── config.yaml              # HA add-on manifest (v1.0.2, aarch64+armv7)
│   ├── Dockerfile               # Alpine + Node.js + Claude Code CLI; clones Claudegram at build
│   ├── run.sh                   # Three-tier env: /share/.env → /data/.env → options.json
│   ├── settings.json            # Claude Code default settings (model, effort, etc.)
│   ├── plugins.txt              # Claude Code plugins to install at build time
│   ├── mcp.d/                   # MCP server configs (one JSON per server, envsubst at runtime)
│   │   ├── onedrive.json
│   │   └── requirements.txt     # pip deps for MCP servers
│   ├── templates/
│   │   ├── CLAUDE.md.template
│   │   └── memory.md.template
│   ├── CHANGELOG.md
│   ├── README.md
│   ├── .env.example
│   ├── icon.png
│   └── logo.png
└── .github/workflows/
    ├── deploy-autoanalyst.yml   # CI/CD for autoanalyst
    └── deploy-claudecode-ea.yml # CI/CD for claudecode-ea
```

## CI/CD

Each add-on has a separate deploy workflow triggered by pushes to `master` with path filters. Both workflows:
- Auto-bump patch version in `config.yaml`
- Generate changelog from git log since last version bump
- Commit with `[skip ci]` to avoid loops

`deploy-claudecode-ea.yml` also supports `workflow_dispatch` with a `force_deploy` option that SCPs files to the HA host and runs `ha apps rebuild`.

---

## autoanalyst

### Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r autoanalyst/requirements.txt
cp autoanalyst/.env.example autoanalyst/.env  # then fill in credentials
python autoanalyst/autoanalyst.py --list-chats  # discover peer ID
python autoanalyst/autoanalyst.py               # run the monitor
```

### Architecture

Single-file design (`autoanalyst/autoanalyst.py`). Pipeline:

```
Incoming Telegram message → TWEET_URL_RE match → dedup check → fetch_tweet() → transcribe_video() → analyze_tweet() → format_response() → event.respond()
```

**Tweet fetching is two-tier:** `fetch_tweet_xapi()` (X API v2 via tweepy) first; `fetch_tweet_fxtwitter()` (free, no auth) fallback.

**Key constraints:**
- Telegram messages use HTML parse mode (not Markdown)
- All user-content must go through `html.escape()`
- Telegram message limit is 4096 chars
- Only incoming messages from `TELEGRAM_PEER_ID` are processed
- Dedup cache: in-memory `OrderedDict`, last 100 tweet IDs
- Claude rate limit: one retry after 60s, then graceful failure

### Configuration

All via `.env` (see `autoanalyst/.env.example`). `X_BEARER_TOKEN` optional (fxtwitter fallback). `OPENAI_API_KEY` optional (video transcription skipped without it).

---

## claudecode-ea

### Architecture

Wraps [Claudegram](https://github.com/NachoSEO/claudegram) via a [fork](https://github.com/maksyms/claudegram) — cloned at Docker build time (`git clone --depth 1`), built with `npm ci && npm run build`, then run as `node /app/claudegram/dist/index.js`. The fork includes a fix for session ID not being cleared on project switch ([upstream PR #26](https://github.com/NachoSEO/claudegram/pull/26)); switch back to upstream once merged.

Claude Code CLI is installed globally (`npm install -g @anthropic-ai/claude-code`) — required by the Agent SDK that Claudegram uses.

### Settings (`settings.json`)

Base Claude Code CLI settings COPYed to `/root/.claude/settings.json` at build time. Currently sets `model` and `effortLevel`. Plugin installs add `enabledPlugins` at build time; MCP merge adds `mcpServers` at runtime. All three layers compose via deep-merge.

### Plugins (`plugins.txt`)

Claude Code plugins are installed at Docker build time. `plugins.txt` declares marketplaces and plugins:
```
marketplace kepano/obsidian-skills
install obsidian@obsidian-skills
```
Parsed in Dockerfile via `grep` — `marketplace` lines run `claude plugin marketplace add`, `install` lines run `claude plugin install`.

### MCP Servers (`mcp.d/`)

One JSON file per MCP server. At startup, `run.sh` iterates `mcp.d/*.json`, runs `envsubst` to substitute env vars, skips files with empty values (missing required vars), and deep-merges all into `/root/.claude/settings.json` (preserving `enabledPlugins` from build-time plugin installs). Pip dependencies go in `mcp.d/requirements.txt`.

### Configuration

Six options configurable via HA UI or `/share/claudecode-ea/.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `ALLOWED_USER_IDS` | Yes | — | Comma-separated Telegram user IDs |
| `ANTHROPIC_API_KEY` | No | — | Anthropic API key (omit for Claude Max) |
| `DANGEROUS_MODE` | No | `false` | Allow Claude to execute arbitrary commands |
| `STREAMING_MODE` | No | `streaming` | `streaming` or `wait` |
| `BOT_NAME` | No | `Claudegram` | Custom bot name |

### run.sh Config Priority

1. `/share/claudecode-ea/.env` (always copied to `/data/.env` if present)
2. `/data/.env` (persisted from previous run)
3. Generated from `/data/options.json` (HA UI values)

### Key Details

- `init: false`, `stdin: true` in config.yaml
- Only aarch64 + armv7 (no amd64)
- Claudegram is always latest upstream at build time
