ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache nodejs npm python3 py3-pip jq git curl bash rclone ffmpeg gettext

# Install Bun (required by Claude Code channel plugins)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# MCP server configs and their pip dependencies
COPY mcp.d/ /app/mcp.d/
RUN pip install --no-cache-dir --break-system-packages -r /app/mcp.d/requirements.txt yt-dlp

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Claude Code default settings (plugins add enabledPlugins at build, MCP merges at runtime)
COPY settings.json /root/.claude/settings.json

# Install Claude Code plugins (including Telegram channel) from plugins.txt
COPY plugins.txt /app/
RUN grep '^marketplace ' /app/plugins.txt | while read -r _ repo; do claude plugin marketplace add "$repo"; done && \
    grep '^install ' /app/plugins.txt | while read -r _ plugin; do claude plugin install "$plugin"; done

# Project templates (root CLAUDE.md, per-project CLAUDE.md, memory.md)
COPY templates/ /app/templates/

# Set up s6-overlay service
RUN mkdir -p /etc/services.d/claudecode
COPY run.sh /etc/services.d/claudecode/run
RUN chmod +x /etc/services.d/claudecode/run
