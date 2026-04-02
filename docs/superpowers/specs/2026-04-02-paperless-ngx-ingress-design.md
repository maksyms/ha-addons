# Paperless-ngx Native HA Ingress

**Date:** 2026-04-02
**Status:** Approved
**Supersedes:** 2026-03-31-paperless-sidebar-link-design.md (panel_iframe approach — removed from HA 2026.4.0)

## Problem

Paperless-ngx has no sidebar entry in HA. The previous `panel_iframe` YAML integration was removed in HA 2026.4.0. A manual Webpage dashboard works but requires X-Frame-Options patching and manual setup per user.

## Solution

Enable HA ingress on the paperless-ngx addon, matching the pattern already used by paperless-gpt. Paperless-ngx natively supports `PAPERLESS_FORCE_SCRIPT_NAME` for subpath routing, so no application patching is needed.

## Changes

### config.yaml

```yaml
# Add
ingress: true
ingress_port: 8000
panel_icon: mdi:file-document-multiple

# Change
ports:
  8000/tcp: null          # ingress-only; addon-to-addon via Docker network unaffected

# Remove
# webui: "http://[HOST]:[PORT:8000]"
```

### run.sh

**Add** (before the web server start, replacing the sed X-Frame-Options hack):

```bash
# --- Ingress subpath support ---
if [ -n "${SUPERVISOR_TOKEN:-}" ]; then
    INGRESS_ENTRY=$(curl -s -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
        http://supervisor/addons/self/info | jq -r '.data.ingress_entry // empty')
    if [ -n "$INGRESS_ENTRY" ]; then
        export PAPERLESS_FORCE_SCRIPT_NAME="$INGRESS_ENTRY"
    fi
fi
export PAPERLESS_USE_X_FORWARD_HOST=true
export PAPERLESS_USE_X_FORWARD_PORT=true
```

**Remove:**

```bash
sed -i 's/^X_FRAME_OPTIONS = .*/X_FRAME_OPTIONS = "ALLOWALL"/' /usr/src/paperless-ngx/src/paperless/settings.py
```

## How It Works

1. HA sees `ingress: true` + `panel_icon` → creates sidebar entry automatically
2. Browser clicks sidebar → HA frontend loads iframe at `/api/hassio_ingress/<token>/`
3. HA Supervisor proxies to addon container at `http://addon:8000/` (strips ingress prefix)
4. `PAPERLESS_FORCE_SCRIPT_NAME` makes Django generate URLs with the ingress prefix (login redirects, static files, API endpoints)
5. `X_FRAME_OPTIONS = "SAMEORIGIN"` works because the iframe and parent are both served from the HA origin
6. `USE_X_FORWARD_HOST` makes Django see the HA host in requests, so CSRF validation passes without hardcoding the HA URL

## What Stays Unchanged

- Addon-to-addon: paperless-gpt uses `http://23930cf1-paperless-ngx:8000` (Docker internal network, unaffected by ingress or port mapping)
- All other run.sh logic (env loading, Redis, migrations, Celery, document_consumer)
- paperless.conf advanced config mechanism
