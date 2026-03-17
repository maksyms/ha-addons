## 1.0.3
- Always prefer /share/ .env over cached /data/.env on start

## 1.0.2


## 1.0.0
- Initial release
- Wraps Claudegram (NachoSEO/claudegram) as HA add-on
- Clones Claudegram at Docker build time (always latest upstream)
- Three-tier env config: /share staging, /data/.env, options.json fallback
- Claude Code CLI installed globally for Agent SDK
