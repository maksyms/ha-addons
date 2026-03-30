# Tika-Gotenberg HA Add-on Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a tika-gotenberg Home Assistant add-on as a companion to paperless-ngx, providing Apache Tika and Gotenberg services for document text extraction.

**Architecture:** Single-container add-on with Gotenberg binary copied from official Docker image, Tika JAR downloaded from Apache archive, both started as background processes by run.sh with `wait -n` foreground watchdog. No user configuration needed -- stateless service.

**Tech Stack:** Debian base (`hassio-addons/debian-base:9.2.0`), Gotenberg v8 (from official image), Apache Tika v3.1.0 (JAR), Java headless runtime

**Spec:** `docs/superpowers/specs/2026-03-30-tika-gotenberg-addon-design.md`

---

### File Structure

All new files.

| File | Purpose |
|------|---------|
| `tika-gotenberg/config.yaml` | HA add-on manifest (no options, internal ports) |
| `tika-gotenberg/Dockerfile` | Debian base, COPY --from gotenberg, Tika JAR download |
| `tika-gotenberg/run.sh` | Start Tika + Gotenberg, wait-n watchdog |
| `tika-gotenberg/README.md` | User-facing documentation |
| `tika-gotenberg/CHANGELOG.md` | Initial changelog entry |
| `tika-gotenberg/icon.png` | Gotenberg project logo |
| `tika-gotenberg/logo.png` | Gotenberg project logo |
| `.github/workflows/deploy-tika-gotenberg.yml` | CI/CD workflow (same pattern as other add-ons) |

---

### Task 1: Create config.yaml

**Files:**
- Create: `tika-gotenberg/config.yaml`

- [ ] **Step 1: Create the config.yaml file**

```yaml
name: Tika-Gotenberg
description: >-
  Apache Tika and Gotenberg services for document
  text extraction. Companion to Paperless-ngx.
version: "1.0.0"
slug: tika-gotenberg
url: "https://github.com/maksyms/ha-addons"
arch:
  - aarch64
init: false
stdin: true
startup: system
boot: auto
ports:
  3000/tcp: null
  9998/tcp: null
ports_description:
  3000/tcp: Gotenberg
  9998/tcp: Tika
```

- [ ] **Step 2: Commit**

```bash
git add tika-gotenberg/config.yaml
git commit -m "feat(tika-gotenberg): add HA add-on manifest"
```

---

### Task 2: Create Dockerfile

**Files:**
- Create: `tika-gotenberg/Dockerfile`

- [ ] **Step 1: Create the Dockerfile**

```dockerfile
ARG BUILD_FROM=ghcr.io/hassio-addons/debian-base:9.2.0
FROM ${BUILD_FROM}

ARG TIKA_VERSION=3.1.0

# Java runtime for Tika
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Gotenberg + pdfcpu binaries from official image
COPY --from=gotenberg/gotenberg:8 /usr/bin/gotenberg /usr/bin/gotenberg
COPY --from=gotenberg/gotenberg:8 /usr/bin/pdfcpu /usr/bin/pdfcpu

# Download Tika server JAR
RUN curl -fsSL "https://archive.apache.org/dist/tika/${TIKA_VERSION}/tika-server-standard-${TIKA_VERSION}.jar" \
    -o /usr/bin/tika-server-standard.jar

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
```

- [ ] **Step 2: Commit**

```bash
git add tika-gotenberg/Dockerfile
git commit -m "feat(tika-gotenberg): add Dockerfile with Gotenberg binary and Tika JAR"
```

---

### Task 3: Create run.sh

**Files:**
- Create: `tika-gotenberg/run.sh`

- [ ] **Step 1: Create the run.sh file**

```bash
#!/usr/bin/env bash
set -euo pipefail

# Start Gotenberg (background)
gotenberg --api-port=3000 --api-timeout=60s --log-level=info &
echo "Gotenberg started on port 3000."

# Start Tika (background)
java -cp "/usr/bin/tika-server-standard.jar" \
  org.apache.tika.server.core.TikaServerCli -h 0.0.0.0 &
echo "Tika started on port 9998."

# Keep container alive -- if either service exits, stop the container
# so the HA supervisor can restart it
wait -n
echo "A service exited unexpectedly, shutting down."
exit 1
```

- [ ] **Step 2: Verify shell syntax**

Run: `bash -n tika-gotenberg/run.sh`
Expected: no output (clean parse)

- [ ] **Step 3: Commit**

```bash
git add tika-gotenberg/run.sh
git commit -m "feat(tika-gotenberg): add run.sh with Gotenberg and Tika startup"
```

---

### Task 4: Create README.md

**Files:**
- Create: `tika-gotenberg/README.md`

- [ ] **Step 1: Create the README.md file**

```markdown
# Tika-Gotenberg - HA Add-on

A Home Assistant add-on providing [Apache Tika](https://tika.apache.org/) and [Gotenberg](https://gotenberg.dev/) services for document text extraction. Designed as a companion to the Paperless-ngx add-on.

## Installation

1. In Home Assistant: **Settings > Add-ons > Add-on Store > three-dot menu > Repositories**
2. Add this repository URL: `https://github.com/maksyms/ha-addons`
3. Click **Add**, then refresh
4. Find **Tika-Gotenberg** in the store and click **Install**

## Configuration

No configuration needed. Just install and start the add-on.

### Connecting Paperless-ngx

In your Paperless-ngx add-on configuration (HA UI or `/addon_configs/paperless_ngx/paperless.conf`):

```
TIKA_GOTENBERG_ENABLED=true
TIKA_ENDPOINT=http://local-tika-gotenberg:9998
GOTENBERG_ENDPOINT=http://local-tika-gotenberg:3000
```

The hostname `local-tika-gotenberg` is how HA resolves local add-on containers. Verify the exact hostname after first install.

## Services

| Service | Port | Description |
|---------|------|-------------|
| Gotenberg | 3000 | PDF operations (minimal, no Chromium/LibreOffice) |
| Apache Tika | 9998 | Document text extraction |

Ports are internal only (not exposed to the host). Other HA add-ons access them via the Docker network.

## Manual Deploy (Force)

Trigger the GitHub Actions workflow manually with `force_deploy: true` for direct deployment via SCP + SSH.

## License

Private / unlicensed.
```

- [ ] **Step 2: Commit**

```bash
git add tika-gotenberg/README.md
git commit -m "feat(tika-gotenberg): add README"
```

---

### Task 5: Create CHANGELOG.md and add icons

**Files:**
- Create: `tika-gotenberg/CHANGELOG.md`
- Create: `tika-gotenberg/icon.png`
- Create: `tika-gotenberg/logo.png`

- [ ] **Step 1: Create the CHANGELOG.md file**

```markdown
## 1.0.0
- Initial release
- Gotenberg v8 (minimal, no Chromium/LibreOffice)
- Apache Tika v3.1.0
- aarch64 only
```

- [ ] **Step 2: Copy the Gotenberg logo for icon.png and logo.png**

The Gotenberg logo has been downloaded to `/tmp/gotenberg-logo.png` (495x495 PNG).

```bash
cp /tmp/gotenberg-logo.png tika-gotenberg/icon.png
cp /tmp/gotenberg-logo.png tika-gotenberg/logo.png
```

- [ ] **Step 3: Commit**

```bash
git add tika-gotenberg/CHANGELOG.md tika-gotenberg/icon.png tika-gotenberg/logo.png
git commit -m "feat(tika-gotenberg): add changelog and icons"
```

---

### Task 6: Create CI/CD workflow

**Files:**
- Create: `.github/workflows/deploy-tika-gotenberg.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Deploy Tika-Gotenberg Add-on

on:
  push:
    branches: [master]
    paths:
      - 'tika-gotenberg/**'
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
          cd tika-gotenberg
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
          CHANGELOG="tika-gotenberg/CHANGELOG.md"
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
          git add tika-gotenberg/config.yaml tika-gotenberg/CHANGELOG.md
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
          REMOTE_DIR="/addons/tika-gotenberg"

          # Ensure remote directory exists
          $SSH_CMD "$TARGET" "mkdir -p ${REMOTE_DIR}"

          # Upload all add-on files
          scp -i ~/.ssh/deploy_key -P ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new \
            tika-gotenberg/config.yaml \
            tika-gotenberg/Dockerfile \
            tika-gotenberg/run.sh \
            tika-gotenberg/CHANGELOG.md \
            "${TARGET}:${REMOTE_DIR}/"

          echo "Deployed version ${VERSION} to ${TARGET}:${REMOTE_DIR}"

      - name: Rebuild and restart add-on
        if: github.event_name == 'workflow_dispatch' && inputs.force_deploy
        run: |
          SSH_CMD="ssh -i ~/.ssh/deploy_key -p ${{ secrets.HA_SSH_PORT }} -o StrictHostKeyChecking=accept-new"
          TARGET="${{ secrets.HA_SSH_USER }}@${{ secrets.HA_SSH_HOST }}"

          $SSH_CMD "$TARGET" "ha apps rebuild local_tika_gotenberg"
```

Note: The `ha apps rebuild` slug uses underscores (`local_tika_gotenberg`) because HA normalizes slugs with hyphens to underscores in the local add-on namespace. Verify the exact slug after first install.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy-tika-gotenberg.yml
git commit -m "ci(tika-gotenberg): add deploy workflow"
```

---

### Task 7: Final verification

- [ ] **Step 1: Verify all files exist**

Run: `ls -la tika-gotenberg/ && ls -la .github/workflows/deploy-tika-gotenberg.yml`

Expected: all 7 files in `tika-gotenberg/` (config.yaml, Dockerfile, run.sh, README.md, CHANGELOG.md, icon.png, logo.png) plus the workflow file.

- [ ] **Step 2: Verify shell syntax**

Run: `bash -n tika-gotenberg/run.sh`

Expected: no output (clean parse)

- [ ] **Step 3: Verify config.yaml parses as valid YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('tika-gotenberg/config.yaml'))"`

Expected: no errors

- [ ] **Step 4: Verify workflow YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-tika-gotenberg.yml'))"`

Expected: no errors

- [ ] **Step 5: Verify git status is clean**

Run: `git status`

Expected: nothing to commit, working tree clean
