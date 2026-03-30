# Tika-Gotenberg - HA Add-on

A Home Assistant add-on providing [Apache Tika](https://tika.apache.org/) and [Gotenberg](https://gotenberg.dev/) services for document text extraction. Designed as a companion to the Paperless-ngx add-on.

## Installation

1. In Home Assistant: **Settings > Add-ons > Add-on Store > three-dot menu > Repositories**
2. Add this repository URL: `https://github.com/maksyms/ha-addons`
3. Click **Add**, then refresh
4. Find **Tika-Gotenberg** in the store and click **Install**

## Configuration

No configuration needed. Just install and start the add-on.

### Connecting Paperless-ngx

In your Paperless-ngx add-on configuration (HA UI or `/addon_configs/paperless_ngx/paperless.conf`):

```
TIKA_GOTENBERG_ENABLED=true
TIKA_ENDPOINT=http://local-tika-gotenberg:9998
GOTENBERG_ENDPOINT=http://local-tika-gotenberg:3000
```

The hostname `local-tika-gotenberg` is how HA resolves local add-on containers. Verify the exact hostname after first install.

## Services

| Service | Port | Description |
|---------|------|-------------|
| Gotenberg | 3000 | PDF operations (minimal, no Chromium/LibreOffice) |
| Apache Tika | 9998 | Document text extraction |

Ports are internal only (not exposed to the host). Other HA add-ons access them via the Docker network.

## Manual Deploy (Force)

Trigger the GitHub Actions workflow manually with `force_deploy: true` for direct deployment via SCP + SSH.

## License

Private / unlicensed.
