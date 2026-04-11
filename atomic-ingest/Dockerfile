FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lib/ lib/
COPY adapters/ adapters/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
