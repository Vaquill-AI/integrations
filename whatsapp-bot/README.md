# Vaquill WhatsApp Bot

WhatsApp integration for the Vaquill Legal AI platform, powered by Twilio.

## Architecture

```
WhatsApp -> Twilio -> /webhook/whatsapp (FastAPI) -> Vaquill /ask API -> WhatsApp
```

- **Stateless API**: chat history is maintained client-side (Redis or in-memory) and sent with each `/ask` request.
- **No project/session IDs**: the Vaquill API does not require them. Just `{question, mode, sources, chatHistory}`.
- **Two modes**: `standard` (fast, 18 techniques) and `deep` (thorough, 35 techniques).

## Quick Start

```bash
cp .env.example .env
# Edit .env with your Vaquill API key and Twilio credentials

pip install -r requirements.txt
python bot.py
```

The bot listens on `http://localhost:8000`. Set your Twilio WhatsApp webhook to `https://<your-domain>/webhook/whatsapp`.

## Docker

```bash
docker build -t vaquill-whatsapp-bot .
docker run -p 8000:8000 --env-file .env vaquill-whatsapp-bot
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Start a new conversation |
| `/help` | Show available commands |
| `/examples` | Show example legal questions |
| `/mode [standard\|deep]` | Switch research mode |
| `/stats` | View your usage statistics |
| `/language [code]` | Change response language |
| `/clear` | Clear conversation history |
| `/feedback [message]` | Send feedback |
| `/about` | About Vaquill |
| `/settings` | View current settings |

## Environment Variables

See `.env.example` for all available settings. Required:

- `VAQUILL_API_KEY` — your Vaquill API key (`vq_key_...`)
- `TWILIO_ACCOUNT_SID` — Twilio Account SID
- `TWILIO_AUTH_TOKEN` — Twilio Auth Token
- `TWILIO_WHATSAPP_NUMBER` — Twilio WhatsApp number (`whatsapp:+14155238886`)

Optional:

- `REDIS_URL` — Redis connection string for persistent sessions/rate-limits. Omit to use in-memory fallback.
- `VAQUILL_MODE` — default research mode (`standard` or `deep`)
- `VAQUILL_COUNTRY_CODE` — default jurisdiction (`IN`, `US`, `CA`, etc.)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Status |
| GET | `/health` | Health check |
| POST | `/webhook/whatsapp` | Twilio webhook |
| GET | `/stats/{phone_number}` | User stats (admin) |
| POST | `/broadcast` | Broadcast message (admin) |
