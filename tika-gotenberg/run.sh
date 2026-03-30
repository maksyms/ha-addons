#!/usr/bin/env bash
set -euo pipefail

# Start Gotenberg (background)
gotenberg --api-port=3000 --api-timeout=60s --log-level=info &
echo "Gotenberg started on port 3000."

# Start Tika (background)
java -cp "/usr/bin/tika-server-standard.jar" \
  org.apache.tika.server.core.TikaServerCli -h 0.0.0.0 &
echo "Tika started on port 9998."

# Keep container alive -- if either service exits, stop the container
# so the HA supervisor can restart it
wait -n
echo "A service exited unexpectedly, shutting down."
exit 1
