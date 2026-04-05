## 1.0.5
- fix(paperless-gpt): cap image size to 4.8MB to stay under Anthropic 5MB API limit
- fix(paperless-ngx): move consumer env vars before Celery worker starts
- fix(tika-gotenberg): disable OTLP exporters to stop metric upload errors
- fix(paperless-ngx): use single rclone copy with --files-from instead of per-file loop
- fix(paperless-ngx): fix rclone lsf stderr polluting file list
- fix(tika-gotenberg): use correct flag to disable Prometheus metrics
- fix(paperless-ngx): copy-once rclone sync to avoid re-downloading consumed files
- fix(tika-gotenberg): disable OTLP metrics to stop log spam
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
- docs: add implementation plan for youtube-sorter add-on
- feat(paperless-ngx): add duplicate deletion and OneDrive scanner sync
- docs: add design spec for youtube-sorter add-on

## 1.0.4
- feat(paperless-gpt): switch to Anthropic Sonnet 4.6, fix startup DNS, expose more config

## 1.0.3
- feat(paperless-ngx): enable native HA ingress for sidebar entry
- fix(paperless-ngx): allow embedding in HA sidebar iframe
- fix(paperless-ngx): start document_consumer to process files in consume dir
- fix(paperless-ngx): persist database across rebuilds by moving data to /data/
- feat(paperless-ngx): add webui button to addon info page
- docs: add design spec for paperless-ngx sidebar link
- fix(paperless-ngx): unset empty PAPERLESS_TIME_ZONE to prevent Django crash
- fix(paperless-ngx): correct path to Django app in src/ subdirectory
- fix(paperless-ngx): add all build deps for pip install

## 1.0.2
- fix(paperless-ngx): allow embedding in HA sidebar iframe
- fix(paperless-ngx): start document_consumer to process files in consume dir
- fix(paperless-ngx): persist database across rebuilds by moving data to /data/
- feat(paperless-ngx): add webui button to addon info page
- docs: add design spec for paperless-ngx sidebar link
- fix(paperless-ngx): unset empty PAPERLESS_TIME_ZONE to prevent Django crash
- fix(paperless-ngx): correct path to Django app in src/ subdirectory
- fix(paperless-ngx): add all build deps for pip install
- fix(paperless-ngx): add missing xz-utils for tar.xz extraction

## 1.0.1
- feat(paperless-gpt): add HA add-on wrapping icereed/paperless-gpt
- Merge master into main to reconcile branches
- ci(tika-gotenberg): add deploy workflow
- feat(tika-gotenberg): add changelog and icons
- feat(tika-gotenberg): add README
- feat(tika-gotenberg): add run.sh with Gotenberg and Tika startup
- feat(tika-gotenberg): add Dockerfile with Gotenberg binary and Tika JAR
- feat(tika-gotenberg): add HA add-on manifest
- docs: add tika-gotenberg add-on implementation plan

## 1.0.0

- Initial release
- Wraps icereed/paperless-gpt upstream image
- AI-powered title, tag, correspondent, and date generation
- LLM-enhanced OCR support
- Ingress support (HA sidebar)
- aarch64 + amd64
