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
