#!/usr/bin/env bash
set -euo pipefail

# Import .env from /share/claudecode-ea/ on first run (staging area).
if [ ! -f /data/.env ] && [ -f /share/claudecode-ea/.env ]; then
    cp /share/claudecode-ea/.env /data/.env
fi

if [ -f /data/.env ]; then
    # Use persisted .env file.
    set -a
    source /data/.env
    set +a
elif [ -f /app/claudegram/.env ]; then
    # Use .env file bundled in the image.
    cp /app/claudegram/.env /data/.env
    set -a
    source /data/.env
    set +a
else
    # Fall back to add-on UI options: export each as an env var.
    CONFIG=/data/options.json
    for key in $(jq -r 'keys[]' "$CONFIG"); do
        value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
        export "$key=$value"
    done
fi

# Run from /data so any state persists across restarts.
cd /data
exec node /app/claudegram/dist/index.js
