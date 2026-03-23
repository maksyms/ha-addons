#!/usr/bin/env bash
set -euo pipefail

# ── Persistent Claude Code state ────────────────────────────────
# Symlink /root/.claude → /data/.claude so auth tokens, session data,
# and plugin state survive container restarts.
mkdir -p /data/.claude

# Preserve build-time settings.json and plugins before symlinking
if [ -f /root/.claude/settings.json ] && [ ! -f /data/.claude/settings.json ]; then
    cp /root/.claude/settings.json /data/.claude/settings.json
fi
if [ -d /root/.claude/plugins ] && [ ! -d /data/.claude/plugins ]; then
    cp -r /root/.claude/plugins /data/.claude/plugins
fi

rm -rf /root/.claude
ln -sf /data/.claude /root/.claude

# ── Load environment ────────────────────────────────────────────
# Always prefer .env from /share/claudecode-ea/ (user-managed staging area).
if [ -f /share/claudecode-ea/.env ]; then
    cp /share/claudecode-ea/.env /data/.env
fi

# If still no .env, generate one from HA UI options.
if [ ! -f /data/.env ] && [ -f /data/options.json ]; then
    CONFIG=/data/options.json
    for key in $(jq -r 'keys[]' "$CONFIG"); do
        value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
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

# ── Telegram bot token ──────────────────────────────────────────
# The Telegram channel plugin reads TELEGRAM_BOT_TOKEN from the env
# or from ~/.claude/channels/telegram/.env. Seed it if not configured yet.
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    mkdir -p /data/.claude/channels/telegram
    echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}" > /data/.claude/channels/telegram/.env
    echo "[telegram] Bot token configured"
fi

# ── Telegram access control ──────────────────────────────────────
# Pre-seed access.json so allowed users can message immediately
# without the interactive pairing flow.
TELEGRAM_DIR=/data/.claude/channels/telegram
mkdir -p "$TELEGRAM_DIR"
if [ -n "${ALLOWED_USER_IDS:-}" ]; then
    IDS_JSON=$(echo "$ALLOWED_USER_IDS" | tr ',' '\n' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//' | jq -R . | jq -s .)
    jq -n --argjson ids "$IDS_JSON" '{
        dmPolicy: "allowlist",
        allowFrom: $ids,
        groups: {},
        mentionPatterns: [],
        ackReaction: "\ud83d\udc40",
        replyToMode: "first",
        textChunkLimit: 4096,
        chunkMode: "newline"
    }' > "$TELEGRAM_DIR/access.json"
    echo "[telegram] Allowlist configured for $(echo "$IDS_JSON" | jq length) user(s)"
else
    echo "[telegram] No ALLOWED_USER_IDS — using pairing mode (check logs for code)"
fi

# ── Claude.ai authentication ───────────────────────────────────
# Channels require claude.ai login (not API key). On first start, Claude
# Code will print a device-code URL in the logs — visit it to authenticate.
# Auth tokens persist in /data/.claude/ across restarts.
#
# Alternatively, pre-seed auth from a local machine:
#   1. Run "claude auth login" locally (opens browser)
#   2. Copy ~/.claude/credentials* and ~/.claude/auth* to /share/claudecode-ea/claude-credentials/
#   3. Restart the add-on
if [ -d /share/claudecode-ea/claude-credentials ]; then
    cp -r /share/claudecode-ea/claude-credentials/* /data/.claude/ 2>/dev/null || true
    echo "[auth] Pre-seeded credentials from /share/claudecode-ea/claude-credentials/"
fi

# Check auth status
AUTH_STATUS=$(claude auth status 2>&1 || true)
if echo "$AUTH_STATUS" | grep -q '"loggedIn": true'; then
    echo "[auth] Claude Code authenticated"
else
    echo "[auth] ============================================"
    echo "[auth] NOT AUTHENTICATED"
    echo "[auth] Claude Code will attempt device-code login."
    echo "[auth] Check the add-on logs for the URL + code,"
    echo "[auth] then visit it in a browser to authenticate."
    echo "[auth] Auth persists across restarts once complete."
    echo "[auth] ============================================"
fi

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

if [ -n "${ONEDRIVE_PROJECTS_PATH:-}" ] && [ -n "$RCLONE_CONF" ]; then
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

    WORK_DIR="$LOCAL_PROJECTS"
    echo "[rclone] WORKSPACE_DIR=${LOCAL_PROJECTS}"
else
    if [ -z "${ONEDRIVE_PROJECTS_PATH:-}" ]; then
        echo "[rclone] ONEDRIVE_PROJECTS_PATH not set, skipping OneDrive sync"
    fi
    if [ -z "$RCLONE_CONF" ]; then
        echo "[rclone] No rclone.conf found, skipping OneDrive sync"
    fi
    WORK_DIR="/data"
fi

# ── Seed root CLAUDE.md for multi-project management ────────────
if [ "$WORK_DIR" != "/data" ] && [ ! -f "$WORK_DIR/CLAUDE.md" ]; then
    cp /app/templates/root-CLAUDE.md.template "$WORK_DIR/CLAUDE.md"
    echo "[projects] Seeded root CLAUDE.md in $WORK_DIR"
fi

# ── MCP servers from mcp.d/ ──────────────────────────────────────
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

# ── Build Claude Code CLI flags ─────────────────────────────────
CLAUDE_FLAGS=(
    --channels "plugin:telegram@claude-plugins-official"
    --verbose
)

# DANGEROUS_MODE maps to --dangerously-skip-permissions
if [ "${DANGEROUS_MODE:-false}" = "true" ]; then
    CLAUDE_FLAGS+=(--dangerously-skip-permissions)
    echo "[claude] DANGEROUS_MODE enabled: all tool permissions auto-approved"
fi

# ── Launch Claude Code ──────────────────────────────────────────
cd "$WORK_DIR"
echo "[claude] Starting Claude Code in ${WORK_DIR}"
echo "[claude] Flags: ${CLAUDE_FLAGS[*]}"
exec claude "${CLAUDE_FLAGS[@]}"
