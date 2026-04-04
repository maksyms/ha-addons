#!/usr/bin/env bash
set -euo pipefail

# Import .env from /share/youtube-sorter/ if present
if [ -f /share/youtube-sorter/.env ]; then
    cp /share/youtube-sorter/.env /data/.env
fi

if [ -f /data/.env ]; then
    set -a
    source /data/.env
    set +a
else
    # Fall back to add-on UI options: export each as an env var
    CONFIG=/data/options.json
    for key in $(jq -r 'keys[]' "$CONFIG"); do
        value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
        # Skip arrays/objects — handled by config.py reading options.json directly
        if [ "$value" != "null" ] && ! echo "$value" | jq -e 'type == "array" or type == "object"' >/dev/null 2>&1; then
            export "$key=$value"
        fi
    done
fi

cd /data
exec python3 -m sorter.main --options /data/options.json --db /data/youtube_sorter.db
