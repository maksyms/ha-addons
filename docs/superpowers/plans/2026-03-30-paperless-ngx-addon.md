# Paperless-ngx HA Add-on Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a paperless-ngx Home Assistant add-on following the repo's existing patterns (env-loading, CI/CD, config schema), using a Debian base image.

**Architecture:** Single-container add-on with paperless-ngx installed from official release tarball, Redis as in-container background daemon, Celery worker/beat as background processes, and Granian web server in foreground. No nginx, no ingress, no s6 service tree.

**Tech Stack:** Debian base (`hassio-addons/debian-base:9.2.0`), Python 3, Redis, Celery, Granian, Tesseract OCR, paperless-ngx v2.20.10

**Spec:** `docs/superpowers/specs/2026-03-30-paperless-ngx-addon-design.md`

---

### File Structure

All new files — nothing modified except the CI workflow directory which already exists.

| File | Purpose |
|------|---------|
| `paperless-ngx/config.yaml` | HA add-on manifest with options schema |
| `paperless-ngx/redis.conf` | Minimal Redis broker-only config |
| `paperless-ngx/Dockerfile` | Debian base, apt deps, tarball install |
| `paperless-ngx/run.sh` | Env loading, Redis, migrations, Celery, Granian |
| `paperless-ngx/.env.example` | Configuration template for users |
| `paperless-ngx/README.md` | User-facing documentation |
| `paperless-ngx/CHANGELOG.md` | Initial changelog entry |
| `paperless-ngx/icon.png` | Already downloaded from reference repo |
| `paperless-ngx/logo.png` | Already downloaded from reference repo |
| `.github/workflows/deploy-paperless-ngx.yml` | CI/CD workflow (same pattern as other add-ons) |

---

### Task 1: Create config.yaml

**Files:**
- Create: `paperless-ngx/config.yaml`

- [ ] **Step 1: Create the config.yaml file**

```yaml
name: Paperless-ngx
description: >-
  Document management system that transforms physical documents
  into a searchable online archive.
version: "1.0.0"
slug: paperless-ngx
url: "https://github.com/maksyms/ha-addons"
arch:
  - aarch64
  - armv7
init: false
stdin: true
startup: application
boot: auto
map:
  - share:rw
  - addon_config:rw
ports:
  8000/tcp: 8000
ports_description:
  8000/tcp: Paperless-ngx web UI
options:
  PAPERLESS_ADMIN_USER: "admin"
  PAPERLESS_ADMIN_PASSWORD: ""
  PAPERLESS_OCR_LANGUAGE: "eng+rus"
  PAPERLESS_TIME_ZONE: ""
  TIKA_GOTENBERG_ENABLED: "false"
  TIKA_ENDPOINT: "http://localhost:9998"
  GOTENBERG_ENDPOINT: "http://localhost:3000"
schema:
  PAPERLESS_ADMIN_USER: str
  PAPERLESS_ADMIN_PASSWORD: str
  PAPERLESS_OCR_LANGUAGE: str?
  PAPERLESS_TIME_ZONE: str?
  TIKA_GOTENBERG_ENABLED: str?
  TIKA_ENDPOINT: str?
  GOTENBERG_ENDPOINT: str?
```

- [ ] **Step 2: Commit**

```bash
git add paperless-ngx/config.yaml
git commit -m "feat(paperless-ngx): add HA add-on manifest"
```

---

### Task 2: Create redis.conf

**Files:**
- Create: `paperless-ngx/redis.conf`

- [ ] **Step 1: Create the redis.conf file**

```
bind 127.0.0.1
port 6379
daemonize no
save ""
appendonly no
```

- [ ] **Step 2: Commit**

```bash
git add paperless-ngx/redis.conf
git commit -m "feat(paperless-ngx): add minimal Redis broker config"
```

---

### Task 3: Create Dockerfile

**Files:**
- Create: `paperless-ngx/Dockerfile`

- [ ] **Step 1: Create the Dockerfile**

```dockerfile
ARG BUILD_FROM=ghcr.io/hassio-addons/debian-base:9.2.0
FROM ${BUILD_FROM}

# System dependencies for paperless-ngx
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    redis-server \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus \
    imagemagick unpaper gnupg libpq5 libmagic1 \
    zlib1g-dev libzbar0 poppler-utils \
    jq gettext-base curl \
    && rm -rf /var/lib/apt/lists/*

# Download and install paperless-ngx from official release
ARG PAPERLESS_VERSION=2.20.10
RUN curl -fsSL "https://github.com/paperless-ngx/paperless-ngx/releases/download/v${PAPERLESS_VERSION}/paperless-ngx-v${PAPERLESS_VERSION}.tar.xz" \
    | tar -xJ -C /usr/src/ \
    && cd /usr/src/paperless-ngx \
    && pip install --no-cache-dir --break-system-packages -r requirements.txt \
    && python3 manage.py collectstatic --noinput

# NLTK data for document classification
RUN python3 -c "import nltk; nltk.download('snowball_data'); nltk.download('stopwords'); nltk.download('punkt_tab')"

# Minimal Redis config
COPY redis.conf /etc/redis/redis.conf

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
```

- [ ] **Step 2: Verify Dockerfile syntax**

Run: `docker run --rm -i hadolint/hadolint < paperless-ngx/Dockerfile || echo "hadolint not available, skipping"`

If hadolint is not available, visually confirm the Dockerfile matches the spec.

- [ ] **Step 3: Commit**

```bash
git add paperless-ngx/Dockerfile
git commit -m "feat(paperless-ngx): add Dockerfile with Debian base and tarball install"
```

---

### Task 4: Create run.sh

**Files:**
- Create: `paperless-ngx/run.sh`

- [ ] **Step 1: Create the run.sh file**

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Environment loading (same priority as other add-ons) ---
# 1. /share/paperless/.env (staging area)
# 2. /data/.env (persisted from previous run)
# 3. Generated from /data/options.json (HA UI)

if [ -f /share/paperless/.env ]; then
    cp /share/paperless/.env /data/.env
fi

if [ -f /data/.env ]; then
    set -a
    source /data/.env
    set +a
else
    CONFIG=/data/options.json
    for key in $(jq -r 'keys[]' "$CONFIG"); do
        value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
        export "$key=$value"
    done
fi

# --- Advanced config from paperless.conf ---
# Users can put any PAPERLESS_* setting here
CONF="/addon_configs/paperless_ngx/paperless.conf"
if [ -f "$CONF" ]; then
    set -a
    source "$CONF"
    set +a
fi

# --- Directories ---
export PAPERLESS_DATA_DIR="/addon_configs/paperless_ngx/data"
export PAPERLESS_MEDIA_ROOT="/share/paperless/media"
export PAPERLESS_CONSUMPTION_DIR="/share/paperless/consume"
mkdir -p "$PAPERLESS_DATA_DIR" "$PAPERLESS_MEDIA_ROOT" "$PAPERLESS_CONSUMPTION_DIR"

# --- Defaults ---
export PAPERLESS_REDIS="redis://localhost:6379"
export PAPERLESS_PORT="${PAPERLESS_PORT:-8000}"
export PAPERLESS_BIND_ADDR="${PAPERLESS_BIND_ADDR:-0.0.0.0}"

# --- Start Redis in background ---
redis-server /etc/redis/redis.conf --daemonize yes
echo "Redis started."

# --- Database migrations ---
cd /usr/src/paperless-ngx
python3 manage.py migrate --noinput
echo "Database migrations complete."

# --- Create superuser if needed ---
if [ -n "${PAPERLESS_ADMIN_USER:-}" ] && [ -n "${PAPERLESS_ADMIN_PASSWORD:-}" ]; then
    python3 manage.py manage_superuser
    echo "Admin user ensured."
fi

# --- Tika/Gotenberg integration ---
if [ "${TIKA_GOTENBERG_ENABLED:-false}" = "true" ]; then
    export PAPERLESS_TIKA_ENABLED="1"
    export PAPERLESS_TIKA_ENDPOINT="${TIKA_ENDPOINT:-http://localhost:9998}"
    export PAPERLESS_TIKA_GOTENBERG_ENDPOINT="${GOTENBERG_ENDPOINT:-http://localhost:3000}"
    echo "Tika/Gotenberg enabled: tika=${PAPERLESS_TIKA_ENDPOINT}, gotenberg=${PAPERLESS_TIKA_GOTENBERG_ENDPOINT}"
fi

# --- Start Celery worker + beat in background ---
celery -A paperless worker --loglevel=info &
celery -A paperless beat --loglevel=info &
echo "Celery worker and scheduler started."

# --- Start web server (foreground) ---
exec granian --interface asgi \
    --host "$PAPERLESS_BIND_ADDR" \
    --port "$PAPERLESS_PORT" \
    paperless.asgi:application
```

- [ ] **Step 2: Verify shell syntax**

Run: `bash -n paperless-ngx/run.sh`
Expected: no output (clean parse)

- [ ] **Step 3: Commit**

```bash
git add paperless-ngx/run.sh
git commit -m "feat(paperless-ngx): add run.sh with env loading and service orchestration"
```

---

### Task 5: Create .env.example

**Files:**
- Create: `paperless-ngx/.env.example`

- [ ] **Step 1: Create the .env.example file**

```bash
PAPERLESS_ADMIN_USER=admin
PAPERLESS_ADMIN_PASSWORD=changeme
PAPERLESS_OCR_LANGUAGE=eng+rus
PAPERLESS_TIME_ZONE=Europe/London
# Tika/Gotenberg (requires separate HA add-ons for Tika and Gotenberg)
TIKA_GOTENBERG_ENABLED=false
TIKA_ENDPOINT=http://localhost:9998
GOTENBERG_ENDPOINT=http://localhost:3000
# Advanced: any PAPERLESS_* var works. See:
# https://docs.paperless-ngx.com/configuration/
```

- [ ] **Step 2: Commit**

```bash
git add paperless-ngx/.env.example
git commit -m "feat(paperless-ngx): add .env.example"
```

---

### Task 6: Create README.md

**Files:**
- Create: `paperless-ngx/README.md`

- [ ] **Step 1: Create the README.md file**

```markdown
# Paperless-ngx - HA Add-on

A Home Assistant add-on for [paperless-ngx](https://docs.paperless-ngx.com/), a document management system that transforms physical documents into a searchable online archive.

## Installation

1. In Home Assistant: **Settings → Add-ons → Add-on Store → three-dot menu → Repositories**
2. Add this repository URL: `https://github.com/maksyms/ha-addons`
3. Click **Add**, then refresh
4. Find **Paperless-ngx** in the store and click **Install**

## Configuration

After installing the add-on, configure it via the **Configuration** tab in the HA UI, or place a `.env` file at `/share/paperless/.env`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `PAPERLESS_ADMIN_USER` | Yes | `admin` | Admin username |
| `PAPERLESS_ADMIN_PASSWORD` | Yes | — | Admin password |
| `PAPERLESS_OCR_LANGUAGE` | No | `eng+rus` | Tesseract OCR languages |
| `PAPERLESS_TIME_ZONE` | No | — | Timezone (e.g. `Europe/London`) |
| `TIKA_GOTENBERG_ENABLED` | No | `false` | Enable Tika/Gotenberg integration |
| `TIKA_ENDPOINT` | No | `http://localhost:9998` | Apache Tika endpoint |
| `GOTENBERG_ENDPOINT` | No | `http://localhost:3000` | Gotenberg endpoint |

### Advanced Configuration

Create `/addon_configs/paperless_ngx/paperless.conf` with any `PAPERLESS_*` environment variables. This file is sourced on startup after the HA UI options, so it can override or extend them.

See the [paperless-ngx configuration docs](https://docs.paperless-ngx.com/configuration/) for all available options.

### External Database

By default, paperless-ngx uses SQLite. To use an external PostgreSQL database, add to `paperless.conf`:

```
PAPERLESS_DBENGINE=postgresql
PAPERLESS_DBHOST=your-db-host
PAPERLESS_DBPORT=5432
PAPERLESS_DBNAME=paperless
PAPERLESS_DBUSER=paperless
PAPERLESS_DBPASS=your-password
```

### Tika/Gotenberg

For processing Office documents (Word, Excel, etc.), install separate Tika and Gotenberg HA add-ons, then enable the integration via the HA UI or `.env`:

```
TIKA_GOTENBERG_ENABLED=true
TIKA_ENDPOINT=http://your-tika-host:9998
GOTENBERG_ENDPOINT=http://your-gotenberg-host:3000
```

## Adding to HA Sidebar

Since this add-on uses direct port mapping (no ingress), add it to the HA sidebar via `configuration.yaml`:

```yaml
panel_iframe:
  paperless:
    title: "Paperless-ngx"
    icon: mdi:file-document-multiple
    url: "http://YOUR_HA_IP:8000"
```

## Data Storage

| Path | Contents |
|------|----------|
| `/addon_configs/paperless_ngx/data` | SQLite DB, search index |
| `/addon_configs/paperless_ngx/paperless.conf` | Advanced config |
| `/share/paperless/media` | Stored documents |
| `/share/paperless/consume` | Consumption inbox |

## Manual Deploy (Force)

For direct deployment bypassing the add-on store update mechanism, trigger the GitHub Actions workflow manually with `force_deploy: true`. This uses SCP + SSH to deploy files directly to the HA instance.

## License

Private / unlicensed.
```

- [ ] **Step 2: Commit**

```bash
git add paperless-ngx/README.md
git commit -m "feat(paperless-ngx): add README"
```

---

### Task 7: Create CHANGELOG.md

**Files:**
- Create: `paperless-ngx/CHANGELOG.md`

- [ ] **Step 1: Create the CHANGELOG.md file**

```markdown
## 1.0.0
- Initial release
- Paperless-ngx v2.20.10
- SQLite default, optional external PostgreSQL
- Tesseract OCR with English + Russian
- Tika/Gotenberg integration toggle
- Redis broker bundled in-container
```

- [ ] **Step 2: Commit with images**

The icon.png and logo.png files are already downloaded to `paperless-ngx/`. Commit them together with the changelog.

```bash
git add paperless-ngx/CHANGELOG.md paperless-ngx/icon.png paperless-ngx/logo.png
git commit -m "feat(paperless-ngx): add changelog and images"
```

---

### Task 8: Create CI/CD workflow

**Files:**
- Create: `.github/workflows/deploy-paperless-ngx.yml`

- [ ] **Step 1: Create the workflow file**

Copy the pattern from `.github/workflows/deploy-autoanalyst.yml`, replacing all `autoanalyst` references with `paperless-ngx` and updating the SCP file list.

```yaml
name: Deploy Paperless-ngx Add-on

on:
  push:
    branches: [master]
    paths:
      - 'paperless-ngx/**'
  workflow_dispatch:
    inputs:
      force_deploy:
        description: 'Force deploy via SCP + rebuild'
        required: false
        type: boolean
        default: false

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
          cd paperless-ngx
          current=$(grep '^version:' config.yaml | sed 's/version: *"\(.*\)"/\1/')
          IFS='.' read -r major minor patch <<< "$current"
          new_version="${major}.${minor}.$((patch + 1))"
          sed -i "s/^version: \"${current}\"/version: \"${new_version}\"/" config.yaml
          echo "VERSION=${new_version}" >> "$GITHUB_ENV"
          echo "PREV_VERSION=${current}" >> "$GITHUB_ENV"
          echo "Bumped version: ${current} → ${new_version}"

      - name: Generate changelog
        run: |
          # Find the previous version bump commit to get changes since then
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

          # Prepend new version entry to CHANGELOG.md
          CHANGELOG="paperless-ngx/CHANGELOG.md"
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
          git add paperless-ngx/config.yaml paperless-ngx/CHANGELOG.md
          git commit -m "Bump HAOS addon version to ${VERSION} [skip ci]"
          git pull --rebase
          git push

      # --- Force deploy path (SCP + rebuild) ---

      - name: Set up SSH
        if: github.event_name == 'workflow_dispatch' && inputs.force_deploy
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.HA_SSH_KEY }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          ssh-keyscan -p ${{ secrets.HA_SSH_PORT }} ${{ secrets.HA_SSH_HOST }} >> ~/.ssh/known_hosts 2>/dev/null

      - name: Force deploy to Home Assistant via SCP
        if: github.event_name == 'workflow_dispatch' && inputs.force_deploy
        run: |
          SSH_CMD="ssh -i ~/.ssh/deploy_key -p ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new"
          TARGET="${{ secrets.HA_SSH_USER }}@${{ secrets.HA_SSH_HOST }}"
          REMOTE_DIR="/addons/paperless-ngx"

          # Ensure remote directory exists
          $SSH_CMD "$TARGET" "mkdir -p ${REMOTE_DIR}"

          # Upload all add-on files
          scp -i ~/.ssh/deploy_key -P ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new \
            paperless-ngx/config.yaml \
            paperless-ngx/Dockerfile \
            paperless-ngx/run.sh \
            paperless-ngx/redis.conf \
            paperless-ngx/CHANGELOG.md \
            "${TARGET}:${REMOTE_DIR}/"

          echo "Deployed version ${VERSION} to ${TARGET}:${REMOTE_DIR}"

      - name: Rebuild and restart add-on
        if: github.event_name == 'workflow_dispatch' && inputs.force_deploy
        run: |
          SSH_CMD="ssh -i ~/.ssh/deploy_key -p ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new"
          TARGET="${{ secrets.HA_SSH_USER }}@${{ secrets.HA_SSH_HOST }}"

          $SSH_CMD "$TARGET" "ha apps rebuild local_paperless_ngx"
```

Note: The `ha apps rebuild` slug uses underscores (`local_paperless_ngx`) because HA normalizes slugs with hyphens to underscores in the local add-on namespace. Verify the exact slug after first install.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy-paperless-ngx.yml
git commit -m "ci(paperless-ngx): add deploy workflow"
```

---

### Task 9: Final verification

- [ ] **Step 1: Verify all files exist**

Run: `ls -la paperless-ngx/ && ls -la .github/workflows/deploy-paperless-ngx.yml`

Expected: all 9 files in `paperless-ngx/` (config.yaml, Dockerfile, run.sh, redis.conf, .env.example, README.md, CHANGELOG.md, icon.png, logo.png) plus the workflow file.

- [ ] **Step 2: Verify shell syntax**

Run: `bash -n paperless-ngx/run.sh`

Expected: no output (clean parse)

- [ ] **Step 3: Verify config.yaml parses as valid YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('paperless-ngx/config.yaml'))"`

Expected: no errors

- [ ] **Step 4: Verify workflow YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-paperless-ngx.yml'))"`

Expected: no errors

- [ ] **Step 5: Verify git status is clean**

Run: `git status`

Expected: nothing to commit, working tree clean
