## 1.0.13
- fix(autoanalyst): survive Telegram reconnect give-up instead of hanging
- fix(atomic-ingest): fix NoneType crash and duplicate URL detection
- feat(atomic-ingest): log skipped raindrop items to /share JSONL file
- feat(atomic-ingest): fallback atom creation for failed URL ingestion
- fix(atomic-ingest): add PATH to crontab for python3 in /usr/local/bin
- fix(atomic-ingest): use python3 in crontab entries
- chore: remove specs/plans from tracking, already gitignored
- chore: remove accidentally committed specs, gitignore future ones
- fix(justfile): use .data.addons[] instead of .data.apps[] in slug detection
- feat(atomic-ingest): add rate limiting, logging, and ingest limit framework
- docs(atomic-ingest): add README and update repo root README
- feat: add atomic-ingest HA add-on
- feat: add justfile with push, wait-and-update, and pushdeploy recipes
- fix(atomic): use container hostname in Caddyfile example
- feat(atomic): add Atomic knowledge base HA add-on
- fix(paperless-ngx): respect user-set FORCE_SCRIPT_NAME over ingress path
- fix(tika-gotenberg): add python3-uno for unoconverter LibreOffice bindings
- fix(tika-gotenberg): add python3-setuptools for unoconverter distutils compat
- fix(paperless-ngx): load options.json before .env so UI settings always apply
- fix(paperless-gpt): lower image file limit to 2.5MB for upstream resize bug headroom
- fix(paperless-gpt): cap pixel dimension to 7680 and lower file limit to 2.9MB
- fix(paperless-gpt): lower image limit to 3.9MB to account for base64 encoding overhead
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
- feat(paperless-gpt): switch to Anthropic Sonnet 4.6, fix startup DNS, expose more config
- feat(paperless-ngx): enable native HA ingress for sidebar entry
- fix(paperless-ngx): allow embedding in HA sidebar iframe
- fix(paperless-ngx): start document_consumer to process files in consume dir
- fix(paperless-ngx): persist database across rebuilds by moving data to /data/
- feat(paperless-ngx): add webui button to addon info page
- docs: add design spec for paperless-ngx sidebar link
- fix(paperless-ngx): unset empty PAPERLESS_TIME_ZONE to prevent Django crash
- fix(paperless-ngx): correct path to Django app in src/ subdirectory
- fix(paperless-ngx): add all build deps for pip install
- fix(paperless-ngx): add missing xz-utils for tar.xz extraction
- fix(tika-gotenberg): add missing Gotenberg deps and switch to build.yaml
- fix(tika-gotenberg): export tool paths in run.sh instead of Dockerfile ENV
- fix(tika-gotenberg): install Gotenberg module dependencies
- fix: add build.json for Debian-based add-ons
- docs: add MIT LICENSE and update README
- feat(paperless-gpt): add HA add-on wrapping icereed/paperless-gpt
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
- feat(paperless-ngx): add changelog and images
- feat(paperless-ngx): add README
- feat(paperless-ngx): add .env.example
- feat(paperless-ngx): add run.sh with env loading and service orchestration
- feat(paperless-ngx): add Dockerfile with Debian base and tarball install
- feat(paperless-ngx): add minimal Redis broker config
- feat(paperless-ngx): add HA add-on manifest
- docs: add paperless-ngx implementation plan
- docs: add Tika/Gotenberg toggle to paperless-ngx spec
- docs: add paperless-ngx add-on design spec
- feat(claudecode-ea): add incremental text streaming to Telegram
- docs: add design spec for Telegram text streaming in Claudegram
- fix(claudecode-ea): auto-resync rclone bisync when listing files are missing
- fix(claudecode-ea): switch to fork with session-switch fix
- feat(claudecode-ea): switch rclone to bisync for bidirectional delete propagation
- feat(claudecode-ea): add project switching and pairing flow
- feat(claudecode-ea): prototype native Claude Code Telegram channels
- feat(claudecode-ea): declarative config for plugins, MCP servers, and settings
- fix(claudecode-ea): sync empty project dirs to OneDrive with rclone
- fix(claudecode-ea): set init: false for s6-overlay compatibility
- fix(claudecode-ea): use s6-overlay service instead of CMD
- fix(claudecode-ea): install onedrive-mcp-server from GitHub
- Merge pull request #1 from maksyms/claude/add-dockerfile-dependencies-FArJD
- Add ffmpeg and yt-dlp dependencies to claudecode-ea Dockerfile
- feat(claudecode-ea): add OneDrive sync, MCP server, project templates
- docs: update CLAUDE.md for full repo, add personal assistant implementation plan
- Always prefer /share/ .env over cached /data/.env on start
- Bump claudecode-ea version to 1.0.1
- Split deploy workflows per add-on with path filters

## 1.0.12
- Fix env var names to match Claudegram upstream

## 1.0.11
- Add claudecode-ea add-on and reorganize READMEs

## 1.0.10
- Add add-on icon and logo (magnifying glass over X with alert badge)

## 1.0.9
- Add share mapping so add-on can read /share/autoanalyst/ for .env and session

## 1.0.8
- Import .env and session from /share/autoanalyst/ on first run

## 1.0.7
- Restructure as HA custom add-on repository

## 1.0.6
- Add auto-generated changelog from commit history on deploy
- Use 'ha apps' instead of deprecated 'ha addons' in deploy workflow

## 1.0.5
- Auto-rebuild add-on after deploy
- Fix deploy workflow rebase handling

## 1.0.4
- Add tweet image support for multimodal AI analysis
- Refine system prompt for deeper credibility and bias analysis

## 1.0.3
- Add GitHub Actions deploy pipeline
- Fix deploy workflow permissions

## 1.0.2
- Pick smallest video variant for transcription
- Fix fxtwitter 403 with User-Agent header

## 1.0.1
- Add video transcription support
- Add Perplexity as alternative analysis backend
- Add ANALYZE_OWN option

## 1.0.0
- Initial release
- Telegram monitoring for tweet links
- Claude-powered critical analysis
