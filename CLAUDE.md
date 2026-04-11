# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Home Assistant custom add-on repository (`repository.json` at root) containing five add-ons:

1. **autoanalyst/** — Telegram userbot that monitors a private chat for tweet links, fetches content, sends it to Claude for critical analysis, and posts back. Uses Telethon (MTProto).
2. **claudecode-ea/** — Telegram bot bridging to Claude Code via Agent SDK. Wraps [Claudegram](https://github.com/NachoSEO/claudegram) as an HA add-on.
3. **paperless-gpt/** — HA add-on wrapping [icereed/paperless-gpt](https://github.com/icereed/paperless-gpt). AI-powered document organizer for Paperless-ngx (titles, tags, correspondents, dates via LLM vision OCR).
4. **atomic/** — HA add-on wrapping [kenforthewin/atomic](https://github.com/kenforthewin/atomic). Personal knowledge base with linked data, real-time collaboration, MCP endpoint for AI tools, and OAuth auth. Uses pre-built upstream Docker images.
5. **atomic-ingest/** — Cron-based Python add-on that ingests data from multiple sources (Readwise, Raindrop, Evernote) into Atomic via its REST API.

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
├── paperless-gpt/               # Paperless-ngx AI organizer add-on
│   ├── config.yaml              # HA add-on manifest (aarch64+amd64)
│   ├── Dockerfile               # Wraps icereed/paperless-gpt:latest
│   ├── run.sh                   # options.json → env vars, waits for paperless-ngx
│   └── CHANGELOG.md
├── atomic/                      # Personal knowledge base add-on
│   ├── config.yaml              # HA add-on manifest (aarch64)
│   ├── Dockerfile               # COPY --from upstream ghcr.io image
│   ├── run.sh                   # reads options.json, starts atomic-server + nginx
│   └── CHANGELOG.md
├── atomic-ingest/               # Atomic data ingestion add-on
│   ├── config.yaml              # HA add-on manifest (aarch64)
│   ├── Dockerfile               # python:3.12-slim + cron
│   ├── run.sh                   # env setup, crontab gen, exec crond
│   ├── requirements.txt
│   ├── lib/                     # Shared modules
│   │   ├── atomic_client.py
│   │   ├── sync_state.py
│   │   └── folder_consumer.py
│   ├── adapters/                # Source-specific ingestion scripts
│   │   ├── readwise.py
│   │   ├── raindrop.py
│   │   └── evernote.py
│   ├── tests/
│   └── .env.example
└── .github/workflows/
    ├── deploy-autoanalyst.yml   # CI/CD for autoanalyst
    ├── deploy-claudecode-ea.yml # CI/CD for claudecode-ea
    ├── deploy-paperless-gpt.yml # CI/CD for paperless-gpt
    └── deploy-atomic.yml        # CI/CD for atomic
```

## CI/CD

Each add-on has a separate deploy workflow triggered by pushes to `master` with path filters. All workflows:
- Auto-bump patch version in `config.yaml`
- Generate changelog from git log since last version bump
- Commit with `[skip ci]` to avoid loops

`deploy-claudecode-ea.yml` also supports `workflow_dispatch` with a `force_deploy` option that SCPs files to the HA host and runs `ha apps rebuild`.

`deploy-atomic.yml` and `deploy-atomic-ingest.yml` follow the same pattern: push-triggered, path-filtered, auto version bump + changelog.

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

---

## paperless-gpt

### Architecture

Thin HA add-on wrapper around `icereed/paperless-gpt:latest`. Dockerfile adds bash/jq/curl, copies `run.sh` which converts HA `options.json` keys to `UPPER_SNAKE_CASE` env vars, waits for paperless-ngx to be reachable, then execs the upstream binary.

### Anthropic Vision API Limits

Two hard limits when sending page images via base64:
1. **5MB on the base64-encoded string** (5,242,880 bytes) — base64 has 4/3 overhead, so max raw JPEG ≈ 3.75MB
2. **8000 pixels max per dimension** — upstream default is 10,000

### Upstream Resize Bug ([icereed/paperless-gpt#946](https://github.com/icereed/paperless-gpt/pull/946))

The image compression pipeline's resize fallback re-encodes at `jpeg.DefaultQuality` (75) instead of the last quality from the reduction loop (60), inflating output ~1.36× above `IMAGE_MAX_FILE_BYTES`. Current config works around this with conservative limits:

```yaml
image_max_pixel_dimension: 7680   # under 8000px Anthropic limit
image_max_file_bytes: 2500000     # 2.5MB × 1.36 bug inflate = 3.4MB → base64 4.5MB < 5MB
```

**When #946 merges:** raise `image_max_file_bytes` to ~3,800,000. Keep `image_max_pixel_dimension: 7680`.

---

## atomic

### Architecture

Thin HA add-on wrapper around `ghcr.io/kenforthewin/atomic:latest`. Dockerfile uses `COPY --from` to extract the pre-built `atomic-server` binary, React frontend, and nginx config from the upstream all-in-one image. No Rust compilation.

Two processes in one container:
- `atomic-server` on `127.0.0.1:8080` (API, WebSocket, MCP, OAuth)
- `nginx` on `0.0.0.0:8081` (static frontend, reverse proxy, SPA fallback)

`run.sh` starts atomic-server in background, waits for health check, then execs nginx. No supervisord — HA Supervisor restarts the container if the health check fails.

### Access

Caddy (separate HA add-on or host service) reverse-proxies to port 8081 for TLS and internet access. No HA ingress. Atomic runs at `/` with no base-path handling needed.

Caddyfile (Caddy runs in its own container, so use the atomic container hostname, not localhost):
```
atomic.example.com {
    reverse_proxy 23930cf1-atomic:8081
}
```

### Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `public_url` | `""` | External URL for OAuth/MCP discovery (e.g., `https://atomic.example.com`) |
| `rust_log` | `warn` | Log verbosity: trace, debug, info, warn, error |

### Data

All data persists in `/data/` (HA-managed volume):
- `atomic.db` — main SQLite database
- Additional databases as created

### Integration

`atomic-ingest` (companion add-on) accesses Atomic's API on the internal HA Docker network. API tokens created manually via Atomic's web UI.

---

## atomic-ingest

### Architecture

Cron-based Python add-on that ingests data from multiple sources into Atomic via its REST API. Single container with `crond` as PID 1, spawning adapter scripts on schedule.

### Commands

```bash
# Run tests locally
cd atomic-ingest && pip install -r requirements.txt && pip install pytest
python -m pytest tests/ -v
```

### Configuration

Three HA UI options: `atomic_api_url`, `atomic_api_token`, `log_level`. All source-specific credentials and schedule overrides in `.env` at `/addon_configs/atomic-ingest/` (mounted as `/config/` inside container).

### Key Files

| File | Purpose |
|------|---------|
| `config.yaml` | HA add-on manifest |
| `Dockerfile` | python:3.12-slim + cron |
| `run.sh` | Entrypoint — env setup, crontab gen, exec crond |
| `lib/atomic_client.py` | Atomic REST API client |
| `lib/sync_state.py` | Per-adapter JSON state in /data/ |
| `lib/folder_consumer.py` | Consume/processed folder pattern |
| `adapters/readwise.py` | Readwise Highlights + Reader |
| `adapters/raindrop.py` | Raindrop.io bookmarks via ingest_url |
| `adapters/evernote.py` | ENEX file import via bulk create |

### Adapters

**Readwise** (hourly): Highlights v2 export (one atom per book) + Reader v3 list (ingest_url + highlight enrichment). Auth: `READWISE_API_TOKEN`.

**Raindrop** (hourly): Bookmarks via `ingest_url` for URLs, `create_atom` for uploaded files. Notes/highlights appended via update. Auth: `RAINDROP_TOKEN`.

**Evernote** (daily): Scans `/share/atomic-ingest/evernote/consume/` for `.enex` files, parses to Markdown, bulk creates, moves to `processed/`.

### Adding a new adapter

1. Create `adapters/<name>.py` with a `main()` that reads env vars, imports from `lib/`, and syncs
2. Add credential env var to `.env.example`
3. Add `<NAME>_SCHEDULE` to `run.sh` crontab generation with a default
4. Add the env var export to `run.sh`'s env dump
