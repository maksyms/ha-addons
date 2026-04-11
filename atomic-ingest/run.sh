#!/usr/bin/env bash
set -euo pipefail

# --- Read HA options ---
OPTIONS="/data/options.json"

ATOMIC_API_URL=$(jq -r '.atomic_api_url // empty' "$OPTIONS")
ATOMIC_API_TOKEN=$(jq -r '.atomic_api_token // empty' "$OPTIONS")
LOG_LEVEL=$(jq -r '.log_level // "info"' "$OPTIONS")

export ATOMIC_API_URL
export ATOMIC_API_TOKEN
export LOG_LEVEL

# --- Source .env if present ---
if [[ -f /config/.env ]]; then
    echo "Loading /config/.env"
    set -a
    source /config/.env
    set +a
fi

# --- Validate required config ---
if [[ -z "${ATOMIC_API_URL:-}" ]]; then
    echo "ERROR: atomic_api_url is required (set in HA UI or /config/.env)"
    exit 1
fi
if [[ -z "${ATOMIC_API_TOKEN:-}" ]]; then
    echo "ERROR: atomic_api_token is required (set in HA UI or /config/.env)"
    exit 1
fi

# --- Create consume/processed dirs ---
mkdir -p /share/atomic-ingest/evernote/consume
mkdir -p /share/atomic-ingest/evernote/processed

# --- Dump env for cron jobs ---
# Cron doesn't inherit environment, so we dump to a file that each job sources.
ENV_FILE=/app/env.sh
{
    printf 'export ATOMIC_API_URL=%q\n' "${ATOMIC_API_URL}"
    printf 'export ATOMIC_API_TOKEN=%q\n' "${ATOMIC_API_TOKEN}"
    printf 'export LOG_LEVEL=%q\n' "${LOG_LEVEL}"
    printf 'export READWISE_API_TOKEN=%q\n' "${READWISE_API_TOKEN:-}"
    printf 'export RAINDROP_TOKEN=%q\n' "${RAINDROP_TOKEN:-}"
} > "$ENV_FILE"

# --- Generate crontab ---
READWISE_SCHEDULE="${READWISE_SCHEDULE:-0 * * * *}"
RAINDROP_SCHEDULE="${RAINDROP_SCHEDULE:-30 * * * *}"
EVERNOTE_SCHEDULE="${EVERNOTE_SCHEDULE:-0 3 * * *}"

CRONTAB_FILE=/etc/cron.d/atomic-ingest
cat > "$CRONTAB_FILE" <<EOF
${READWISE_SCHEDULE} root . /app/env.sh && cd /app && python -u adapters/readwise.py >> /proc/1/fd/1 2>&1
${RAINDROP_SCHEDULE} root . /app/env.sh && cd /app && python -u adapters/raindrop.py >> /proc/1/fd/1 2>&1
${EVERNOTE_SCHEDULE} root . /app/env.sh && cd /app && python -u adapters/evernote.py >> /proc/1/fd/1 2>&1
EOF

chmod 0644 "$CRONTAB_FILE"

echo "Crontab installed:"
cat "$CRONTAB_FILE"
echo ""
echo "Starting crond..."

# --- Exec crond as PID 1 ---
exec cron -f
