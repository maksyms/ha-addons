# Knowledge Base — Implementation Spec (Atomic Edition)

## Overview

Personal knowledge base that aggregates 23 data sources into Atomic — a self-hosted, Rust-based, AI-augmented knowledge graph with built-in semantic search, MCP server, and wiki synthesis. Accessible via Claude (mobile, web, desktop) through remote MCP.

## Why Atomic

Atomic replaces the need to build a custom vector store, MCP server, indexer, and link generator. It provides out of the box:

- **Vector search** via sqlite-vec (single SQLite file, no external DB)
- **MCP server** at `/mcp` with tools: `semantic_search`, `read_atom`, `create_atom`
- **Auto-tagging** — LLM-powered hierarchical tag extraction
- **Wiki synthesis** — AI-generated articles from atoms under a tag, with inline citations
- **Knowledge graph** — force-directed canvas, semantic clustering
- **Chat** — agentic RAG interface that searches atoms mid-conversation
- **RSS feeds** — subscribe and auto-ingest articles
- **Browser extension** — Chrome web clipper
- **iOS app** — native SwiftUI client
- **REST API** — full CRUD for atoms, used by ingestion scripts
- **Multi-database** — multiple knowledge bases with shared registry

Tech stack: Rust + SQLite + sqlite-vec + actix-web + React. MIT license. Open source.

GitHub: https://github.com/kenforthewin/atomic

---

## Architecture

### Containers (HAOS)

1. **Atomic** — single Docker container (API server + web frontend + MCP endpoint). Single SQLite file for all data including embeddings.

2. **Ingestion** — cron-based Python scripts that push data into Atomic via REST API (`create_atom`).

3. **Caddy** — HAOS addon. Reverse proxy with automatic Let's Encrypt.

### Network

- DNS: A-record `kb.<domain>.com` → home external IP (ddclient for dynamic IP if needed)
- Router: port 443 forwarded to HAOS
- Caddy terminates TLS (Let's Encrypt auto), proxies to Atomic on internal port 8080
- Auth: Atomic has built-in API token authentication

### Claude integration

- claude.ai → Settings → Connectors → Add Custom Connector
- URL: `https://kb.<domain>.com/mcp`
- Auth: Atomic API token in Advanced Settings
- Syncs automatically to Claude mobile and desktop apps
- Available MCP tools: `semantic_search`, `read_atom`, `create_atom`

---

## Data flow

```

[API sources - automated]              [Manual / one-time sources]

Readwise, Raindrop, GitHub,            Evernote export, Kindle,

Reddit, Withings, Telegram             Goodreads CSV, Claude.ai JSON,

       |                               WhatsApp, local PDFs

       | cron (Ingestion container)            |

       v                                      v

  Atomic REST API (create_atom)        Atomic REST API or web UI

       |                                      |

       v                                      v

  SQLite + sqlite-vec (single file, all data + embeddings)

       |

       | auto-tagging, chunking, embedding (Atomic internal)

       |

       | MCP endpoint (/mcp)

       v

  Claude (mobile/web/desktop)

  [Backup]

  SQLite file → cron copy to backup location (NAS, cloud, etc.)

```

---

## Container 1: Atomic

### Deployment

```bash

git clone https://github.com/kenforthewin/atomic.git

cd atomic

docker build -t atomic .

docker run -d \

  --name atomic \

  -p 8080:8080 \

  -v atomic_data:/data \

  atomic

```

Single container: API server + web frontend + MCP endpoint, all in one.

### First launch

1. Open `http://<ha-ip>:8080` (internal) or `https://kb.<domain>.com` (external via Caddy)

2. Setup wizard: claim instance, configure AI provider

3. Create API token for ingestion scripts and MCP access

### AI provider configuration

Two options:

**Option A: Ollama (local, private)**

- Install Ollama on HA (separate container)
- Pull models: `ollama pull nomic-embed-text` (embeddings), `ollama pull llama3` (tagging/wiki/chat)
- Atomic auto-discovers available models
- Pro: free, data stays local
- Con: needs RAM, slower on HA hardware

**Option B: OpenRouter (cloud)**

- API key from openrouter.ai
- Separate model selection for: embedding, tagging, wiki, chat
- Pro: better quality, fast
- Con: costs money, data leaves HA

**Recommendation:** Start with OpenRouter for quality. Switch to Ollama later if privacy or cost matters. Atomic supports both simultaneously.

### Persistent data

- SQLite database file (all atoms + embeddings + tags): mount as Docker volume
- Back up this single file via cron to NAS, cloud storage, or any backup target

### MCP endpoint

Runs at `/mcp` on the server. Tools:

- `semantic_search` — vector search across all atoms
- `read_atom` — read full content of a specific atom
- `create_atom` — create new atom (used by ingestion scripts and Claude itself)

---

## Container 2: Ingestion

### Tech stack

- Python 3.12
- Cron (or APScheduler)
- Per-source adapter scripts
- All adapters call Atomic REST API to create atoms

### Atom format

Each ingestion script creates atoms via Atomic's REST API with:

- **Content:** markdown body
- **Source URL:** original link (if applicable)
- **Tags:** will be auto-generated by Atomic, but adapters can suggest initial tags

Atomic handles: chunking, embedding, auto-tagging, semantic linking.

### Source adapters

#### Type 1: API sources — automated, cron

##### Readwise (P0) — daily

- API: `https://readwise.io/api/v2/`
- Auth: API token
- Pull: highlights, books, articles
- Output: one atom per book/article, highlights as blockquotes
- Incremental: `updated__gt` parameter with last sync timestamp

##### Raindrop.io (P0) — daily

- API: `https://api.raindrop.io/rest/v1/`
- Auth: OAuth2 token (one-time setup)
- Pull: all bookmarks with tags, notes, collections
- Output: one atom per bookmark
- Incremental: filter by `lastUpdate`

##### GitHub Stars (P1) — weekly

- API: GitHub REST API v3
- Auth: personal access token
- Pull: starred repos (name, description, URL, language, topics)
- Output: one atom per starred repo

##### Reddit Saved (P2) — weekly

- API: Reddit API (via PRAW)
- Auth: OAuth2 app credentials
- Pull: saved posts and comments
- Output: one atom per saved item

##### Telegram Saved (P1) — daily

- Library: Telethon
- Auth: Telegram API credentials (api_id, api_hash)
- Pull: saved messages, optionally specific channels
- Output: one atom per message or grouped by day
- Note: media files — save URL reference in atom

##### Withings (P2) — daily

- API: Withings API (OAuth2)
- Auth: OAuth2 (one-time setup)
- Pull: weight, blood pressure, sleep, temperature
- Output: monthly summary atoms with daily data tables

##### YouTube (P1) — weekly

- API: YouTube Data API v3
- Auth: API key or OAuth2
- Pull: playlists, Watch Later, liked videos
- Output: one atom per video or per playlist

##### RSS Feeds — continuous

- Atomic has built-in RSS support
- Configure feeds directly in Atomic UI
- Articles auto-ingested as atoms
- Good for: Hacker News, tech blogs, industry feeds

#### Type 2: One-time import scripts (run from laptop)

##### Evernote (P0)

- Tool: `evernote-backup` Python CLI
- Process: ENEX export → MD conversion → push each note as atom via API
- Run once, then cancel Evernote subscription

##### Goodreads (P2)

- Export: CSV from goodreads.com/review/import
- Script: parse CSV → create atom per book (title, author, rating, review, shelves)

##### Audible (P2)

- Method: Readwise integration (if available) or manual library list
- Output: atom per audiobook with metadata

##### Claude.ai (P1)

- Export: Settings → Export Data → JSON
- Script: parse conversations JSON → atom per conversation
- Metadata: date, title, summary

##### Apple Health (P2)

- Export: iPhone → Health → Export All Health Data → ZIP
- Script: parse `export.xml` → aggregate by day/week → atoms with data tables
- Focus: steps, HRV, resting HR, sleep, workouts

#### Type 3: Manual / no-API sources (Phase 4)

##### LinkedIn Saved — quarterly Meta data export, HTML → atom via API

##### Facebook Saved — quarterly Meta data export (Download Your Information), JSON → atom via API

##### Instagram Saved — quarterly Meta data export (Download Your Information), JSON → atom via API

##### Perplexity — manual copy of valuable threads → create atom via web UI

##### Apple Podcasts — OPML export of subscriptions → atom via API

##### JustWatch — maintain watchlist as atoms, create via web UI or API

##### WhatsApp — per-chat export from app → TXT → atom via API

##### Fastmail — IMAP fetch specific folders → atom via API

### Configuration (environment variables)

```

ATOMIC_API_URL=http://atomic-server:8080

ATOMIC_API_TOKEN=<token-from-setup>

READWISE_API_TOKEN=<token>

RAINDROP_TOKEN=<token>

GITHUB_TOKEN=<token>

REDDIT_CLIENT_ID=<id>

REDDIT_CLIENT_SECRET=<secret>

REDDIT_USERNAME=<username>

TELEGRAM_API_ID=<id>

TELEGRAM_API_HASH=<hash>

WITHINGS_CLIENT_ID=<id>

WITHINGS_CLIENT_SECRET=<secret>

YOUTUBE_API_KEY=<key>

```

### Cron schedule

```

# P0 — daily at 03:00

0 3 * * * python /app/adapters/readwise.py

15 3 * * * python /app/adapters/raindrop.py

# P1 — daily at 04:00

0 4 * * * python /app/adapters/telegram.py

15 4 * * * python /app/adapters/youtube.py

# P1 — weekly Sunday 05:00

0 5 * * 0 python /app/adapters/github.py

# P2 — daily at 05:00

30 5 * * * python /app/adapters/withings.py

# P2 — weekly Sunday 06:00

0 6 * * 0 python /app/adapters/reddit.py

```

### Dockerfile outline

```dockerfile

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cron or APScheduler entrypoint

CMD ["python", "scheduler.py"]

```

### requirements.txt

```

requests

pyyaml

telethon

praw

google-api-python-client

apscheduler

```

---

## Container 3: Caddy (HAOS addon)

### Install

Add repository: `https://github.com/einschmidt/hassio-addons`

Install "Caddy 2" from add-on store.

### Caddyfile

```

kb.<domain>.com {

    reverse_proxy atomic:8080

}

```

Caddy handles Let's Encrypt automatically. No certbot, no renewal cron.

### Router

Port 443 forwarded to HAOS IP.

---

## Additional features to leverage

### Browser extension

- Install Atomic Web Clipper (Chrome/Edge/Brave)
- Configure server URL (`https://kb.<domain>.com`) and API token
- Clip web pages directly into Atomic as atoms
- Captures queued offline and synced when server available

### iOS app

- Native SwiftUI client from App Store
- Read and write atoms on mobile
- Configure to connect to `https://kb.<domain>.com`

### Wiki synthesis

- Once enough atoms accumulate under a tag, Atomic generates wiki articles
- Cited articles with inline links back to source atoms
- Useful for: biohacking topics, sailing knowledge, investment research, tech leadership

### Canvas / knowledge graph

- Force-directed visualization in web UI
- Semantically similar atoms cluster together
- Explore connections visually

---

## 23 Data Sources — Summary

| # | Source | Type | Method | Phase |

|---|--------|------|--------|-------|

| 1 | Evernote | Notes | One-time import | P0 / Phase 1 |

| 2 | Raindrop.io | Bookmarks | API, daily cron | P0 / Phase 1 |

| 3 | Readwise / Reader | Highlights | API, daily cron | P0 / Phase 1 |

| 4 | Paperless-ngx | Documents | API or manual | P1 / Phase 2 |

| 5 | Kindle Highlights | Book notes | Via Readwise | P0 / Phase 1 |

| 6 | Goodreads | Book catalog | CSV import | P2 / Phase 3 |

| 7 | Audible | Audiobooks | Via Readwise or manual | P2 / Phase 3 |

| 8 | YouTube | Playlists | API, weekly cron | P1 / Phase 2 |

| 9 | Apple Podcasts | Subscriptions | OPML export | P3 / Phase 4 |

| 10 | JustWatch | Watchlist | Manual | P3 / Phase 4 |

| 11 | GitHub | Stars/repos | API, weekly cron | P1 / Phase 2 |

| 12 | Fastmail | Email archives | IMAP script | P2 / Phase 3 |

| 13 | LinkedIn | Saved posts | Quarterly export | P3 / Phase 4 |

| 14 | Telegram | Saved messages | Telethon, daily cron | P1 / Phase 2 |

| 15 | WhatsApp | Chat exports | Manual | P2 / Phase 3 |

| 16 | Reddit | Saved | API, weekly cron | P2 / Phase 3 |

| 17 | Facebook | Saved | Quarterly export | P3 / Phase 4 |

| 18 | Instagram | Saved | Quarterly export | P3 / Phase 4 |

| 19 | Claude.ai | Chat history | JSON export | P1 / Phase 2 |

| 20 | Perplexity | Search history | Manual | P3 / Phase 4 |

| 21 | Apple Health | Health data | XML export | P2 / Phase 3 |

| 22 | Withings | Health data | API, daily cron | P2 / Phase 3 |

| 23 | Local PDF/docs | Documents | Manual import | P1 / Phase 2 |

---

## Phases

### Phase 0: Infrastructure (1 evening)

- [ ] Build and run Atomic container on HAOS
- [ ] Caddy addon installed and configured
- [ ] DNS A-record for `kb.<domain>.com`
- [ ] Port 443 forwarded on router
- [ ] Atomic setup wizard: claim instance, configure AI provider
- [ ] Create API token
- [ ] Claude.ai → Settings → Connectors → add custom connector (`https://kb.<domain>.com/mcp`)
- [ ] Verify: Claude mobile can call `semantic_search` (returns empty)
- [ ] Install Atomic browser extension, configure server URL
- [ ] Set up backup cron for Atomic SQLite data

### Phase 1: Quick wins — P0 sources (1 weekend)

- [ ] Readwise adapter → atoms via API
- [ ] Raindrop adapter → atoms via API
- [ ] Evernote one-time import (export ENEX → convert → push atoms)
- [ ] Kindle highlights covered by Readwise
- [ ] Verify: Claude can answer questions about imported content
- [ ] Configure useful RSS feeds in Atomic

### Phase 2: High-value — P1 sources (1-2 weeks)

- [ ] Telegram adapter (Telethon)
- [ ] YouTube adapter
- [ ] GitHub stars adapter
- [ ] Claude.ai conversation export and import
- [ ] Local PDF import pipeline
- [ ] Paperless-ngx → Atomic bridge (if needed)

### Phase 3: Long tail — P2 sources (2-4 weeks)

- [ ] Goodreads CSV import
- [ ] Audible import
- [ ] Fastmail adapter
- [ ] WhatsApp chat exports
- [ ] Reddit adapter
- [ ] Apple Health XML import
- [ ] Withings adapter

### Phase 4: Manual sources — P3 (ongoing)

- [ ] LinkedIn quarterly export workflow
- [ ] Facebook saved quarterly export workflow
- [ ] Instagram saved quarterly export workflow
- [ ] Perplexity manual save workflow
- [ ] Apple Podcasts OPML export
- [ ] JustWatch watchlist management

### Phase 5: Optimization (ongoing)

- [ ] Tune AI provider/model selection for quality vs cost
- [ ] Leverage wiki synthesis for key knowledge domains
- [ ] Explore Ollama for local-only operation
- [ ] Review and curate auto-generated tags
- [ ] Evaluate if additional RAG tuning (re-ranking, prompt templates) is needed

---

## Backup strategy

Atomic stores everything in a single SQLite file. Backup = copy this file.

- Atomic data directory mounted as Docker volume on HAOS
- Cron job copies SQLite file daily to backup location (NAS, cloud storage, etc.)
- SQLite is safe to copy while Atomic is running (WAL mode)

---

## Security checklist

- [ ] Atomic API token: generated via setup wizard, stored in HA secrets
- [ ] HTTPS only (Caddy enforces via Let's Encrypt)
- [ ] Ingestion container: all API tokens in environment variables, not in code
- [ ] Router: only port 443 forwarded, nothing else
- [ ] Optional: Caddy IP allowlist for Anthropic ranges (for MCP endpoint only)
- [ ] Atomic web UI: protected by instance claim (first user becomes owner)

---

## Key differences from previous (custom) spec

| Aspect | Custom spec | Atomic spec |

|--------|------------|-------------|

| Vector store | ChromaDB (Python, separate) | sqlite-vec (embedded in SQLite) |

| MCP server | Custom FastAPI | Built into Atomic |

| Indexer/watchdog | Custom Python watchdog | Built into Atomic |

| Link generation | Custom script (Phase 3) | Built-in canvas + semantic clustering |

| Wiki synthesis | Not planned | Built-in |

| Auto-tagging | Not planned | Built-in |

| Web clipper | Not planned | Built-in browser extension |

| iOS app | Not planned | Built-in |

| Language | Python | Rust (Atomic) + Python (ingestion only) |

| Containers needed | 4 (OneDrive, Knowledge API, Ingestion, Caddy) | 3 (Atomic, Ingestion, Caddy addon) |

| Custom code | ~2000 lines | ~500 lines (ingestion adapters only) |
