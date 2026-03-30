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
