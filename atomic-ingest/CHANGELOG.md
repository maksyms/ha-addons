## 1.0.8
- feat(atomic-ingest): log skipped raindrop items to /share JSONL file

## 1.0.7
- feat(atomic-ingest): fallback atom creation for failed URL ingestion

## 1.0.6
- fix(atomic-ingest): add PATH to crontab for python3 in /usr/local/bin

## 1.0.5
- fix(atomic-ingest): use python3 in crontab entries

## 1.0.4
- chore: remove specs/plans from tracking, already gitignored
- chore: remove accidentally committed specs, gitignore future ones
- fix(justfile): use .data.addons[] instead of .data.apps[] in slug detection

## 1.0.3
- feat(atomic-ingest): add rate limiting, logging, and ingest limit framework

## 1.0.2
- docs(atomic-ingest): add README and update repo root README

## 1.0.1
- feat: add atomic-ingest HA add-on
- feat: add justfile with push, wait-and-update, and pushdeploy recipes
- fix(atomic): use container hostname in Caddyfile example
- feat(atomic): add Atomic knowledge base HA add-on
- fix(paperless-ngx): respect user-set FORCE_SCRIPT_NAME over ingress path
- fix(tika-gotenberg): add python3-uno for unoconverter LibreOffice bindings
