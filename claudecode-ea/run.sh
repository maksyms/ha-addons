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

    # Initial pull — use 'copy --update' (not 'sync') to avoid deleting
    # locally-created files (history/, memory.md) that haven't been pushed yet.
    echo "[rclone] Initial pull: ${REMOTE_PATH} -> ${LOCAL_PROJECTS}"
    rclone copy "$REMOTE_PATH" "$LOCAL_PROJECTS" --config "$RCLONE_CONF" \
        --update --stats-one-line -v 2>&1 || \
        echo "[rclone] WARNING: Initial pull failed, continuing anyway"

    # Background bidirectional sync loop.
    # Uses 'copy --update' both ways: newer files win, nothing is deleted.
    (
        while true; do
            sleep "$SYNC_INTERVAL"
            # Pull remote changes (newer remote files overwrite older local)
            rclone copy "$REMOTE_PATH" "$LOCAL_PROJECTS" --config "$RCLONE_CONF" \
                --update --quiet 2>&1 || true
            # Push local changes back (newer local files overwrite older remote)
            rclone copy "$LOCAL_PROJECTS" "$REMOTE_PATH" --config "$RCLONE_CONF" \
                --update --create-empty-src-dirs --quiet 2>&1 || true
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

# ── OneDrive MCP server config ───────────────────────────────────
if [ "${ONEDRIVE_MCP_ENABLED:-true}" = "true" ] && [ -n "${AZURE_CLIENT_ID:-}" ]; then
    # Register MCP server in Claude Code user settings
    mkdir -p /root/.claude
    cat > /root/.claude/settings.json <<MCPEOF
{
  "mcpServers": {
    "onedrive": {
      "command": "onedrive-mcp-server",
      "args": [],
      "env": {
        "AZURE_CLIENT_ID": "${AZURE_CLIENT_ID}",
        "ONEDRIVE_MCP_TOKEN_CACHE": "/data/onedrive-mcp-token-cache.json"
      }
    }
  }
}
MCPEOF
    echo "[mcp] OneDrive MCP server configured (MrFixit96/onedrive-mcp-server)"
else
    if [ -z "${AZURE_CLIENT_ID:-}" ]; then
        echo "[mcp] AZURE_CLIENT_ID not set, skipping OneDrive MCP server"
    fi
fi

# Tell Claudegram where to find the .env (it looks relative to config.ts by default).
export CLAUDEGRAM_ENV_PATH=/data/.env

# Run from /data so any state persists across restarts.
cd /data
exec node /app/claudegram/dist/index.js
