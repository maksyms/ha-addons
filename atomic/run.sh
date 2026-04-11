#!/usr/bin/env bash
set -euo pipefail

# --- Read HA options ---
OPTIONS="/data/options.json"

PUBLIC_URL=$(jq -r '.public_url // empty' "$OPTIONS")
RUST_LOG=$(jq -r '.rust_log // "warn"' "$OPTIONS")

export RUST_LOG

# --- Build atomic-server command ---
ATOMIC_CMD=(atomic-server --data-dir /data serve --bind 127.0.0.1 --port 8080)

if [[ -n "$PUBLIC_URL" ]]; then
    ATOMIC_CMD+=(--public-url "$PUBLIC_URL")
fi

# --- Start atomic-server in background ---
echo "Starting atomic-server..."
"${ATOMIC_CMD[@]}" &
ATOMIC_PID=$!

# --- Wait for atomic-server to be ready ---
echo "Waiting for atomic-server..."
READY=false
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo "atomic-server ready"
        READY=true
        break
    fi
    if ! kill -0 "$ATOMIC_PID" 2>/dev/null; then
        echo "atomic-server failed to start"
        exit 1
    fi
    sleep 1
done

if [[ "$READY" != "true" ]]; then
    echo "atomic-server did not become ready in 30 seconds"
    exit 1
fi

# --- Exec nginx as PID 1 ---
echo "Starting nginx..."
exec nginx -g "daemon off;"
