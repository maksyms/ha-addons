## 1.0.9
- fix(tika-gotenberg): add python3-setuptools for unoconverter distutils compat
- fix(paperless-ngx): load options.json before .env so UI settings always apply

## 1.0.8
- fix(tika-gotenberg): disable OTLP exporters to stop metric upload errors
- fix(paperless-ngx): use single rclone copy with --files-from instead of per-file loop
- fix(paperless-ngx): fix rclone lsf stderr polluting file list

## 1.0.7
- fix(tika-gotenberg): use correct flag to disable Prometheus metrics
- fix(paperless-ngx): copy-once rclone sync to avoid re-downloading consumed files

## 1.0.6
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
- feat(paperless-gpt): switch to Anthropic Sonnet 4.6, fix startup DNS, expose more config
- feat(paperless-ngx): enable native HA ingress for sidebar entry
- fix(paperless-ngx): allow embedding in HA sidebar iframe
- fix(paperless-ngx): start document_consumer to process files in consume dir
- fix(paperless-ngx): persist database across rebuilds by moving data to /data/
- feat(paperless-ngx): add webui button to addon info page
- docs: add design spec for paperless-ngx sidebar link

## 1.0.5
- fix(tika-gotenberg): add missing Gotenberg deps and switch to build.yaml

## 1.0.4
- fix(tika-gotenberg): export tool paths in run.sh instead of Dockerfile ENV

## 1.0.3
- fix(tika-gotenberg): install Gotenberg module dependencies

## 1.0.2
- fix: add build.json for Debian-based add-ons
- docs: add MIT LICENSE and update README

## 1.0.1
- Merge master into main to reconcile branches
- ci(tika-gotenberg): add deploy workflow
- feat(tika-gotenberg): add changelog and icons
- feat(tika-gotenberg): add README
- feat(tika-gotenberg): add run.sh with Gotenberg and Tika startup
- feat(tika-gotenberg): add Dockerfile with Gotenberg binary and Tika JAR
- feat(tika-gotenberg): add HA add-on manifest
- docs: add tika-gotenberg add-on implementation plan
- docs: add tika-gotenberg add-on design spec
- ci(paperless-ngx): add deploy workflow

## 1.0.0
- Initial release
- Gotenberg v8 (minimal, no Chromium/LibreOffice)
- Apache Tika v3.1.0
- aarch64 only
