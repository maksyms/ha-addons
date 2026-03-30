#!/usr/bin/env bash
set -euo pipefail

# Convert HA options.json keys to UPPER_SNAKE_CASE env vars
for key in $(jq -r 'keys[]' /data/options.json); do
    value=$(jq -r --arg k "$key" '.[$k] | tostring' /data/options.json)
    upper_key=$(echo "$key" | tr '[:lower:]-' '[:upper:]_')
    [ -n "$value" ] && export "${upper_key}=${value}"
done

echo "Starting paperless-gpt..."
exec /app/paperless-gpt
