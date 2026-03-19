ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache nodejs npm python3 py3-pip jq git curl bash rclone ffmpeg

# OneDrive MCP server (https://github.com/MrFixit96/onedrive-mcp-server)
# Provides MCP tools for OneDrive file access via Microsoft Graph API
RUN pip install --no-cache-dir --break-system-packages onedrive-mcp-server yt-dlp

# Clone Claudegram at build time (always latest)
RUN git clone --depth 1 https://github.com/NachoSEO/claudegram.git /app/claudegram

WORKDIR /app/claudegram
RUN npm ci --ignore-scripts && npm run build

# Install Claude Code CLI globally (required by Agent SDK)
RUN npm install -g @anthropic-ai/claude-code

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
