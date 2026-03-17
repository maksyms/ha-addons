#!/usr/bin/env bash
set -euo pipefail

# Always prefer .env from /share/claudecode-ea/ (user-managed staging area).
if [ -f /share/claudecode-ea/.env ]; then
    cp /share/claudecode-ea/.env /data/.env
fi

# If still no .env, generate one from HA UI options.
if [ ! -f /data/.env ] && [ -f /data/options.json ]; then
    CONFIG=/data/options.json
    for key in $(jq -r 'keys[]' "$CONFIG"); do
        value=$(jq -r --arg k "$key" '.[$k]' "$CONFIG")
        # Only write non-empty values.
        [ -n "$value" ] && echo "${key}=${value}" >> /data/.env
    done
fi

# Source .env if it exists.
if [ -f /data/.env ]; then
    set -a
    source /data/.env
    set +a
fi

# Tell Claudegram where to find the .env (it looks relative to config.ts by default).
export CLAUDEGRAM_ENV_PATH=/data/.env

# Run from /data so any state persists across restarts.
cd /data
exec node /app/claudegram/dist/index.js
