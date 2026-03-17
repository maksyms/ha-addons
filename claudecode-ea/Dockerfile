ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache nodejs npm python3 py3-pip jq git curl bash

# Clone Claudegram at build time (always latest)
RUN git clone --depth 1 https://github.com/NachoSEO/claudegram.git /app/claudegram

WORKDIR /app/claudegram
RUN npm ci --ignore-scripts && npm run build

# Install Claude Code CLI globally (required by Agent SDK)
RUN npm install -g @anthropic-ai/claude-code

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
