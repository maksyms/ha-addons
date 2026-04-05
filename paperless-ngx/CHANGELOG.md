## 1.0.24
- fix(paperless-ngx): move consumer env vars before Celery worker starts
- fix(tika-gotenberg): disable OTLP exporters to stop metric upload errors

## 1.0.23
- fix(paperless-ngx): use single rclone copy with --files-from instead of per-file loop

## 1.0.22
- fix(paperless-ngx): fix rclone lsf stderr polluting file list
- fix(tika-gotenberg): use correct flag to disable Prometheus metrics

## 1.0.21
- fix(paperless-ngx): copy-once rclone sync to avoid re-downloading consumed files
- fix(tika-gotenberg): disable OTLP metrics to stop log spam

## 1.0.20
- fix(paperless-ngx): install latest rclone, fix OneDrive downloads
- fix(youtube-sorter): fix HTML entities in config.yaml, fix reorder stats
- ci(youtube-sorter): add deploy workflow
- feat(youtube-sorter): add web UI with Dracula theme
- feat(youtube-sorter): add orchestrator with scheduling
- feat(youtube-sorter): add AI classifier with batching
- feat(youtube-sorter): add innertube client for playlist mutations
- feat(youtube-sorter): add YouTube read layer with yt-dlp
- feat(youtube-sorter): add database layer with tests
- feat(youtube-sorter): scaffold add-on structure

## 1.0.19
- debug(paperless-ngx): add --dump headers to rclone diagnostic

## 1.0.18
- debug(paperless-ngx): rclone DEBUG log to file for diagnosis

## 1.0.17
- debug(paperless-ngx): enable rclone -vv on initial sync
- fix(youtube-sorter): fix HTML entities in config.yaml, fix reorder stats
- ci(youtube-sorter): add deploy workflow
- feat(youtube-sorter): add web UI with Dracula theme
- feat(youtube-sorter): add orchestrator with scheduling
- feat(youtube-sorter): add AI classifier with batching
- feat(youtube-sorter): add innertube client for playlist mutations
- feat(youtube-sorter): add YouTube read layer with yt-dlp
- feat(youtube-sorter): add database layer with tests
- feat(youtube-sorter): scaffold add-on structure
- docs: add implementation plan for youtube-sorter add-on

## 1.0.16
- feat(paperless-ngx): add duplicate deletion and OneDrive scanner sync
- docs: add design spec for youtube-sorter add-on
- feat(paperless-gpt): switch to Anthropic Sonnet 4.6, fix startup DNS, expose more config

## 1.0.15
- feat(paperless-ngx): enable native HA ingress for sidebar entry
- fix(paperless-ngx): allow embedding in HA sidebar iframe
- fix(paperless-ngx): start document_consumer to process files in consume dir
- fix(paperless-ngx): persist database across rebuilds by moving data to /data/
- feat(paperless-ngx): add webui button to addon info page
- docs: add design spec for paperless-ngx sidebar link

## 1.0.14
- fix(paperless-ngx): use with-contenv shebang for SUPERVISOR_TOKEN access

## 1.0.13
- debug(paperless-ngx): add SUPERVISOR_TOKEN and INGRESS_ENTRY logging

## 1.0.12
- fix(paperless-ngx): enable hassio_api for ingress FORCE_SCRIPT_NAME

## 1.0.11
- fix(paperless-ngx): re-expose port 8000 on host for debugging

## 1.0.10
- feat(paperless-ngx): enable native HA ingress for sidebar entry

## 1.0.9
- fix(paperless-ngx): allow embedding in HA sidebar iframe

## 1.0.8
- fix(paperless-ngx): start document_consumer to process files in consume dir

## 1.0.7
- fix(paperless-ngx): persist database across rebuilds by moving data to /data/

## 1.0.6
- feat(paperless-ngx): add webui button to addon info page
- docs: add design spec for paperless-ngx sidebar link

## 1.0.5
- fix(paperless-ngx): unset empty PAPERLESS_TIME_ZONE to prevent Django crash

## 1.0.4
- fix(paperless-ngx): correct path to Django app in src/ subdirectory

## 1.0.3
- fix(paperless-ngx): add all build deps for pip install

## 1.0.2
- fix(paperless-ngx): add missing xz-utils for tar.xz extraction

## 1.0.1
- fix(tika-gotenberg): add missing Gotenberg deps and switch to build.yaml
- fix(tika-gotenberg): export tool paths in run.sh instead of Dockerfile ENV
- fix(tika-gotenberg): install Gotenberg module dependencies
- fix: add build.json for Debian-based add-ons
- docs: add MIT LICENSE and update README
- feat(paperless-gpt): add HA add-on wrapping icereed/paperless-gpt

## 1.0.0
- Initial release
- Paperless-ngx v2.20.10
- SQLite default, optional external PostgreSQL
- Tesseract OCR with English + Russian
- Tika/Gotenberg integration toggle
- Redis broker bundled in-container
