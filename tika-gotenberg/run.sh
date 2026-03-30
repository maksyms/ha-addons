#!/usr/bin/env bash
set -euo pipefail

# Gotenberg needs to know where its module tools live
# (HA s6-overlay strips Dockerfile ENV vars, so set them here)
export CHROMIUM_BIN_PATH=/usr/bin/chromium
export LIBREOFFICE_BIN_PATH=/usr/bin/libreoffice
export EXIFTOOL_BIN_PATH=/usr/bin/exiftool
export PDFTK_BIN_PATH=/usr/bin/pdftk
export QPDF_BIN_PATH=/usr/bin/qpdf
export PDFCPU_BIN_PATH=/usr/bin/pdfcpu

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
