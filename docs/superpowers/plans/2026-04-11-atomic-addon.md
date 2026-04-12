# Atomic HA Add-on Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Home Assistant add-on that runs Atomic (personal knowledge base) using pre-built upstream Docker images.

**Architecture:** Single container with nginx (static frontend + reverse proxy) and atomic-server (Rust API), managed by `run.sh`. Caddy on the host provides TLS and internet access. No supervisord, no forking, no Rust compilation.

**Tech Stack:** Docker (multi-stage COPY --from), nginx, bash, jq

**Spec:** `docs/superpowers/specs/2026-04-11-atomic-addon-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `atomic/config.yaml` | HA add-on manifest — name, arch, ports, options schema, health check |
| `atomic/Dockerfile` | Multi-stage build — copies binary + frontend + nginx config from upstream image |
| `atomic/run.sh` | Entrypoint — reads options.json, starts atomic-server, execs nginx |
| `atomic/CHANGELOG.md` | Version history — empty initially, auto-populated by CI |
| `atomic/icon.png` | Add-on icon (128x128) |
| `atomic/logo.png` | Add-on logo (256x256) |
| `.github/workflows/deploy-atomic.yml` | CI — path-filtered auto version bump + changelog |
| `README.md` | Repository readme — add atomic entry |
| `CLAUDE.md` | Dev docs — add atomic section |

---

### Task 1: Create config.yaml

**Files:**
- Create: `atomic/config.yaml`

- [ ] **Step 1: Create the directory and config.yaml**

```yaml
name: Atomic
description: >-
  Personal knowledge base powered by Atomic Server.
  Linked data, real-time collaboration, and AI-ready
  knowledge management with MCP endpoint.
version: "1.0.0"
slug: atomic
url: "https://github.com/kenforthewin/atomic"
arch:
  - aarch64
init: false
startup: application
boot: auto

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

- [ ] **Step 2: Verify YAML is valid**

Run: `python3 -c "import yaml; yaml.safe_load(open('atomic/config.yaml'))"`
Expected: No output (no errors)

- [ ] **Step 3: Commit**

```bash
git add atomic/config.yaml
git commit -m "feat(atomic): add HA add-on manifest"
```

---

### Task 2: Create Dockerfile

**Files:**
- Create: `atomic/Dockerfile`

- [ ] **Step 1: Create the Dockerfile**

```dockerfile
FROM ghcr.io/kenforthewin/atomic:latest AS upstream

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx curl jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pre-built artifacts from upstream
COPY --from=upstream /usr/local/bin/atomic-server /usr/local/bin/
COPY --from=upstream /usr/share/nginx/html /usr/share/nginx/html

# nginx config from upstream — stays in sync with :latest
COPY --from=upstream /etc/nginx/conf.d/atomic.conf /etc/nginx/conf.d/atomic.conf

# Remove default nginx site
RUN rm -f /etc/nginx/sites-enabled/default

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8081
CMD ["/run.sh"]
```

- [ ] **Step 2: Commit**

```bash
git add atomic/Dockerfile
git commit -m "feat(atomic): add Dockerfile with COPY --from upstream"
```

---

### Task 3: Create run.sh

**Files:**
- Create: `atomic/run.sh`

- [ ] **Step 1: Create run.sh**

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

- [ ] **Step 2: Verify script syntax**

Run: `bash -n atomic/run.sh`
Expected: No output (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add atomic/run.sh
git commit -m "feat(atomic): add entrypoint script"
```

---

### Task 4: Create CHANGELOG.md and icons

**Files:**
- Create: `atomic/CHANGELOG.md`
- Create: `atomic/icon.png`
- Create: `atomic/logo.png`

- [ ] **Step 1: Create empty CHANGELOG.md**

```markdown
## 1.0.0
- Initial release
- Atomic Server knowledge base
- nginx reverse proxy with SPA fallback
- Health check support
```

- [ ] **Step 2: Create icon.png and logo.png**

Generate icon (128x128) and logo (256x256) using Atomic's branding — the Atomic logo is a stylized atom symbol. Use a blue/purple color scheme consistent with Atomic's brand. The icon should be recognizable at small sizes in the HA sidebar.

Use ImageMagick or a similar tool to create simple branded PNGs:

```bash
# icon.png - 128x128, atom symbol on dark background
convert -size 128x128 xc:'#1a1a2e' \
  -fill '#e94560' -stroke '#e94560' -strokewidth 2 \
  -draw "circle 64,64 64,40" \
  -draw "ellipse 64,64 40,20 30" \
  -draw "ellipse 64,64 40,20 -30" \
  -draw "ellipse 64,64 40,20 90" \
  -fill '#e94560' -draw "circle 64,64 64,58" \
  atomic/icon.png

# logo.png - 256x256, same design larger
convert -size 256x256 xc:'#1a1a2e' \
  -fill '#e94560' -stroke '#e94560' -strokewidth 3 \
  -draw "circle 128,128 128,80" \
  -draw "ellipse 128,128 80,40 30" \
  -draw "ellipse 128,128 80,40 -30" \
  -draw "ellipse 128,128 80,40 90" \
  -fill '#e94560' -draw "circle 128,128 128,118" \
  atomic/logo.png
```

Note: The exact ImageMagick commands may need adjustment to produce a clean result. The goal is an atom-like symbol (nucleus + orbits) on a dark background with Atomic's red/pink accent color (#e94560). If the generated images don't look good, download Atomic's favicon from the upstream repo at `browser/public/favicon.svg` and convert it:

```bash
# Alternative: convert upstream favicon
convert -background none -resize 128x128 /tmp/atomic-upstream/browser/public/favicon.svg atomic/icon.png
convert -background none -resize 256x256 /tmp/atomic-upstream/browser/public/favicon.svg atomic/logo.png
```

- [ ] **Step 3: Verify files exist and have reasonable sizes**

Run: `ls -la atomic/icon.png atomic/logo.png atomic/CHANGELOG.md`
Expected: icon.png ~5-50KB, logo.png ~10-100KB, CHANGELOG.md non-empty

- [ ] **Step 4: Commit**

```bash
git add atomic/CHANGELOG.md atomic/icon.png atomic/logo.png
git commit -m "feat(atomic): add changelog and icons"
```

---

### Task 5: Create CI workflow

**Files:**
- Create: `.github/workflows/deploy-atomic.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Deploy Atomic Add-on

on:
  push:
    branches: [master]
    paths:
      - 'atomic/**'

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0

      - name: Bump addon version
        run: |
          cd atomic
          current=$(grep '^version:' config.yaml | sed 's/version: *"\(.*\)"/\1/')
          IFS='.' read -r major minor patch <<< "$current"
          new_version="${major}.${minor}.$((patch + 1))"
          sed -i "s/^version: \"${current}\"/version: \"${new_version}\"/" config.yaml
          echo "VERSION=${new_version}" >> "$GITHUB_ENV"
          echo "PREV_VERSION=${current}" >> "$GITHUB_ENV"
          echo "Bumped version: ${current} → ${new_version}"

      - name: Generate changelog
        run: |
          PREV_COMMIT=$(git log --oneline --grep="Bump HAOS addon version to ${PREV_VERSION}" --format="%H" -1)
          if [ -n "$PREV_COMMIT" ]; then
            CHANGES=$(git log --oneline "${PREV_COMMIT}..HEAD" --no-decorate \
              | grep -v "\[skip ci\]" \
              | sed 's/^[a-f0-9]* /- /')
          else
            CHANGES=$(git log --oneline -10 --no-decorate \
              | grep -v "\[skip ci\]" \
              | sed 's/^[a-f0-9]* /- /')
          fi

          CHANGELOG="atomic/CHANGELOG.md"
          NEW_ENTRY="## ${VERSION}"$'\n'"${CHANGES}"
          if [ -f "$CHANGELOG" ]; then
            echo -e "${NEW_ENTRY}\n\n$(cat "$CHANGELOG")" > "$CHANGELOG"
          else
            echo "$NEW_ENTRY" > "$CHANGELOG"
          fi

      - name: Commit version bump and changelog
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add atomic/config.yaml atomic/CHANGELOG.md
          git commit -m "Bump HAOS addon version to ${VERSION} [skip ci]"
          git pull --rebase
          git push
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-atomic.yml'))"`
Expected: No output (no errors)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy-atomic.yml
git commit -m "ci(atomic): add deploy workflow"
```

---

### Task 6: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add atomic entry to the Add-ons section**

Add after the Tika & Gotenberg entry (before `## License`):

```markdown
### [Atomic](atomic/)

Personal knowledge base powered by Atomic Server. Linked data, real-time collaboration, and AI-ready knowledge management.

- MCP endpoint for AI integration
- Real-time WebSocket collaboration
- OAuth authentication
- Caddy reverse proxy for TLS
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add atomic to README"
```

---

### Task 7: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the "What This Is" section**

Add entry 4 to the numbered list:

```markdown
4. **atomic/** — HA add-on wrapping [kenforthewin/atomic](https://github.com/kenforthewin/atomic). Personal knowledge base with linked data, real-time collaboration, MCP endpoint for AI tools, and OAuth auth. Uses pre-built upstream Docker images.
```

- [ ] **Step 2: Update the Repository Structure tree**

Add to the tree after the `paperless-gpt/` section:

```
├── atomic/                      # Personal knowledge base add-on
│   ├── config.yaml              # HA add-on manifest (aarch64)
│   ├── Dockerfile               # COPY --from upstream ghcr.io image
│   ├── run.sh                   # reads options.json, starts atomic-server + nginx
│   └── CHANGELOG.md
```

- [ ] **Step 3: Add atomic section after paperless-gpt section**

Add before the existing `---` separator at the end:

```markdown
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

Caddyfile:
```
atomic.example.com {
    reverse_proxy localhost:8081
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

`atomic-ingest` (companion add-on, future) accesses Atomic's API on the internal HA Docker network. API tokens created manually via Atomic's web UI.
```

- [ ] **Step 4: Update the CI/CD section**

Add to the `deploy-claudecode-ea.yml` paragraph area, or update to reflect that atomic also has a workflow. Add after the existing CI/CD description:

```markdown
`deploy-atomic.yml` follows the same pattern: push-triggered, path-filtered, auto version bump + changelog.
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add atomic section to CLAUDE.md"
```

---

### Task 8: Build and verify

**Files:** None (verification only)

- [ ] **Step 1: Verify all files are in place**

Run: `ls -la atomic/`
Expected: config.yaml, Dockerfile, run.sh, CHANGELOG.md, icon.png, logo.png

Run: `ls -la .github/workflows/deploy-atomic.yml`
Expected: File exists

- [ ] **Step 2: Build the Docker image**

Run: `docker build -t atomic-test atomic/`
Expected: Successful build. The `COPY --from` pulls the upstream image and extracts the binary, frontend, and nginx config. Should complete in under 2 minutes (mostly downloading the upstream image).

- [ ] **Step 3: Test the container starts**

Run: `docker run --rm -d --name atomic-test -p 8081:8081 -v /tmp/atomic-data:/data atomic-test`
Expected: Container starts without errors.

Run (wait 15 seconds for startup): `curl -sf http://localhost:8081/health`
Expected: `{"status":"ok","version":"..."}` — confirms both atomic-server and nginx are running.

- [ ] **Step 4: Verify the web UI loads**

Run: `curl -sf http://localhost:8081/ | head -5`
Expected: HTML response containing `<div id="root">` or similar React SPA mount point.

- [ ] **Step 5: Clean up**

Run: `docker stop atomic-test && docker rmi atomic-test && rm -rf /tmp/atomic-data`

- [ ] **Step 6: Commit any fixes**

If any issues were found and fixed during testing, commit the fixes:

```bash
git add -A atomic/
git commit -m "fix(atomic): address issues found during testing"
```

---

### Task 9: Deploy to Home Assistant

**Files:** None (deployment only)

- [ ] **Step 1: Push to master**

Verify all changes are committed:

Run: `git status`
Expected: Clean working tree.

Run: `git push origin master`
Expected: Push succeeds. CI workflow triggers for the `atomic/**` path change and bumps the version.

- [ ] **Step 2: Install on Home Assistant**

Run on HA CLI (SSH):
```bash
ha store refresh
```

Then in HA UI: Settings > Add-ons > Add-on Store > find "Atomic" > Install.

Or via CLI:
```bash
ha apps install local_atomic
```

- [ ] **Step 3: Configure and start**

In HA UI: Set `public_url` to your domain (e.g., `https://kb.example.com`), then start the add-on.

- [ ] **Step 4: Verify health**

Run on HA CLI:
```bash
ha apps info local_atomic
```
Expected: State is "started", health is "healthy".

- [ ] **Step 5: Configure Caddy and verify external access**

Add to Caddyfile:
```
atomic.example.com {
    reverse_proxy localhost:8081
}
```

Reload Caddy and verify:
```bash
curl -sf https://atomic.example.com/health
```
Expected: `{"status":"ok","version":"..."}` with valid TLS.
