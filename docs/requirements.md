# Claudecode-EA Requirements

> MoSCoW-prioritised requirements for the Claude Code Telegram bot add-on.
> Status: **Draft** | Last updated: 2026-03-24

---

## Must Have

### M1 — Project Support
Each project has its own directory with a dedicated `CLAUDE.md` that defines context and behaviour for that project. The bot operates within the active project's scope.

- [ ] Projects are directories under a configurable workspace root
- [ ] Each project contains a `CLAUDE.md` that is read on project activation
- [ ] Only one project is active per chat session at a time

### M2 — Project Switching with Context Lifecycle
When the user switches projects via `/project`, the bot performs a full context transition:

1. **Summarise** the current conversation into `history/<YYYYMMDD> - conversation <N>.md`
2. **Extract** key takeaways into `memory.md` (format TBD)
3. **Reset** the conversation context
4. **Read** the new project's `CLAUDE.md` and resume in the new project scope

- [ ] `/project` command triggers the full lifecycle above
- [ ] Conversation summaries are persisted per project
- [ ] `memory.md` is updated with durable takeaways across sessions
- [ ] Conversation numbering increments per day per project

### M3 — Multi-Backend Authentication
Support three authentication backends for the Claude API:

| Backend | Auth mechanism |
| --- | --- |
| **Amazon Bedrock** | `CLAUDE_CODE_USE_BEDROCK=1` + AWS credentials |
| **Anthropic API key** | `ANTHROPIC_API_KEY` |
- [ ] Bedrock credentials via env vars (`AWS_REGION`, `AWS_ACCESS_KEY_ID`, etc.)
- [ ] Direct API key via `ANTHROPIC_API_KEY`

---

## Should Have

### S1 — Personal Subscription Support
Support authenticating via a personal Claude Pro/Max subscription (OAuth / `claude.ai` login), in addition to Bedrock and API key backends.

- [ ] Personal subscription auth (feasibility depends on Claude Code CLI capabilities)

---

## Could Have

> *To be defined.*

---

## Won't Have (this iteration)

> *To be defined.*
