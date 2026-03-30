# Paperless-ngx - HA Add-on

A Home Assistant add-on for [paperless-ngx](https://docs.paperless-ngx.com/), a document management system that transforms physical documents into a searchable online archive.

## Installation

1. In Home Assistant: **Settings → Add-ons → Add-on Store → three-dot menu → Repositories**
2. Add this repository URL: `https://github.com/maksyms/ha-addons`
3. Click **Add**, then refresh
4. Find **Paperless-ngx** in the store and click **Install**

## Configuration

After installing the add-on, configure it via the **Configuration** tab in the HA UI, or place a `.env` file at `/share/paperless/.env`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `PAPERLESS_ADMIN_USER` | Yes | `admin` | Admin username |
| `PAPERLESS_ADMIN_PASSWORD` | Yes | — | Admin password |
| `PAPERLESS_OCR_LANGUAGE` | No | `eng+rus` | Tesseract OCR languages |
| `PAPERLESS_TIME_ZONE` | No | — | Timezone (e.g. `Europe/London`) |
| `TIKA_GOTENBERG_ENABLED` | No | `false` | Enable Tika/Gotenberg integration |
| `TIKA_ENDPOINT` | No | `http://localhost:9998` | Apache Tika endpoint |
| `GOTENBERG_ENDPOINT` | No | `http://localhost:3000` | Gotenberg endpoint |

### Advanced Configuration

Create `/addon_configs/paperless_ngx/paperless.conf` with any `PAPERLESS_*` environment variables. This file is sourced on startup after the HA UI options, so it can override or extend them.

See the [paperless-ngx configuration docs](https://docs.paperless-ngx.com/configuration/) for all available options.

### External Database

By default, paperless-ngx uses SQLite. To use an external PostgreSQL database, add to `paperless.conf`:

```
PAPERLESS_DBENGINE=postgresql
PAPERLESS_DBHOST=your-db-host
PAPERLESS_DBPORT=5432
PAPERLESS_DBNAME=paperless
PAPERLESS_DBUSER=paperless
PAPERLESS_DBPASS=your-password
```

### Tika/Gotenberg

For processing Office documents (Word, Excel, etc.), install separate Tika and Gotenberg HA add-ons, then enable the integration via the HA UI or `.env`:

```
TIKA_GOTENBERG_ENABLED=true
TIKA_ENDPOINT=http://your-tika-host:9998
GOTENBERG_ENDPOINT=http://your-gotenberg-host:3000
```

## Adding to HA Sidebar

Since this add-on uses direct port mapping (no ingress), add it to the HA sidebar via `configuration.yaml`:

```yaml
panel_iframe:
  paperless:
    title: "Paperless-ngx"
    icon: mdi:file-document-multiple
    url: "http://YOUR_HA_IP:8000"
```

## Data Storage

| Path | Contents |
|------|----------|
| `/addon_configs/paperless_ngx/data` | SQLite DB, search index |
| `/addon_configs/paperless_ngx/paperless.conf` | Advanced config |
| `/share/paperless/media` | Stored documents |
| `/share/paperless/consume` | Consumption inbox |

## Manual Deploy (Force)

For direct deployment bypassing the add-on store update mechanism, trigger the GitHub Actions workflow manually with `force_deploy: true`. This uses SCP + SSH to deploy files directly to the HA instance.

## License

Private / unlicensed.
