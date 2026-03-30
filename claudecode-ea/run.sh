#!/usr/bin/env bash
set -euo pipefail

# Always prefer .env from /share/claudecode-ea/ (user-managed staging area).
if [ -f /share/claudecode-ea/.env ]; then
    cp /share/claudecode-ea/.env /data/.env
fi

# If still no .env, generate one from HA UI options.
if [ ! -f /data/.env ] && [ -f /data/options.json ]; then
    CONFIG=/data/options.json
    for key in $(jq -r 'keys[]' "$CONFIG"); do
        value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
        # Only write non-empty values.
        [ -n "$value" ] && echo "${key}=${value}" >> /data/.env
    done
fi

# Source .env if it exists.
if [ -f /data/.env ]; then
    set -a
    source /data/.env
    set +a
fi

# Bypass Claude Code's root-user check — the container is already sandboxed.
export CLAUDE_CODE_BUBBLEWRAP="${CLAUDE_CODE_BUBBLEWRAP:-1}"

# ── OneDrive rclone sync ─────────────────────────────────────────
# bisync stores tracking files in $XDG_CACHE_HOME/rclone/bisync/.
# Point it to /data/ so state survives container restarts.
export XDG_CACHE_HOME="/data/.cache"

RCLONE_REMOTE="${RCLONE_REMOTE_NAME:-onedrive}"
RCLONE_CONF="${RCLONE_CONFIG_PATH:-}"
SYNC_INTERVAL="${RCLONE_SYNC_INTERVAL:-300}"
LOCAL_PROJECTS="/share/claudecode-ea/projects"

# Find rclone config
if [ -z "$RCLONE_CONF" ]; then
    if [ -f /share/claudecode-ea/rclone.conf ]; then
        RCLONE_CONF=/share/claudecode-ea/rclone.conf
    elif [ -f /data/rclone.conf ]; then
        RCLONE_CONF=/data/rclone.conf
    fi
fi

if [ -n "$ONEDRIVE_PROJECTS_PATH" ] && [ -n "$RCLONE_CONF" ]; then
    mkdir -p "$LOCAL_PROJECTS"
    REMOTE_PATH="${RCLONE_REMOTE}:${ONEDRIVE_PROJECTS_PATH}"
    BISYNC_FLAGS=(--config "$RCLONE_CONF" --create-empty-src-dirs --force)

    # bisync requires a one-time --resync to establish baseline.
    # The tracking files are stored in ~/.cache/rclone/bisync/ (persists via /data).
    BISYNC_MARKER="/data/.rclone-bisync-initialized"
    if [ ! -f "$BISYNC_MARKER" ]; then
        echo "[rclone] First run: initializing bisync baseline"
        rclone bisync "$REMOTE_PATH" "$LOCAL_PROJECTS" "${BISYNC_FLAGS[@]}" \
            --resync --stats-one-line -v 2>&1 || \
            echo "[rclone] WARNING: Initial bisync --resync failed, continuing anyway"
        touch "$BISYNC_MARKER"
    else
        echo "[rclone] Initial bisync: ${REMOTE_PATH} <-> ${LOCAL_PROJECTS}"
        if ! rclone bisync "$REMOTE_PATH" "$LOCAL_PROJECTS" "${BISYNC_FLAGS[@]}" \
            --stats-one-line -v 2>&1; then
            echo "[rclone] WARNING: bisync failed — listing files may be missing, retrying with --resync"
            rclone bisync "$REMOTE_PATH" "$LOCAL_PROJECTS" "${BISYNC_FLAGS[@]}" \
                --resync --stats-one-line -v 2>&1 || \
                echo "[rclone] WARNING: bisync --resync also failed, continuing anyway"
        fi
    fi

    # Background bidirectional sync loop.
    # bisync propagates creates, updates, AND deletes in both directions.
    (
        while true; do
            sleep "$SYNC_INTERVAL"
            if ! rclone bisync "$REMOTE_PATH" "$LOCAL_PROJECTS" "${BISYNC_FLAGS[@]}" \
                --quiet 2>&1; then
                echo "[rclone] Background bisync failed, retrying with --resync"
                rclone bisync "$REMOTE_PATH" "$LOCAL_PROJECTS" "${BISYNC_FLAGS[@]}" \
                    --resync --quiet 2>&1 || true
            fi
        done
    ) &

    # Point Claudegram at the synced folder
    export WORKSPACE_DIR="$LOCAL_PROJECTS"
    echo "[rclone] WORKSPACE_DIR=${LOCAL_PROJECTS}"
else
    if [ -z "$ONEDRIVE_PROJECTS_PATH" ]; then
        echo "[rclone] ONEDRIVE_PROJECTS_PATH not set, skipping OneDrive sync"
    fi
    if [ -z "$RCLONE_CONF" ]; then
        echo "[rclone] No rclone.conf found, skipping OneDrive sync"
    fi
fi

# ── MCP servers from mcp.d/ ──────────────────────────────────────
# Each JSON file defines one MCP server entry. Env vars (${FOO}) are
# substituted at runtime via envsubst; files with any empty value are skipped.
SETTINGS=/root/.claude/settings.json
mkdir -p /root/.claude

MCP_DIR=/app/mcp.d
if [ -d "$MCP_DIR" ]; then
    MERGED='{}'
    for f in "$MCP_DIR"/*.json; do
        [ -f "$f" ] || continue
        EXPANDED=$(envsubst < "$f")
        if echo "$EXPANDED" | jq -e '.. | strings | select(. == "")' >/dev/null 2>&1; then
            echo "[mcp] Skipping $(basename "$f"): missing required env vars"
            continue
        fi
        MERGED=$(echo "$MERGED" | jq --argjson srv "$EXPANDED" '. * $srv')
        echo "[mcp] Loaded $(basename "$f")"
    done
    if [ "$MERGED" != '{}' ]; then
        MCP_WRAP=$(echo "$MERGED" | jq '{mcpServers: .}')
        if [ -f "$SETTINGS" ]; then
            jq --argjson mcp "$MCP_WRAP" '. * $mcp' "$SETTINGS" > "${SETTINGS}.tmp" && mv "${SETTINGS}.tmp" "$SETTINGS"
        else
            echo "$MCP_WRAP" | jq . > "$SETTINGS"
        fi
    fi
fi

# Tell Claudegram where to find the .env (it looks relative to config.ts by default).
export CLAUDEGRAM_ENV_PATH=/data/.env

# Run from /data so any state persists across restarts.
cd /data
exec node /app/claudegram/dist/index.js
