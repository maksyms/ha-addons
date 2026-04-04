ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip jq

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY sorter/ ./sorter/
COPY static/ ./static/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
