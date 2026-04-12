# Justfile Recipes for ha-addons

**Date:** 2026-04-11
**Status:** Approved

## Purpose

Provide `just` recipes that Claude can invoke to push code and deploy add-ons to Home Assistant. Three recipes covering the full workflow: push changes, wait for CI then update HA, and a combined recipe that does both.

## Design

### File

`justfile` at repo root.

### Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ha_host` | `192.168.0.14` | HA CLI SSH host |
| `ha_user` | `root` | HA CLI SSH user |
| `poll_interval` | `30` | CI poll frequency (seconds) |
| `ci_timeout` | `1800` | CI max wait time (seconds, default 30 min) |

All overridable via `just --set var value` or environment variables.

### Recipe: `push message`

Commits and pushes local changes, rebasing on top of any upstream changes.

**Steps:**
1. Check if working tree is dirty (`git status --porcelain`)
2. If dirty, `git stash`
3. `git pull --rebase`
4. If stashed, `git stash pop` (fail loudly on conflict)
5. `git add -A`
6. `git commit -m "{{message}}"`
7. `git push`

**Parameters:**
- `message` (required) — commit message string

**Example:**
```
just push "fix(autoanalyst): handle empty tweet bodies"
```

### Recipe: `wait-and-update addon`

Monitors the latest CI workflow run for the given add-on. On success, refreshes the HA add-on store and updates the app.

**Steps:**
1. Find latest workflow run for `deploy-{{addon}}.yml` on `master` via `gh run list --workflow "deploy-{{addon}}.yml" --branch master --limit 1 --json databaseId,status,conclusion`
2. Poll `gh run view <id> --json status,conclusion` every `poll_interval` seconds
3. If `status == "completed"` and `conclusion == "success"`:
   - SSH to HA CLI: `ssh {{ha_user}}@{{ha_host}}`
   - Run `ha store refresh`
   - Auto-detect slug: `ha apps list --raw-json | jq` filtering for addon name
   - Run `ha apps update <slug>`
4. If `conclusion != "success"` — print failure info and run URL, exit 1
5. If timeout exceeded — print timeout message, exit 1

**Parameters:**
- `addon` (required) — add-on directory name (e.g., `autoanalyst`, `claudecode-ea`, `atomic`)

**Example:**
```
just wait-and-update autoanalyst
```

### Recipe: `pushdeploy addon message`

Combines `push` and `wait-and-update` sequentially.

**Steps:**
1. `just push "{{message}}"`
2. `just wait-and-update "{{addon}}"`

**Parameters:**
- `addon` (required) — add-on directory name
- `message` (required) — commit message string

**Example:**
```
just pushdeploy autoanalyst "fix(autoanalyst): handle empty tweet bodies"
```

## HA Slug Auto-Detection

The HA app slug is detected at runtime by SSHing to the HA CLI and querying the app list:

```bash
ssh root@192.168.0.14 "ha apps list --raw-json" | jq -r '.data.apps[] | select(.slug | test("addon_name")) | .slug'
```

This avoids hardcoding slug naming conventions (e.g., `local_autoanalyst`) that could change.

## Error Handling

- **Stash pop conflicts:** Fail loudly. No auto-resolution.
- **Rebase conflicts:** Fail loudly. No auto-resolution.
- **CI failure:** Print the conclusion and a URL to the failed run.
- **CI timeout:** Print elapsed time and exit 1.
- **SSH failure:** Fail loudly from SSH exit code.
- **Slug not found:** Print error if grep/jq returns empty, exit 1.

## Claude Usage Instructions

Each recipe includes a doc-comment block explaining:
- What the recipe does
- Parameter descriptions
- Example invocations
- When to use each recipe

This ensures Claude can discover and correctly invoke the recipes by reading the justfile.
