# claudecode-ea Personal Assistant Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform claudecode-ea into a multi-project personal assistant with OneDrive integration, conversation history, and project memory.

**Architecture:** Claudegram's built-in `/project` command sets cwd and loads per-project `CLAUDE.md` — no fork needed. A specific OneDrive folder is rclone-synced (using `rclone copy --update` both ways to avoid data loss) as `WORKSPACE_DIR` for projects. Other OneDrive files are accessible on-demand via [MrFixit96/onedrive-mcp-server](https://github.com/MrFixit96/onedrive-mcp-server) (Python, MIT, device-code auth, 6 tools, 47 tests) registered in Claude Code's user settings. `CLAUDE_CODE_BUBBLEWRAP=1` fixes the root/DANGEROUS_MODE issue.

**Tech Stack:** Shell (run.sh), Dockerfile (Alpine/apk), rclone (OneDrive sync), Python (OneDrive MCP server — pip install), Markdown (CLAUDE.md templates)

**Key design choices:**
- `rclone copy --update` (not `rclone sync`) for both pull and push — prevents deletion of locally-created files (history, memory) before they're pushed
- `init: true` in config.yaml — ensures Docker uses tini as PID 1 to properly reap the background rclone sync process
- OneDrive MCP via [MrFixit96/onedrive-mcp-server](https://github.com/MrFixit96/onedrive-mcp-server) — lightweight Python server with device-code auth (one-time browser auth, then headless forever), registered via `~/.claude/settings.json`. **Needs runtime verification (Task 7a).** Fallback: rclone CLI instructions in CLAUDE.md.

---

## File Structure

```
claudecode-ea/
  .env.example              # MODIFY — comprehensive config based on Claudegram's, with our extensions
  run.sh                    # MODIFY — add BUBBLEWRAP, rclone sync, WORKSPACE_DIR, MCP config
  Dockerfile                # MODIFY — add rclone, pip install onedrive-mcp-server
  config.yaml               # MODIFY — add new options (ONEDRIVE_PROJECTS_PATH, RCLONE_SYNC_INTERVAL, etc.)
  templates/                # CREATE — project templates
    CLAUDE.md.template      # Per-project CLAUDE.md template with history/memory instructions
  README.md                 # MODIFY — document new features
  CHANGELOG.md              # MODIFY — document changes
```

---

### Task 1: Comprehensive .env.example

**Files:**
- Modify: `claudecode-ea/.env.example`

Use Claudegram's well-commented .env.example as the base. Extend with claudecode-ea-specific variables. Preserve all original Claudegram comments.

- [ ] **Step 1: Read current .env.example and Claudegram's**

Current file: `claudecode-ea/.env.example`
Reference: Claudegram's .env.example at https://github.com/NachoSEO/claudegram/blob/main/.env.example
Alternatively, after Docker build it's at `/app/claudegram/.env.example` inside the container.

- [ ] **Step 2: Write new .env.example**

Start with Claudegram's full .env.example verbatim (all sections, all comments), then append a new section:

```bash
# ══════════════════════════════════════════════════════════════════
# claudecode-ea Add-on Extensions
# ══════════════════════════════════════════════════════════════════

# ── Docker / Runtime ──────────────────────────────────────────────
# Bypass Claude Code's root-user check inside the HA add-on container.
# The container is already sandboxed, so this is safe.
# Required for DANGEROUS_MODE to work in HA add-ons (which run as root).
CLAUDE_CODE_BUBBLEWRAP=1

# ── OneDrive Sync (rclone) ───────────────────────────────────────
# rclone remote name for OneDrive (configured in rclone.conf)
# Default: onedrive
# RCLONE_REMOTE_NAME=onedrive

# OneDrive folder path to sync as WORKSPACE_DIR (your projects root).
# This folder and all its contents are synced locally every RCLONE_SYNC_INTERVAL.
# Example: "Documents/AI-Projects" syncs onedrive:Documents/AI-Projects
ONEDRIVE_PROJECTS_PATH=

# How often to sync the projects folder, in seconds.
# Default: 300 (5 minutes)
# RCLONE_SYNC_INTERVAL=300

# Path to rclone config file.
# Default: /data/rclone.conf
# You can also place it at /share/claudecode-ea/rclone.conf for easy editing.
# RCLONE_CONFIG_PATH=/data/rclone.conf

# ── OneDrive MCP (on-demand access) ──────────────────────────────
# Enable the OneDrive MCP server for on-demand access to files
# outside the synced projects folder (browse, search, download, edit).
# Uses MrFixit96/onedrive-mcp-server with Microsoft Graph API.
# Default: true
# ONEDRIVE_MCP_ENABLED=true

# Azure App Registration client ID for OneDrive MCP device-code auth.
# Create a free app registration at https://portal.azure.com → App registrations.
# Required permissions: Files.ReadWrite.All (delegated).
# On first start, the add-on log will show a URL + code — visit the URL and enter the code.
# After that, auth is fully automatic (tokens cached in /data/).
# AZURE_CLIENT_ID=
```

Also ensure `WORKSPACE_DIR` in the Claudegram section is commented to explain our usage:

```bash
# Root directory for /project picker.
# In claudecode-ea, this is auto-set to the rclone-synced OneDrive folder.
# Override only if you want a different projects root.
# WORKSPACE_DIR=/share/claudecode-ea/projects
```

- [ ] **Step 3: Commit**

```bash
git add claudecode-ea/.env.example
git commit -m "feat(claudecode-ea): comprehensive .env.example based on Claudegram upstream"
```

---

### Task 2: Fix DANGEROUS_MODE (root user bypass)

**Files:**
- Modify: `claudecode-ea/run.sh`

- [ ] **Step 1: Add CLAUDE_CODE_BUBBLEWRAP=1 to run.sh**

Add this line after the `.env` sourcing block but before the `exec` line. Only set it if not already defined (so .env can override):

```bash
# Bypass Claude Code's root-user check — the container is already sandboxed.
export CLAUDE_CODE_BUBBLEWRAP="${CLAUDE_CODE_BUBBLEWRAP:-1}"
```

- [ ] **Step 2: Verify run.sh is correct**

Read the complete run.sh and confirm the line is in the right place — after sourcing .env, before `cd /data` and `exec node`.

- [ ] **Step 3: Commit**

```bash
git add claudecode-ea/run.sh
git commit -m "fix(claudecode-ea): bypass Claude Code root check with CLAUDE_CODE_BUBBLEWRAP"
```

---

### Task 3: Add rclone and OneDrive MCP server to Dockerfile

**Files:**
- Modify: `claudecode-ea/Dockerfile`

- [ ] **Step 1: Add rclone and onedrive-mcp-server installation**

Add rclone to the `apk add` line, then pip-install the OneDrive MCP server:

```dockerfile
RUN apk add --no-cache nodejs npm python3 py3-pip jq git curl bash rclone

# Install OneDrive MCP server (https://github.com/MrFixit96/onedrive-mcp-server)
# Provides 6 MCP tools: list_files, search_files, get_file_metadata, upload_file, download_file, create_sharing_link
# Uses Microsoft Graph API with device-code auth (one-time browser auth, then headless)
RUN pip install --no-cache-dir --break-system-packages onedrive-mcp-server
```

(rclone is in Alpine's community repo, enabled by default in HA base images. The MCP server is a pure Python package on PyPI.)

- [ ] **Step 2: Verify Dockerfile builds conceptually**

Read the full Dockerfile to confirm both additions don't break existing build steps. The `--break-system-packages` flag is needed on Alpine 3.18+ where pip is externally managed.

- [ ] **Step 3: Commit**

```bash
git add claudecode-ea/Dockerfile
git commit -m "feat(claudecode-ea): add rclone and onedrive-mcp-server"
```

---

### Task 4: rclone sync in run.sh

**Files:**
- Modify: `claudecode-ea/run.sh`

- [ ] **Step 1: Add rclone sync logic to run.sh**

After sourcing .env and before the final `exec`, add a background sync loop. The sync should:
1. Look for rclone.conf in `/share/claudecode-ea/rclone.conf` first, then `/data/rclone.conf`
2. Do an initial pull before starting Claudegram (so projects are available immediately)
3. Start a background loop that syncs every `RCLONE_SYNC_INTERVAL` seconds (default 300)
4. Sync bidirectionally using `rclone copy --update` (NOT `rclone sync` — sync deletes local files not on remote, destroying history/memory files before they're pushed)
5. Set `WORKSPACE_DIR` to the local sync target

Add after the BUBBLEWRAP line, before `cd /data`:

```bash
# ── OneDrive rclone sync ─────────────────────────────────────────
RCLONE_REMOTE="${RCLONE_REMOTE_NAME:-onedrive}"
RCLONE_CONF="${RCLONE_CONFIG_PATH:-}"
SYNC_INTERVAL="${RCLONE_SYNC_INTERVAL:-300}"
LOCAL_PROJECTS="/share/claudecode-ea/projects"

# Find rclone config
if [ -z "$RCLONE_CONF" ]; then
    if [ -f /share/claudecode-ea/rclone.conf ]; then
        RCLONE_CONF=/share/claudecode-ea/rclone.conf
    elif [ -f /data/rclone.conf ]; then
        RCLONE_CONF=/data/rclone.conf
    fi
fi

if [ -n "$ONEDRIVE_PROJECTS_PATH" ] && [ -n "$RCLONE_CONF" ]; then
    mkdir -p "$LOCAL_PROJECTS"
    REMOTE_PATH="${RCLONE_REMOTE}:${ONEDRIVE_PROJECTS_PATH}"

    # Initial pull — use 'copy --update' (not 'sync') to avoid deleting
    # locally-created files (history/, memory.md) that haven't been pushed yet.
    echo "[rclone] Initial pull: ${REMOTE_PATH} -> ${LOCAL_PROJECTS}"
    rclone copy "$REMOTE_PATH" "$LOCAL_PROJECTS" --config "$RCLONE_CONF" \
        --update --stats-one-line -v 2>&1 || \
        echo "[rclone] WARNING: Initial pull failed, continuing anyway"

    # Background bidirectional sync loop.
    # Uses 'copy --update' both ways: newer files win, nothing is deleted.
    (
        while true; do
            sleep "$SYNC_INTERVAL"
            # Pull remote changes (newer remote files overwrite older local)
            rclone copy "$REMOTE_PATH" "$LOCAL_PROJECTS" --config "$RCLONE_CONF" \
                --update --quiet 2>&1 || true
            # Push local changes back (newer local files overwrite older remote)
            rclone copy "$LOCAL_PROJECTS" "$REMOTE_PATH" --config "$RCLONE_CONF" \
                --update --quiet 2>&1 || true
        done
    ) &

    # Point Claudegram at the synced folder
    export WORKSPACE_DIR="$LOCAL_PROJECTS"
    echo "[rclone] WORKSPACE_DIR=${LOCAL_PROJECTS}"
else
    if [ -z "$ONEDRIVE_PROJECTS_PATH" ]; then
        echo "[rclone] ONEDRIVE_PROJECTS_PATH not set, skipping OneDrive sync"
    fi
    if [ -z "$RCLONE_CONF" ]; then
        echo "[rclone] No rclone.conf found, skipping OneDrive sync"
    fi
fi
```

**Note on `copy --update` vs `sync`:** `rclone copy --update` only copies files where the source is newer. It never deletes files at the destination. This is critical because Claude creates local files (history logs, memory.md updates) that don't exist on OneDrive yet — `rclone sync` would delete them before the push cycle runs.

- [ ] **Step 2: Verify the complete run.sh reads correctly**

Read full run.sh. Confirm ordering: .env sourcing → BUBBLEWRAP → rclone sync → cd /data → exec node.

- [ ] **Step 3: Commit**

```bash
git add claudecode-ea/run.sh
git commit -m "feat(claudecode-ea): add rclone OneDrive sync with background refresh"
```

---

### Task 5: Update config.yaml with new options

**Files:**
- Modify: `claudecode-ea/config.yaml`

- [ ] **Step 1: Add new options to config.yaml**

Add the OneDrive-related options to the HA add-on config. Also change `init: false` to `init: true` so Docker uses tini as PID 1 — this properly reaps the background rclone sync process when the container stops.

```yaml
init: true
# ...
options:
  TELEGRAM_BOT_TOKEN: ""
  ALLOWED_USER_IDS: ""
  ANTHROPIC_API_KEY: ""
  DANGEROUS_MODE: "false"
  STREAMING_MODE: "streaming"
  BOT_NAME: ""
  ONEDRIVE_PROJECTS_PATH: ""
  RCLONE_SYNC_INTERVAL: "300"
  ONEDRIVE_MCP_ENABLED: "true"
  AZURE_CLIENT_ID: ""
schema:
  TELEGRAM_BOT_TOKEN: str
  ALLOWED_USER_IDS: str
  ANTHROPIC_API_KEY: str
  DANGEROUS_MODE: str?
  STREAMING_MODE: str?
  BOT_NAME: str?
  ONEDRIVE_PROJECTS_PATH: str?
  RCLONE_SYNC_INTERVAL: str?
  ONEDRIVE_MCP_ENABLED: str?
  AZURE_CLIENT_ID: str?
```

- [ ] **Step 2: Commit**

```bash
git add claudecode-ea/config.yaml
git commit -m "feat(claudecode-ea): add OneDrive config options to HA UI"
```

---

### Task 6: Per-project CLAUDE.md template with history and memory

**Files:**
- Create: `claudecode-ea/templates/CLAUDE.md.template`

This template is what users place in each project folder (e.g., `health/CLAUDE.md`). It instructs Claude to:
1. Save conversation summaries to `history/` subfolder after each meaningful exchange
2. Condense insights into `memory.md` to persist across conversations
3. Read `memory.md` at the start of each conversation to restore context

- [ ] **Step 1: Create the template**

```markdown
# [PROJECT_NAME] Project

## About This Project
<!-- Describe what this project is about, your goals, and any important context -->

## Instructions
- You are my personal assistant for the [PROJECT_NAME] project.
- Read `memory.md` in this directory at the start of every conversation for accumulated context.
- Be concise but thorough. Ask clarifying questions when my intent is unclear.

## Conversation History
After each conversation (when I switch projects or say goodbye):
1. Save a summary to `history/YYYY-MM-DD-HHMMSS.md` with:
   - Date and brief topic
   - Key decisions made
   - Action items identified
   - Any unresolved questions
2. Update `memory.md` with any new durable knowledge:
   - Important facts, decisions, preferences, or conclusions
   - Remove or update anything that has become outdated
   - Keep it concise — this is a working document, not a log

## Files
- `memory.md` — persistent project memory (updated each conversation)
- `history/` — conversation summaries (append-only archive)
- Other `.md` files — project-specific documents you create or I provide
```

- [ ] **Step 2: Create a starter memory.md template**

Create `claudecode-ea/templates/memory.md.template`:

```markdown
# [PROJECT_NAME] Memory

<!-- This file is automatically maintained by your AI assistant. -->
<!-- It accumulates durable knowledge across conversations. -->

## Key Facts

## Decisions Made

## Preferences

## Open Questions
```

- [ ] **Step 3: Commit**

```bash
git add claudecode-ea/templates/
git commit -m "feat(claudecode-ea): add per-project CLAUDE.md and memory.md templates"
```

---

### Task 7: OneDrive MCP server (MrFixit96/onedrive-mcp-server)

**Files:**
- Modify: `claudecode-ea/run.sh` (configure MCP server + initial auth instructions)

Uses the existing [MrFixit96/onedrive-mcp-server](https://github.com/MrFixit96/onedrive-mcp-server) package (already pip-installed in Task 3). This is a Python MCP server using Microsoft Graph API with device-code OAuth2 auth. It provides 6 tools: `list_files`, `search_files`, `get_file_metadata`, `upload_file`, `download_file`, `create_sharing_link`. Security-hardened with error sanitization and audit logging. 47 tests.

**Auth flow:** Device code flow — on first run, the server prints a URL and a code. The user visits the URL on any browser (phone, laptop), enters the code, and authorizes. Tokens are cached to `~/.config/onedrive-mcp/token_cache.json` and auto-refresh silently. After initial auth, it runs fully headless.

**MCP registration:** Configured via `~/.claude/settings.json` so the Agent SDK discovers it.

**Risk:** The Agent SDK may not discover MCP servers from settings.json. Task 7a verifies this. Fallback: rclone CLI instructions in CLAUDE.md.

- [ ] **Step 7a: Verify MCP server discovery via Agent SDK**

Before configuring the MCP server, verify that Claude Code's Agent SDK actually discovers and spawns MCP servers from `~/.claude/settings.json`. Test by:
1. Deploy the add-on with the pip-installed `onedrive-mcp-server`
2. Register it in `~/.claude/settings.json` inside the container (see Step 2 below)
3. Send a message via Claudegram asking Claude to list available MCP tools
4. If Claude sees the OneDrive MCP tools → this approach works
5. If not → implement the fallback (rclone CLI instructions in CLAUDE.md)

This step is manual/exploratory and blocks Step 2. If verification fails, skip to the fallback.

- [ ] **Step 1: Determine the MCP server command**

The pip-installed package should provide a console script entry point. Check what command it installs:

```bash
# Inside the container, after pip install:
which onedrive-mcp-server || pip show onedrive-mcp-server | grep -i location
# Or check: python -m onedrive_mcp_server
```

The command will be something like `onedrive-mcp-server` or `python -m onedrive_mcp_server`.

- [ ] **Step 2: Configure MCP server in run.sh**

After the rclone sync block, add MCP server registration. The server needs:
- `AZURE_CLIENT_ID` — Azure app registration client ID for device-code auth
- Token cache path — must be on a persistent volume (`/data/`)

```bash
# ── OneDrive MCP server config ───────────────────────────────────
if [ "${ONEDRIVE_MCP_ENABLED:-true}" = "true" ]; then
    # Ensure token cache persists across container restarts
    export ONEDRIVE_MCP_TOKEN_CACHE="/data/onedrive-mcp-token-cache.json"

    # Register MCP server in Claude Code user settings
    mkdir -p /root/.claude
    cat > /root/.claude/settings.json <<MCPEOF
{
  "mcpServers": {
    "onedrive": {
      "command": "onedrive-mcp-server",
      "args": [],
      "env": {
        "AZURE_CLIENT_ID": "${AZURE_CLIENT_ID:-}",
        "ONEDRIVE_MCP_TOKEN_CACHE": "/data/onedrive-mcp-token-cache.json"
      }
    }
  }
}
MCPEOF
    echo "[mcp] OneDrive MCP server configured (MrFixit96/onedrive-mcp-server)"
fi
```

**Note:** The exact env vars and command name need to be confirmed from the package's docs/source. The `AZURE_CLIENT_ID` is required for device-code auth — the user must create an Azure app registration (free) and provide this ID.

- [ ] **Step 3: Update .env.example with Azure/MCP config**

Add to the claudecode-ea extensions section in `.env.example`:

```bash
# ── OneDrive MCP (on-demand access) ──────────────────────────────
# Enable the OneDrive MCP server for on-demand access to files
# outside the synced projects folder (browse, search, download, edit).
# Uses MrFixit96/onedrive-mcp-server with Microsoft Graph API.
# Default: true
# ONEDRIVE_MCP_ENABLED=true

# Azure App Registration client ID for OneDrive MCP device-code auth.
# Create a free app registration at https://portal.azure.com → App registrations.
# Required permissions: Files.ReadWrite.All (delegated).
# On first start, the add-on log will show a URL + code — visit the URL and enter the code
# to authorize. After that, auth is fully automatic.
# AZURE_CLIENT_ID=
```

- [ ] **Step 4: Commit**

```bash
git add claudecode-ea/run.sh claudecode-ea/.env.example
git commit -m "feat(claudecode-ea): configure OneDrive MCP server (MrFixit96/onedrive-mcp-server)"
```

**Fallback (if Step 7a fails — Agent SDK does not discover MCP from settings.json):**

Instead of MCP, add rclone CLI instructions to the CLAUDE.md template. Since DANGEROUS_MODE is enabled, Claude can run rclone commands directly via Bash:

Add this section to `claudecode-ea/templates/CLAUDE.md.template`:

```markdown
## OneDrive Access
You have access to OneDrive files via the `rclone` CLI. The rclone config is at the path in $RCLONE_CONFIG_PATH.
The remote is named per $RCLONE_REMOTE_NAME (default: `onedrive`).

Common commands:
- List files: `rclone lsjson onedrive:Documents --config /data/rclone.conf`
- Search: `rclone lsjson onedrive:Documents --recursive --max-depth 5 --include "*.pdf" --config /data/rclone.conf`
- Download: `rclone copy onedrive:path/to/file.md /tmp/ --config /data/rclone.conf && cat /tmp/file.md`
- Upload: `rclone copyto /tmp/file.md onedrive:path/to/file.md --config /data/rclone.conf`
```

---

### Task 8: Update README.md

**Files:**
- Modify: `claudecode-ea/README.md`

- [ ] **Step 1: Update README with new features**

Add sections covering:
- OneDrive integration (rclone sync + MCP)
- Project setup (CLAUDE.md template, memory.md)
- Conversation history and memory
- rclone configuration guide (how to set up rclone.conf for OneDrive)
- New env vars

- [ ] **Step 2: Commit**

```bash
git add claudecode-ea/README.md
git commit -m "docs(claudecode-ea): document OneDrive integration and project features"
```

---

## Task Dependencies

```
Task 1 (.env.example) ─────────────────┐
Task 2 (BUBBLEWRAP fix) ───────────────┤
Task 3 (rclone + MCP pip in Dockerfile)┤── all independent, can parallelize
Task 5 (config.yaml + init:true) ──────┤
Task 6 (CLAUDE.md template) ───────────┘
                                        │
Task 4 (rclone sync in run.sh) ────────┤── depends on Task 2 + Task 3
                                        │
Task 7a (verify MCP discovery) ────────┤── manual/exploratory, depends on Task 4
Task 7 (MCP config in run.sh) ─────────┤── depends on Task 7a passing
  OR Task 7-fallback (rclone CLAUDE.md)┤── if Task 7a fails, update Task 6 template
                                        │
Task 8 (README) ────────────────────────┘── depends on all above
```

**Parallel batch 1:** Tasks 1, 2, 3, 5, 6 (all independent)
**Sequential batch 2:** Task 4 (needs run.sh from Task 2 + Dockerfile from Task 3)
**Gate:** Task 7a — manual verification of MCP discovery via Agent SDK
**Sequential batch 3:** Task 7 or Task 7-fallback depending on gate result
**Final:** Task 8 (document everything)
