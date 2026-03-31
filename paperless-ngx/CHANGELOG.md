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
