# Vaquill Slack Bot

Slack bot for the Vaquill Legal AI platform. Responds to @mentions, DMs,
and slash commands with AI-powered legal research answers backed by
cited case law and statutes.

## Features

- **@mention / DM** -- ask legal questions in any channel or DM
- **Thread context** -- maintains chat history per thread
- **Legal sources** -- displays cited cases, statutes, and courts
- **Feedback buttons** -- thumbs up / down for response quality
- **Slash commands** -- `/vaquill <question>` and `/vaquill-help`
- **Rate limiting** -- per-user and per-channel, with optional Redis backend

## Quick Start

```bash
# 1. Copy and fill in environment variables
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run (Socket Mode for development)
python bot.py
```

## Docker

```bash
docker compose up -d
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot user OAuth token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Yes | Slack app signing secret |
| `SLACK_APP_TOKEN` | No | App-level token for Socket Mode (`xapp-...`) |
| `VAQUILL_API_KEY` | Yes | Vaquill API key (`vq_key_...`) |
| `VAQUILL_API_URL` | No | API base URL (default: `https://api.vaquill.ai/api/v1`) |
| `VAQUILL_MODE` | No | RAG mode: `standard` or `deep` (default: `standard`) |
| `VAQUILL_COUNTRY_CODE` | No | Country code for jurisdiction (e.g. `IN`) |
| `REDIS_URL` | No | Redis URL for distributed rate limiting |

## Architecture

```
User message
  -> Slack Event API
  -> bot.py (slack_bolt AsyncApp)
  -> vaquill_client.py (POST /api/v1/ask)
  -> Format response + sources
  -> Reply in thread
```

Chat history is maintained client-side in `conversation_manager.py` as
`[{role, content}, ...]` arrays, passed to the Vaquill API on each request.
No server-side sessions are created.

## Slash Commands

Register these in your Slack app configuration:

| Command | Description |
|---|---|
| `/vaquill` | Ask a legal question |
| `/vaquill-help` | Show help and usage info |
