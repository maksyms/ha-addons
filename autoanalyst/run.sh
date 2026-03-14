#!/usr/bin/env bash
set -euo pipefail

# Import .env from /share/autoanalyst/ on first run (staging area).
if [ ! -f /data/.env ] && [ -f /share/autoanalyst/.env ]; then
    cp /share/autoanalyst/.env /data/.env
fi

if [ -f /data/.env ]; then
    # Use persisted .env file.
    set -a
    source /data/.env
    set +a
elif [ -f /app/.env ]; then
    # Use .env file bundled in the image.
    cp /app/.env /data/.env
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

# Import session from /share/autoanalyst/ on first run (staging area).
if [ ! -f /data/autoanalyst.session ] && [ -f /share/autoanalyst/autoanalyst.session ]; then
    cp /share/autoanalyst/autoanalyst.session /data/autoanalyst.session
fi

# Copy bundled session file to /data if not already there (first run).
if [ -f /app/autoanalyst.session ] && [ ! -f /data/autoanalyst.session ]; then
    cp /app/autoanalyst.session /data/autoanalyst.session
fi

# Run from /data so Telethon's session file persists across restarts.
cd /data
exec python3 /app/autoanalyst.py
