# Atomic Home Assistant Add-on — Rough Spec

## Goal

Run Atomic (personal knowledge base) as a Home Assistant add-on in a single Docker container on Raspberry Pi 5.

## Key Decisions

- **Option A**: Keep nginx inside the container for internal static file serving + routing. External access via Caddy 2 (already running on the host/network).
- **No fork**: Separate HA add-on repo that pulls from upstream's published multi-arch Docker images.
- **No building Rust on the Pi**: Upstream CI already publishes ARM64 images to `ghcr.io/kenforthewin/atomic:latest` (built on native ARM runners via `.github/workflows/docker.yml`).

## Why nginx Can't Be Removed

`atomic-server` is a pure API server (REST `/api/*`, WebSocket `/ws`, MCP `/mcp`, OAuth `/oauth/*`, health `/health`). It has:
- No `actix-files` dependency
- No `--static-dir` CLI flag
- No catch-all route for SPA fallback

The React frontend is a static Vite build that must be served separately. In the upstream all-in-one image, nginx serves these from `/usr/share/nginx/html` and proxies API routes to `atomic-server` on `127.0.0.1:8080`. The combined service listens on port `8081`.

## Upstream All-in-One Architecture

The upstream `Dockerfile` (target: `all-in-one`) already bundles everything:

- **Base**: `debian:bookworm-slim`
- **Processes**: supervisord manages `atomic-server` (port 8080) + `nginx` (port 8081)
- **Frontend**: static files in `/usr/share/nginx/html`
- **nginx config**: `docker/nginx-fly.conf` — routes `/api/*`, `/ws`, `/mcp`, `/oauth/*`, `/.well-known/*` to atomic-server; serves frontend with SPA fallback for everything else
- **supervisord config**: `docker/supervisord.conf`
- **Data volume**: `/data` (SQLite databases: registry.db + data DBs)
- **Health check**: HTTP GET `/health` on port 8081
- **User**: `atomic` (non-root)

## Add-on Dockerfile Strategy

Use `COPY --from` to extract pre-built artifacts from the upstream image:

```dockerfile
FROM ghcr.io/kenforthewin/atomic:latest AS upstream

FROM debian:bookworm-slim
COPY --from=upstream /usr/local/bin/atomic-server /usr/local/bin/
COPY --from=upstream /usr/share/nginx/html /usr/share/nginx/html
# Then install nginx, supervisor, add HA-specific configs
```

This avoids forking, avoids Rust compilation, and builds in seconds.

## What the Add-on Repo Needs

1. **`config.yaml`** — HA add-on manifest: name, slug, version, description, arch (`aarch64`, `amd64`), ports, options schema, ingress settings
2. **`Dockerfile`** — Pulls from upstream image, installs nginx + supervisor, copies HA-specific configs
3. **`run.sh`** — Entrypoint that reads HA options from `/data/options.json` and starts supervisord (or starts processes directly)
4. **nginx config** — Adapt `docker/nginx-fly.conf` from upstream; listen port may need adjusting for HA ingress
5. **supervisord config** — Adapt `docker/supervisord.conf` from upstream

## Data Persistence

HA mounts `/data` for add-on storage. Atomic already uses `/data` as its data directory in Docker:
- `/data/registry.db` — settings, API tokens, database metadata
- `/data/default.db` — default knowledge base
- `/data/{uuid}.db` — additional databases

This aligns naturally with HA's `/data` convention.

## Networking Considerations

- Expose port `8081` (nginx) from the container
- Caddy 2 on the host reverse-proxies to this port for external/TLS access
- If using HA ingress (sidebar access), handle ingress proxy headers and base path — this may require SPA routing adjustments
- WebSocket (`/ws`) and SSE (`/mcp`) need proxy configs that support long-lived connections (already handled in nginx-fly.conf with 86400s keepalive and streaming settings)

## Upstream Files to Reference

- `Dockerfile` — stages `all-in-one`, `rust-builder`, `frontend-builder` (lines ~106+)
- `docker/nginx-fly.conf` — internal nginx routing config
- `docker/supervisord.conf` — process management
- `.github/workflows/docker.yml` — CI that publishes multi-arch images
- `.cargo/config.toml` — confirms ARM64 (aarch64) is explicitly supported
- `crates/atomic-server/src/main.rs` — server route setup (confirms no static file serving)
- `crates/atomic-server/src/config.rs` — CLI flags (confirms no --static-dir)

## Version Tracking

To update the add-on, bump the upstream image tag in the Dockerfile. Current upstream version: v1.20.2 (commit b7da738).
