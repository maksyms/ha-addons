FROM ghcr.io/kenforthewin/atomic:latest AS upstream

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx curl jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pre-built artifacts from upstream
COPY --from=upstream /usr/local/bin/atomic-server /usr/local/bin/
COPY --from=upstream /usr/share/nginx/html /usr/share/nginx/html

# nginx config from upstream — stays in sync with :latest
COPY --from=upstream /etc/nginx/conf.d/atomic.conf /etc/nginx/conf.d/atomic.conf

# Remove default nginx site
RUN rm -f /etc/nginx/sites-enabled/default

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8081
CMD ["/run.sh"]
