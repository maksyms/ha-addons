ARG BUILD_FROM=icereed/paperless-gpt:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache bash jq curl

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
