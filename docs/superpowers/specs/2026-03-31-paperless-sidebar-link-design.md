# Paperless-ngx: HA Sidebar Link

**Date:** 2026-03-31
**Scope:** Minimal — one config line

## Problem

The paperless-ngx addon has no "Open Web UI" button on the addon info page. Users must manually navigate to `http://<HA_IP>:8000`.

## Solution

Add the `webui` field to `paperless-ngx/config.yaml`:

```yaml
webui: "http://[HOST]:[PORT:8000]"
```

This gives the standard "Open Web UI" button on the addon's info page in HA.

The README already documents how to add a `panel_iframe` entry for a true sidebar link (lines 55-65), so no README changes are needed.

## Changes

| File | Change |
|------|--------|
| `paperless-ngx/config.yaml` | Add `webui: "http://[HOST]:[PORT:8000]"` |
