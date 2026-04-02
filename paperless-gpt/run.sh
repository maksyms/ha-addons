#!/usr/bin/env bash
set -euo pipefail

# Convert HA options.json keys to UPPER_SNAKE_CASE env vars
for key in $(jq -r 'keys[]' /data/options.json); do
    value=$(jq -r --arg k "$key" '.[$k] | tostring' /data/options.json)
    upper_key=$(echo "$key" | tr '[:lower:]-' '[:upper:]_')
    [ -n "$value" ] && export "${upper_key}=${value}"
done

# Wait for paperless-ngx to be reachable before starting
PAPERLESS_URL="${PAPERLESS_BASE_URL:-}"
if [ -n "$PAPERLESS_URL" ]; then
    echo "Waiting for paperless-ngx at ${PAPERLESS_URL}..."
    retries=0
    until curl -sf -o /dev/null "${PAPERLESS_URL}/api/" 2>/dev/null; do
        retries=$((retries + 1))
        if [ $retries -ge 60 ]; then
            echo "WARNING: paperless-ngx not reachable after 60 attempts, starting anyway"
            break
        fi
        sleep 5
    done
    [ $retries -lt 60 ] && echo "paperless-ngx is reachable"
fi

echo "Starting paperless-gpt..."
exec /app/paperless-gpt
