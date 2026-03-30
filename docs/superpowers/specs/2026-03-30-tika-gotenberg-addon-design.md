# Tika-Gotenberg HA Add-on Design Spec

**Date:** 2026-03-30
**Status:** Draft

## Goal

Add a tika-gotenberg add-on to the ha-addons repository as a companion to paperless-ngx. Provides Apache Tika (text extraction) and Gotenberg (PDF operations) as internal services that paperless-ngx connects to.

## Key Decisions

- **Base image:** `ghcr.io/hassio-addons/debian-base:9.2.0` (Debian, same as paperless-ngx)
- **Gotenberg binary:** Copied from official `gotenberg/gotenberg:8` image via `COPY --from` (no Go build)
- **Tika JAR:** Downloaded from Apache archive at build time (pinned v3.1.0)
- **Minimal Gotenberg:** No Chromium, no LibreOffice, no fonts -- PDF operations only
- **Architecture:** aarch64 only (official Gotenberg image doesn't publish armv7)
- **Ports:** 3000 (Gotenberg) and 9998 (Tika), mapped as `null` (internal only)
- **Stateless:** No persistent data, no user-configurable options, no volume maps
- **Process management:** Both services backgrounded, `wait -n` in foreground to catch exits
- **Icon/logo:** Gotenberg project logo (495x495 PNG)

## File Structure

```
tika-gotenberg/
├── config.yaml          # HA add-on manifest
├── Dockerfile           # Debian base, COPY --from gotenberg, Tika JAR download
├── run.sh               # Start Tika + Gotenberg, wait for exit
├── CHANGELOG.md         # Initial entry
├── README.md            # User docs
├── icon.png             # Gotenberg logo
└── logo.png             # Gotenberg logo

.github/workflows/
└── deploy-tika-gotenberg.yml  # CI/CD (same pattern as other add-ons)
```

## config.yaml

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

No `map`, no `options`, no `schema` -- this add-on is stateless. Ports are `null` (internal only, accessed by other add-ons on the HA Docker network).

`startup: system` so it starts before paperless-ngx (`startup: application`).

## Dockerfile

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

### Build notes

- Gotenberg binary copied from official multi-arch image (no Go toolchain needed)
- pdfcpu copied alongside Gotenberg (used by Gotenberg for PDF operations)
- No Chromium, LibreOffice, or fonts -- minimal for text extraction use case
- Tika version pinned as `ARG` for easy bumps
- Tika downloaded from archive.apache.org (stable URL, no signature verification for simplicity)
- `default-jre-headless` provides Java runtime for Tika (~150 MB)

## run.sh

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

### run.sh notes

- No env loading needed (no user-configurable options)
- No paperless.conf, no .env files, no options.json parsing
- Both services started in background
- `wait -n` blocks until either process exits, then exits non-zero so HA supervisor restarts the container
- Gotenberg listens on 0.0.0.0:3000 by default
- Tika listens on 0.0.0.0:9998 by default (Tika default port)

## Integration with Paperless-ngx

Paperless-ngx connects to this add-on using HA's internal Docker network hostnames. In the paperless-ngx add-on configuration:

```
TIKA_GOTENBERG_ENABLED=true
TIKA_ENDPOINT=http://local-tika-gotenberg:9998
GOTENBERG_ENDPOINT=http://local-tika-gotenberg:3000
```

The hostname `local-tika-gotenberg` is how HA resolves local add-on containers by slug (hyphens preserved). This should be verified after first install.

## CI/CD: deploy-tika-gotenberg.yml

Same pattern as `deploy-autoanalyst.yml` and `deploy-paperless-ngx.yml`:
- Trigger: push to `master` with `paths: ['tika-gotenberg/**']`
- `workflow_dispatch` with `force_deploy` option
- Auto-bump patch version in `tika-gotenberg/config.yaml`
- Generate changelog from git log since last version bump
- Commit with `[skip ci]`
- Optional SCP force deploy to HA host

## What's NOT Included (vs reference repo)

- No Chromium / Google Chrome (no HTML-to-PDF)
- No LibreOffice / unoconverter (no Office-to-PDF)
- No fonts (no rendering)
- No s6-overlay service tree (simple background processes)
- No multi-stage Go build (binary copied from official image)
- No gotenberg user (runs as root per HA convention)
- No signature verification for Tika JAR (simplicity)
- No amd64 or armv7 support
- No pdftk, qpdf, exiftool (not needed without LibreOffice/Chromium)
- pdfcpu IS included (copied alongside Gotenberg, used for PDF operations)
