# Paperless-GPT Home Assistant Add-on

AI-powered document organizer for [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx). Uses LLMs to automatically generate titles, tags, correspondents, and dates for your documents.

Wraps [paperless-gpt](https://github.com/icereed/paperless-gpt) as a Home Assistant add-on.

## Installation

1. Add this repository to Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Install **Paperless-GPT** from the store
3. Configure the required options (see below)
4. Start the add-on

## Configuration

### Required

| Option | Description |
|---|---|
| `paperless_base_url` | Paperless-ngx URL (default: `http://local-paperless-ngx:8000`) |
| `paperless_api_token` | API token from Paperless-ngx admin |

### LLM Provider

Configure one LLM provider:

| Option | Description |
|---|---|
| `llm_provider` | `openai`, `ollama`, `anthropic`, `googleai`, or `mistral` (default: `openai`) |
| `llm_model` | Model name (e.g. `gpt-4o`, `qwen3:8b`) (default: `gpt-4o`) |
| `openai_api_key` | OpenAI API key |
| `anthropic_api_key` | Anthropic API key |
| `ollama_host` | Ollama endpoint (e.g. `http://host.docker.internal:11434`) |

### Usage

**Manual mode:** Tag a document with `paperless-gpt` in Paperless-ngx, then open the web UI to review AI suggestions.

**Auto mode:** Tag a document with `paperless-gpt-auto` for fully automatic processing.

The web UI is accessible from the Home Assistant sidebar (via ingress) or directly at port 8080.

## Services

| Service | Port | Description |
|---|---|---|
| paperless-gpt | 8080 | Web UI and API |

## Manual Deploy

Use the GitHub Actions workflow with **force_deploy** enabled to SCP files and rebuild on your HA instance.

## License

MIT
