# Vaquill Microsoft Teams Bot

A Microsoft Teams bot that provides AI-powered legal research via the Vaquill API.

## Features

- Legal Q&A powered by Vaquill Legal AI
- Conversation history with context (client-side, no server sessions)
- Adaptive Cards UI with source citations
- Rate limiting (per-user, per-channel, per-tenant)
- Redis support for distributed deployments
- Security controls: tenant/channel allowlists, user blocklists

## Setup

1. **Register a Bot** in the [Azure Bot Service](https://portal.azure.com/).
2. Copy `.env.example` to `.env` and fill in your credentials.
3. Install dependencies and run:

```bash
pip install -r requirements.txt
python app.py
```

4. Expose port 3978 via ngrok or deploy behind a reverse proxy.
5. Set the messaging endpoint in Azure to `https://your-host/api/messages`.

## Docker

```bash
docker build -t vaquill-teams-bot .
docker run -p 3978:3978 --env-file .env vaquill-teams-bot
```

## Commands

| Command   | Description                      |
|-----------|----------------------------------|
| `/help`   | Show available commands          |
| `/clear`  | Clear conversation history       |
| `/status` | Check bot status and rate limits |

## Architecture

```
app.py                  Flask entry point, Bot Framework adapter
bot.py                  VaquillTeamsBot (ActivityHandler)
vaquill_client.py       Shared Vaquill API client (POST /api/v1/ask)
conversation_manager.py Client-side chat history (Redis or in-memory)
rate_limiter.py         Sliding-window rate limiter
adaptive_cards.py       Adaptive Card templates
auth_handler.py         Teams JWT / tenant validation
input_validator.py      Input sanitization and injection detection
config.py               Environment-based configuration
```

## API Contract

The bot calls `POST /api/v1/ask` with:

```json
{
  "question": "...",
  "mode": "standard",
  "sources": true,
  "maxSources": 5,
  "chatHistory": [{"role": "user", "content": "..."}, ...]
}
```

Response:

```json
{
  "data": {
    "answer": "...",
    "sources": [{"caseName": "...", "citation": "...", "court": "..."}],
    "mode": "standard"
  },
  "meta": {"processingTimeMs": 1234, "creditsConsumed": 1}
}
```

Auth: `Authorization: Bearer vq_key_...`
