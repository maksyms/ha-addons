# Atomic HA Add-on — Design Spec

## Overview

Home Assistant add-on that runs [Atomic](https://github.com/kenforthewin/atomic) (personal knowledge base) as a single container on Raspberry Pi 5. Uses pre-built upstream Docker images — no Rust compilation, no forking.

## Architecture

```
┌─────────────────────────────────────────────┐
│  HA Add-on Container (debian:bookworm-slim) │
│                                             │
│  run.sh (PID 1)                             │
│    ├── reads /data/options.json             │
│    ├── starts atomic-server (background)    │
│    │     └── 127.0.0.1:8080                 │
│    └── execs nginx (foreground)             │
│          └── 0.0.0.0:8081                   │
│                                             │
│  /data/  (HA-managed persistent volume)     │
│    ├── atomic.db (+ other databases)        │
│    └── options.json                         │
│                                             │
│  /usr/share/nginx/html/ (React SPA)         │
└──────────────┬──────────────────────────────┘
               │ :8081
               ▼
┌──────────────────────┐     ┌──────────────┐
│  Caddy (HA add-on)   │────▶│  Internet    │
│  atomic.example.com  │     │  (MCP, Web)  │
└──────────────────────┘     └──────────────┘
               ▲
               │ internal network
┌──────────────┴───────┐
│  atomic-ingest       │
│  (future add-on)     │
└──────────────────────┘
```

### Why nginx is required

`atomic-server` is a pure API server (REST, WebSocket, MCP, OAuth). It has no static file serving capability — no `actix-files` dependency, no `--static-dir` flag, no SPA fallback route. The React frontend is a static Vite build served by nginx, which also proxies API routes to atomic-server.

### Process management

`run.sh` is PID 1. It starts `atomic-server` in the background, waits for it to pass a health check, then `exec`s nginx in the foreground. No supervisord — if atomic-server crashes, the HA health check fails and the Supervisor restarts the container.

### Access method

Caddy-only (no HA ingress). The entire app — frontend, API, WebSocket, MCP, OAuth — is exposed via Caddy reverse proxy for external/TLS access. Atomic runs at `/` with no base-path complications. HA ingress is earmarked for a future iteration.

### Internet access

The MCP endpoint (`/mcp`) and full web UI are internet-accessible via Caddy. Atomic's built-in OAuth/token auth handles security — Caddy just proxies through.

### Internal network access

The `atomic-ingest` companion add-on (future) will access Atomic's API on the internal HA Docker network via `hostname:port`. No special configuration needed beyond the exposed port.

### User and permissions

Everything runs as root. Consistent with other add-ons in this repo. The container is sandboxed by HA Supervisor.

## Dockerfile

Multi-stage build using `COPY --from` to extract pre-built artifacts from the upstream all-in-one image:

```dockerfile
FROM ghcr.io/kenforthewin/atomic:latest AS upstream

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx curl jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pre-built artifacts from upstream
COPY --from=upstream /usr/local/bin/atomic-server /usr/local/bin/
COPY --from=upstream /usr/share/nginx/html /usr/share/nginx/html

# nginx config copied from upstream — stays in sync with :latest
COPY --from=upstream /etc/nginx/conf.d/atomic.conf /etc/nginx/conf.d/atomic.conf

# Remove default nginx config
RUN rm -f /etc/nginx/sites-enabled/default

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8081
CMD ["/run.sh"]
```

Key decisions:
- **Base: `debian:bookworm-slim`** — matches upstream, consistent with other add-ons in this repo. Not using the HA addon base (`hassio-addons/debian-base`) since we don't need bashio, S6 overlay, or Tempio.
- **Version: `:latest`** — upstream develops fast, no pinning. Builds are not reproducible, but upstream breakage is caught quickly on the Pi.
- **nginx config: `COPY --from=upstream`** — no local `nginx.conf` in the repo. Stays automatically in sync with upstream. Port override (if non-default) is applied at runtime via `sed` in `run.sh`.
- **Arch: `aarch64` only** — this repo targets Raspberry Pi 5 exclusively.

## config.yaml

```yaml
name: Atomic
description: Personal knowledge base powered by Atomic Server
version: "1.0.0"
slug: atomic
url: "https://github.com/kenforthewin/atomic"
arch:
  - aarch64
startup: application
boot: auto
init: false

ports:
  8081/tcp: 8081
ports_description:
  8081/tcp: Atomic web UI and API

options:
  public_url: ""
  rust_log: "warn"
schema:
  public_url: str
  rust_log: "list(trace|debug|info|warn|error)"

healthcheck: "curl -sf http://localhost:8081/health || exit 1"
healthcheck_interval: 10
healthcheck_timeout: 3
healthcheck_start_period: 15
healthcheck_retries: 3

map:
  - data:rw
```

### Options

| Option | Type | Default | Required | Description |
|--------|------|---------|----------|-------------|
| `public_url` | string | `""` | No (but needed for OAuth/MCP) | External URL where Atomic is reachable (e.g., `https://atomic.example.com`). Required for OAuth discovery and remote MCP. |
| `rust_log` | enum | `warn` | No | Log verbosity for atomic-server. One of: `trace`, `debug`, `info`, `warn`, `error`. |

Note: the container always listens on port 8081 internally. Users can remap the host-side port via the HA UI if 8081 conflicts.

### Health check

Uses the nginx-proxied `/health` endpoint (port 8081) to validate the full stack — both nginx and atomic-server must be healthy. Start period of 15 seconds accommodates Pi 5 cold start.

## run.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Read HA options ---
OPTIONS="/data/options.json"

PUBLIC_URL=$(jq -r '.public_url // empty' "$OPTIONS")
RUST_LOG=$(jq -r '.rust_log // "warn"' "$OPTIONS")

export RUST_LOG

# --- Build atomic-server command ---
ATOMIC_CMD=(atomic-server --data-dir /data serve --bind 127.0.0.1 --port 8080)

if [[ -n "$PUBLIC_URL" ]]; then
    ATOMIC_CMD+=(--public-url "$PUBLIC_URL")
fi

# --- Start atomic-server in background ---
echo "Starting atomic-server..."
"${ATOMIC_CMD[@]}" &
ATOMIC_PID=$!

# --- Wait for atomic-server to be ready ---
echo "Waiting for atomic-server..."
READY=false
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo "atomic-server ready"
        READY=true
        break
    fi
    if ! kill -0 "$ATOMIC_PID" 2>/dev/null; then
        echo "atomic-server failed to start"
        exit 1
    fi
    sleep 1
done

if [[ "$READY" != "true" ]]; then
    echo "atomic-server did not become ready in 30 seconds"
    exit 1
fi

# --- Exec nginx as PID 1 ---
echo "Starting nginx..."
exec nginx -g "daemon off;"
```

## nginx config

**Not maintained in this repo.** Copied from the upstream image at Docker build time:

```dockerfile
COPY --from=upstream /etc/nginx/conf.d/atomic.conf /etc/nginx/conf.d/atomic.conf
```

This keeps the config automatically in sync with upstream's `:latest` tag. The upstream config (`docker/nginx-fly.conf`) handles:

- `/api/*` — proxy to atomic-server with streaming support (300s timeout)
- `/ws` — WebSocket proxy with 24-hour keepalive
- `/mcp` — SSE proxy with disabled buffering (300s timeout)
- `/oauth/*`, `/.well-known/*` — OAuth discovery and flow
- `/health` — health check pass-through
- `/assets/*` — static assets with 1-year cache (Vite content-hashed)
- `/` — SPA fallback (`try_files $uri $uri/ /index.html`)

No runtime modifications are made to this config.

## Data persistence

HA mounts `/data` for add-on storage. Atomic uses `--data-dir /data` which stores:
- `atomic.db` — main database (SQLite)
- Additional databases as created by the user

This aligns naturally with HA's `/data` convention. No migration or symlink needed.

## Caddy configuration

Caddy (running as a separate HA add-on or on the host) reverse-proxies to the container. Caddy natively handles WebSocket upgrades and SSE streaming with no special configuration.

Recommended Caddyfile snippet:

```
atomic.example.com {
    reverse_proxy <atomic-container-hostname>:8081
}
```

Caddy auto-provisions TLS via Let's Encrypt. Replace `atomic.example.com` with your actual domain. Since Caddy runs in its own HA add-on container, use the atomic container's hostname (e.g., `23930cf1-atomic`) as the upstream — not `localhost`.

## API token for integrations

Atomic supports API tokens for programmatic access (used by atomic-ingest and remote MCP clients). Tokens are created manually:

- **Web UI:** Settings > API Tokens in the Atomic frontend
- **CLI:** `docker exec <container> atomic-server token create --name <name>`

Tokens persist in `/data` across container restarts.

## CI/CD

**File:** `.github/workflows/deploy-atomic.yml`

Follows the same pattern as other add-ons:

- **Trigger:** Push to `master` with path filter `atomic/**`
- **Steps:**
  1. Checkout repo
  2. Extract current version from `atomic/config.yaml`
  3. Bump patch version
  4. Generate `CHANGELOG.md` from git log since last version bump
  5. Commit with `[skip ci]` to prevent loop

No `workflow_dispatch` or force deploy.

## File inventory

### New files in `atomic/`

| File | Purpose |
|------|---------|
| `config.yaml` | HA add-on manifest |
| `Dockerfile` | Multi-stage COPY --from upstream |
| `run.sh` | Entrypoint — reads options, manages processes |
| `CHANGELOG.md` | Empty initially, auto-populated by CI |
| `icon.png` | Add-on icon (from Atomic branding) |
| `logo.png` | Add-on logo (from Atomic branding) |

### New files elsewhere

| File | Purpose |
|------|---------|
| `.github/workflows/deploy-atomic.yml` | CI/CD workflow |

### Updated files

| File | Change |
|------|--------|
| `README.md` | Add atomic to add-on listing (including Caddy config) |
| `CLAUDE.md` | Add atomic section |

Note: `repository.json` does not need updating — it contains repo-level metadata only. HA auto-discovers add-ons by scanning directories with `config.yaml`.

### Notably absent

| File | Why |
|------|-----|
| `nginx.conf` | Copied from upstream at build time |
| `supervisord.conf` | Not using supervisord |
| `build.yaml` | Single arch, no per-arch base image overrides |

## Future work (earmarked)

- **HA ingress support** — sidebar access with base-path handling for the SPA
- **PostgreSQL option** — expose `storage` and `database_url` options if scaling beyond SQLite
