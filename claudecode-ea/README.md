# Claude Code EA

A Home Assistant add-on that runs [Claudegram](https://github.com/NachoSEO/claudegram) — a Telegram bot bridging to Claude Code via the Agent SDK. Gives you an AI-powered executive assistant accessible through Telegram.

## How It Works

Claudegram is cloned from upstream at Docker build time, so each rebuild picks up the latest version automatically. The add-on installs the Claude Code CLI globally (required by the Agent SDK) and runs the Claudegram Node.js process.

## Configuration

Configure via the **Configuration** tab in the HA UI, or place a `.env` file in `/share/claudecode-ea/`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from [@BotFather](https://t.me/BotFather) |
| `ALLOWED_USER_IDS` | Yes | — | Comma-separated Telegram user IDs |
| `ANTHROPIC_API_KEY` | No | — | From https://console.anthropic.com (omit for Claude Max) |
| `DANGEROUS_MODE` | No | `false` | Allow Claude to execute arbitrary commands |
| `STREAMING_MODE` | No | `streaming` | `streaming` (live-updating) or `wait` (send when complete) |
| `BOT_NAME` | No | `Claudegram` | Custom name for the bot |
| `ONEDRIVE_PROJECTS_PATH` | No | — | OneDrive folder path to sync (e.g. `Documents/AI-Projects`) |
| `RCLONE_SYNC_INTERVAL` | No | `300` | Sync interval in seconds (default: 5 minutes) |
| `RCLONE_REMOTE_NAME` | No | `onedrive` | rclone remote name |
| `RCLONE_CONFIG_PATH` | No | auto | Path to rclone.conf (auto-detected from `/share/claudecode-ea/` or `/data/`) |
| `ONEDRIVE_MCP_ENABLED` | No | `true` | Enable OneDrive MCP server for on-demand file access |
| `AZURE_CLIENT_ID` | No | — | Azure app registration client ID for OneDrive MCP auth |
| `CLAUDE_CODE_BUBBLEWRAP` | No | `1` | Bypass root-user check (required for HA add-on) |

## First Run

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) and note the token
2. Get your Telegram user ID (e.g. via [@userinfobot](https://t.me/userinfobot))
3. Set `TELEGRAM_BOT_TOKEN`, `ALLOWED_USER_IDS`, and `ANTHROPIC_API_KEY` in the add-on config
4. **(Optional)** Set up rclone for OneDrive sync:
   - Install rclone locally: `brew install rclone` / `apt install rclone` / [rclone.org/install](https://rclone.org/install/)
   - Run `rclone config` → New remote → name it `onedrive` → type `onedrive` → follow the OAuth browser flow
   - Copy the config to HA: `scp ~/.config/rclone/rclone.conf root@<HA_IP>:/share/claudecode-ea/rclone.conf`
   - Set `ONEDRIVE_PROJECTS_PATH` to the folder you want to sync (e.g. `Documents/AI-Projects`)
   - Restart the add-on
5. Start the add-on and message your bot

## Multi-Project Setup

Claudegram's `/project` command lets you switch between projects in your `WORKSPACE_DIR`. Each project is a subdirectory with its own context:

- **`CLAUDE.md`** — project-specific instructions for Claude (see `templates/CLAUDE.md.template` for a starter)
- **`memory.md`** — persistent project knowledge (Claude updates this after each conversation)
- **`history/`** — conversation summaries (archived in `YYYY-MM-DD-HHMMSS.md` format)

When you switch projects or end a conversation, Claude automatically:
1. Saves a summary to `history/YYYY-MM-DD-HHMMSS.md`
2. Updates `memory.md` with new durable knowledge (facts, decisions, preferences)

This gives Claude long-term memory per project, even across sessions.

## OneDrive Integration

The add-on includes two OneDrive integrations:

### 1. rclone Sync (Bidirectional Background Sync)

When `ONEDRIVE_PROJECTS_PATH` is set, the add-on uses rclone to sync your OneDrive projects folder locally:

- **Initial pull** on startup (remote → local)
- **Bidirectional sync** every `RCLONE_SYNC_INTERVAL` seconds (default: 5 minutes)
- Uses `rclone copy --update` (newer files win, nothing is deleted)
- Local path is `/share/claudecode-ea/projects`, automatically set as `WORKSPACE_DIR`

**Setup rclone.conf:**

Configure rclone on a local machine (where you have a browser for OAuth), then copy the config to HA:

```bash
# 1. Install rclone locally (if not already installed)
#    macOS: brew install rclone
#    Linux: apt install rclone / see https://rclone.org/install/

# 2. Create the OneDrive remote
rclone config
# → n (New remote)
# → Name: onedrive
# → Storage: onedrive (Microsoft OneDrive)
# → client_id: (leave blank)
# → client_secret: (leave blank)
# → region: global
# → Edit advanced config: n
# → Auto config: y → sign in via browser
# → Drive type: onedrive (personal)
# → Confirm the drive shown → y

# 3. Verify it works
rclone lsd onedrive:YourProjectsFolder

# 4. Copy to HA
scp ~/.config/rclone/rclone.conf root@<HA_IP>:/share/claudecode-ea/rclone.conf

# 5. Restart the add-on
```

### 2. OneDrive MCP (On-Demand File Access)

When `AZURE_CLIENT_ID` is set, the add-on configures the [OneDrive MCP server](https://github.com/MrFixit96/onedrive-mcp-server) for on-demand access to files outside the synced folder:

- Browse, search, download, and edit OneDrive files via Claude
- Uses Microsoft Graph API with device-code auth
- Tokens are cached in `/data/onedrive-mcp-token-cache.json`

**Setup Azure App Registration:**
1. Go to [Azure Portal](https://portal.azure.com) → App registrations → New registration
2. Name: `Claude Code OneDrive MCP`
3. Supported account types: **Personal Microsoft accounts only**
4. Redirect URI: leave blank
5. After creation, copy the **Application (client) ID** → set as `AZURE_CLIENT_ID`
6. Go to **API permissions** → Add permission → Microsoft Graph → Delegated → `Files.ReadWrite.All`
7. Go to **Authentication** → Advanced settings → **Allow public client flows** → Yes

**First-run device auth:**
On first start, check the add-on logs. You'll see:
```
To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code XXXXXXXXX
```
Visit the URL, enter the code, and sign in. After that, auth is automatic.

## Claude Code Settings

Default Claude Code CLI settings are in `settings.json` (COPYed to `/root/.claude/settings.json` at build time). Plugins and MCP servers are merged into this file at build and runtime respectively.

```json
{
  "model": "opus",
  "effortLevel": "high"
}
```

To change the model or effort level, edit `settings.json` and rebuild.

## Claude Code Plugins

Plugins are installed at Docker build time from `plugins.txt`. Each line is either a `marketplace` or `install` directive:

```
marketplace kepano/obsidian-skills
install obsidian@obsidian-skills
```

To add a new plugin, edit `plugins.txt` and rebuild.

## MCP Servers

MCP server configs live in `mcp.d/`, one JSON file per server. At startup, `run.sh`:

1. Runs `envsubst` on each file to substitute env vars (e.g. `${AZURE_CLIENT_ID}`)
2. Skips files where any env value is empty (missing required var)
3. Merges all loaded servers into Claude Code's `settings.json`

**Adding a new MCP server:**

1. Create `mcp.d/myserver.json`:
   ```json
   {
     "myserver": {
       "command": "myserver-cmd",
       "args": [],
       "env": {
         "MY_API_KEY": "${MY_API_KEY}"
       }
     }
   }
   ```
2. If it needs a pip package, add it to `mcp.d/requirements.txt`
3. Set the required env vars in your `.env`

## Env File Staging

Place a `.env` file in `/share/claudecode-ea/` on the HA host. On startup, the add-on always prefers this file over the cached `/data/.env`. This is useful when migrating or setting up from a file rather than the UI.
