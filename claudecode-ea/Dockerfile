ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache nodejs npm python3 py3-pip jq git curl bash rclone ffmpeg gettext

# MCP server configs and their pip dependencies
COPY mcp.d/ /app/mcp.d/
RUN pip install --no-cache-dir --break-system-packages -r /app/mcp.d/requirements.txt yt-dlp

# Clone Claudegram from fork (includes session-switch fix: NachoSEO/claudegram#26)
RUN git clone --depth 1 https://github.com/maksyms/claudegram.git -b fix/clear-session-on-project-switch /app/claudegram

WORKDIR /app/claudegram
RUN npm ci --ignore-scripts && npm run build

# Install Claude Code CLI globally (required by Agent SDK)
RUN npm install -g @anthropic-ai/claude-code

# Claude Code default settings (plugins add enabledPlugins at build, MCP merges at runtime)
COPY settings.json /root/.claude/settings.json

# Install Claude Code plugins from plugins.txt
COPY plugins.txt /app/
RUN grep '^marketplace ' /app/plugins.txt | while read -r _ repo; do claude plugin marketplace add "$repo"; done && \
    grep '^install ' /app/plugins.txt | while read -r _ plugin; do claude plugin install "$plugin"; done

# Set up s6-overlay service (required for init: true in HA add-ons)
RUN mkdir -p /etc/services.d/claudegram
COPY run.sh /etc/services.d/claudegram/run
RUN chmod +x /etc/services.d/claudegram/run
