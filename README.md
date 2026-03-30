# Maksym's HA Add-ons

A Home Assistant custom add-on repository.

## Installation

1. In Home Assistant: **Settings → Add-ons → Add-on Store → three-dot menu → Repositories**
2. Add this repository URL: `https://github.com/maksyms/ha-addons`
3. Click **Add**, then refresh
4. Find the add-on you want and click **Install**

## Add-ons

### [Auto Analyst](autoanalyst/)

Monitors a Telegram chat for tweet links, fetches content, sends it for critical analysis, and posts the result back.

- Two-tier tweet fetching (X API v2 + fxtwitter fallback)
- Video transcription via OpenAI Whisper
- Claude or Perplexity analysis backend

### [Claude Code EA](claudecode-ea/)

Telegram bot bridging to Claude Code via the Agent SDK. Wraps [Claudegram](https://github.com/NachoSEO/claudegram) as a Home Assistant add-on.

- AI-powered executive assistant over Telegram
- Streaming responses
- Optional dangerous mode for arbitrary command execution

### [Paperless-ngx](paperless-ngx/)

Document management system that transforms physical documents into a searchable online archive.

- Full-text search and tagging
- Automatic document classification
- Web UI with ingress support

### [Paperless-GPT](paperless-gpt/)

AI-powered document organizer for Paperless-ngx. Generates titles, tags, correspondents, and dates using LLMs.

- Supports OpenAI, Anthropic, Ollama, Google AI, and Mistral
- Manual and fully automatic processing modes
- LLM-enhanced OCR support

### [Tika & Gotenberg](tika-gotenberg/)

Apache Tika and Gotenberg services for document text extraction. Companion to Paperless-ngx.

- Apache Tika for content extraction
- Gotenberg for PDF conversion
- Shared infrastructure for document processing

## License

MIT
