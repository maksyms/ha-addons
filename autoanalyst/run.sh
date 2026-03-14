#!/usr/bin/env bash
set -euo pipefail

if [ -f /app/.env ]; then
    # Use .env file bundled in the image — skip add-on options.
    cp /app/.env /data/.env
else
    # Fall back to add-on UI options: export each as an env var.
    CONFIG=/data/options.json
    for key in $(jq -r 'keys[]' "$CONFIG"); do
        value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
        export "$key=$value"
    done
fi

# Copy bundled session file to /data if not already there (first run).
if [ -f /app/autoanalyst.session ] && [ ! -f /data/autoanalyst.session ]; then
    cp /app/autoanalyst.session /data/autoanalyst.session
fi

# Run from /data so Telethon's session file persists across restarts.
cd /data
exec python3 /app/autoanalyst.py
