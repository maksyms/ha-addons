## 1.1.2
- fix(claudecode-ea): auto-resync rclone bisync when listing files are missing

## 1.1.1
- fix(claudecode-ea): switch to fork with session-switch fix

## 1.0.11
- feat(claudecode-ea): switch rclone to bisync for bidirectional delete propagation

## 1.0.10
- feat(claudecode-ea): declarative config for plugins, MCP servers, and settings

## 1.0.9
- fix(claudecode-ea): sync empty project dirs to OneDrive with rclone

## 1.0.8
- fix(claudecode-ea): set init: false for s6-overlay compatibility

## 1.0.7
- fix(claudecode-ea): use s6-overlay service instead of CMD

## 1.0.6
- fix(claudecode-ea): install onedrive-mcp-server from GitHub

## 1.0.5
- Merge pull request #1 from maksyms/claude/add-dockerfile-dependencies-FArJD
- Add ffmpeg and yt-dlp dependencies to claudecode-ea Dockerfile

## 1.0.4
- feat(claudecode-ea): add OneDrive sync, MCP server, project templates
- docs: update CLAUDE.md for full repo, add personal assistant implementation plan

## 1.0.3
- Always prefer /share/ .env over cached /data/.env on start

## 1.0.2


## 1.0.0
- Initial release
- Wraps Claudegram (NachoSEO/claudegram) as HA add-on
- Clones Claudegram at Docker build time (always latest upstream)
- Three-tier env config: /share staging, /data/.env, options.json fallback
- Claude Code CLI installed globally for Agent SDK
