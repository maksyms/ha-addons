ARG BUILD_FROM=ghcr.io/hassio-addons/debian-base:9.2.0
FROM ${BUILD_FROM}

# System dependencies for paperless-ngx
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    build-essential pkg-config \
    redis-server \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus \
    imagemagick unpaper gnupg ghostscript qpdf pngquant jbig2dec \
    libpq-dev libmagic1 libxml2-dev libxslt1-dev \
    default-libmysqlclient-dev \
    zlib1g-dev libzbar0 poppler-utils \
    jq gettext-base curl xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Download and install paperless-ngx from official release
ARG PAPERLESS_VERSION=2.20.10
RUN curl -fsSL "https://github.com/paperless-ngx/paperless-ngx/releases/download/v${PAPERLESS_VERSION}/paperless-ngx-v${PAPERLESS_VERSION}.tar.xz" \
    | tar -xJ -C /usr/src/ \
    && cd /usr/src/paperless-ngx \
    && pip install --no-cache-dir --break-system-packages -r requirements.txt \
    && python3 manage.py collectstatic --noinput

# NLTK data for document classification
RUN python3 -c "import nltk; nltk.download('snowball_data'); nltk.download('stopwords'); nltk.download('punkt_tab')"

# Minimal Redis config
COPY redis.conf /etc/redis/redis.conf

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
