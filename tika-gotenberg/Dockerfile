ARG BUILD_FROM=ghcr.io/hassio-addons/debian-base:9.2.0
FROM ${BUILD_FROM}

ARG TIKA_VERSION=3.1.0

# Java runtime for Tika
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Gotenberg + pdfcpu binaries from official image
COPY --from=gotenberg/gotenberg:8 /usr/bin/gotenberg /usr/bin/gotenberg
COPY --from=gotenberg/gotenberg:8 /usr/bin/pdfcpu /usr/bin/pdfcpu

# Download Tika server JAR
RUN curl -fsSL "https://archive.apache.org/dist/tika/${TIKA_VERSION}/tika-server-standard-${TIKA_VERSION}.jar" \
    -o /usr/bin/tika-server-standard.jar

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
