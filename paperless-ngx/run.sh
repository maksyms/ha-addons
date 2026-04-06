#!/command/with-contenv bash
set -euo pipefail

# --- Environment loading ---
# options.json (HA UI) provides the base, then .env files override on top.
# This way UI settings always apply, even when .env exists for extras like rclone.

# 1. Load options.json as base (skip empty values so paperless-ngx uses defaults)
CONFIG=/data/options.json
for key in $(jq -r 'keys[]' "$CONFIG"); do
    value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
    [ -n "$value" ] && export "$key=$value"
done

# 2. .env overrides (staging area → persisted copy)
if [ -f /share/paperless/.env ]; then
    cp /share/paperless/.env /data/.env
fi
if [ -f /data/.env ]; then
    set -a
    source /data/.env
    set +a
fi

# --- Advanced config from paperless.conf ---
# Users can put any PAPERLESS_* setting here (addon_config slug uses hyphen)
CONF="/addon_configs/paperless-ngx/paperless.conf"
if [ -f "$CONF" ]; then
    set -a
    source "$CONF"
    set +a
fi

# --- Directories ---
# /data/ is HA's always-persistent add-on storage (survives rebuilds/updates)
# /share/ is shared across add-ons (documents accessible from host)
export PAPERLESS_DATA_DIR="/data/paperless-ngx"
export PAPERLESS_MEDIA_ROOT="/share/paperless/media"
export PAPERLESS_CONSUMPTION_DIR="/share/paperless/consume"
mkdir -p "$PAPERLESS_DATA_DIR" "$PAPERLESS_MEDIA_ROOT" "$PAPERLESS_CONSUMPTION_DIR"

# --- Unset empty optional vars so paperless-ngx uses its defaults ---
[ -z "${PAPERLESS_TIME_ZONE:-}" ] && unset PAPERLESS_TIME_ZONE
[ -z "${PAPERLESS_OCR_LANGUAGE:-}" ] && unset PAPERLESS_OCR_LANGUAGE

# --- Defaults ---
export PAPERLESS_REDIS="redis://localhost:6379"
export PAPERLESS_PORT="${PAPERLESS_PORT:-8000}"
export PAPERLESS_BIND_ADDR="${PAPERLESS_BIND_ADDR:-0.0.0.0}"

# --- Ingress subpath support ---
# HA ingress serves the addon under /api/hassio_ingress/<token>/
# Paperless-ngx needs FORCE_SCRIPT_NAME to generate correct URLs
if [ -n "${SUPERVISOR_TOKEN:-}" ]; then
    INGRESS_ENTRY=$(curl -s -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
        http://supervisor/addons/self/info | jq -r '.data.ingress_entry // empty')
    if [ -n "$INGRESS_ENTRY" ]; then
        export PAPERLESS_FORCE_SCRIPT_NAME="$INGRESS_ENTRY"
        echo "Ingress path: $INGRESS_ENTRY"
    fi
fi
# HA ingress proxy sets X-Forwarded-Host — Django uses it for CSRF validation
export PAPERLESS_USE_X_FORWARD_HOST=true
export PAPERLESS_USE_X_FORWARD_PORT=true

# --- Start Redis in background ---
redis-server /etc/redis/redis.conf --daemonize yes
echo "Redis started."

# --- Database migrations ---
cd /usr/src/paperless-ngx/src
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

# --- Consumer settings (must be set before Celery starts, since the worker
#     reads Django settings at import time) ---
# Use polling because inotify does not work reliably on Docker bind mounts.
export PAPERLESS_CONSUMER_POLLING=1
# Delete files from consume folder if they are duplicates of already-ingested documents.
export PAPERLESS_CONSUMER_DELETE_DUPLICATES="${PAPERLESS_CONSUMER_DELETE_DUPLICATES:-true}"

# --- Start Celery worker + beat in background ---
celery -A paperless worker --loglevel=info &
celery -A paperless beat --loglevel=info &
echo "Celery worker and scheduler started."

# --- OneDrive rclone one-way sync to consume folder ---
# Copies new files from OneDrive to PAPERLESS_CONSUMPTION_DIR.
# Each file is copied exactly once — tracked in a state file so files
# deleted by paperless after consumption are never re-downloaded.
# Source files on OneDrive are never deleted.
RCLONE_REMOTE="${RCLONE_REMOTE_NAME:-onedrive}"
RCLONE_CONF="${RCLONE_CONFIG_PATH:-}"
SYNC_INTERVAL="${RCLONE_SYNC_INTERVAL:-300}"
RCLONE_SEEN="${RCLONE_SEEN_FILE:-/data/rclone_seen.txt}"

# Find rclone config
if [ -z "$RCLONE_CONF" ]; then
    if [ -f /share/paperless/rclone.conf ]; then
        RCLONE_CONF=/share/paperless/rclone.conf
    elif [ -f /data/rclone.conf ]; then
        RCLONE_CONF=/data/rclone.conf
    fi
fi

# Copy only files not yet seen (tracked in RCLONE_SEEN state file).
rclone_copy_new() {
    local remote_path="$1" dest="$2" conf="$3" log_level="${4:---quiet}"
    touch "$RCLONE_SEEN"

    # List remote files, diff against seen file to find new ones
    local tmplist="/tmp/rclone_new_files.txt"
    rclone lsf "$remote_path" --config "$conf" --recursive 2>/dev/null \
        | grep -vxFf "$RCLONE_SEEN" > "$tmplist" || true

    local count
    count=$(wc -l < "$tmplist" | tr -d ' ')
    if [ "$count" -eq 0 ]; then
        echo "[rclone] No new files"
        rm -f "$tmplist"
        return 0
    fi

    echo "[rclone] Copying $count new file(s)..."
    if rclone copy "$remote_path" "$dest" \
            --config "$conf" --files-from "$tmplist" \
            $log_level; then
        cat "$tmplist" >> "$RCLONE_SEEN"
        echo "[rclone] Copied $count new file(s)"
    else
        echo "[rclone] WARNING: Copy failed, will retry next cycle"
    fi
    rm -f "$tmplist"
}

if [ -n "${RCLONE_SCANNER_PATH:-}" ] && [ -n "$RCLONE_CONF" ]; then
    REMOTE_PATH="${RCLONE_REMOTE}:${RCLONE_SCANNER_PATH}/"

    echo "[rclone] Initial sync: ${REMOTE_PATH} -> ${PAPERLESS_CONSUMPTION_DIR}"
    rclone_copy_new "$REMOTE_PATH" "$PAPERLESS_CONSUMPTION_DIR" "$RCLONE_CONF" "--stats-one-line -v" || \
        echo "[rclone] WARNING: Initial sync failed, continuing anyway"

    # Background sync loop
    (
        while true; do
            sleep "$SYNC_INTERVAL"
            rclone_copy_new "$REMOTE_PATH" "$PAPERLESS_CONSUMPTION_DIR" "$RCLONE_CONF" "--quiet" || \
                echo "[rclone] WARNING: Background sync failed"
        done
    ) &
    echo "[rclone] Background sync every ${SYNC_INTERVAL}s"
else
    if [ -z "${RCLONE_SCANNER_PATH:-}" ]; then
        echo "[rclone] RCLONE_SCANNER_PATH not set, skipping OneDrive sync"
    fi
    if [ -z "$RCLONE_CONF" ]; then
        echo "[rclone] No rclone.conf found, skipping OneDrive sync"
    fi
fi

# --- Start document consumer in background ---
# Watches PAPERLESS_CONSUMPTION_DIR for new files and triggers consume tasks.
python3 manage.py document_consumer &
echo "Document consumer started (polling mode)."

# --- Start web server (foreground) ---
exec granian --interface asgi \
    --host "$PAPERLESS_BIND_ADDR" \
    --port "$PAPERLESS_PORT" \
    paperless.asgi:application
