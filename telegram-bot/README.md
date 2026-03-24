# Vaquill Telegram Bot

Telegram bot for the Vaquill Legal AI platform. Answers legal questions using
the Vaquill `/ask` API, renders markdown tables as images, and displays
case-law sources with inline keyboard buttons.

## Features

- `/start`, `/help`, `/clear`, `/examples`, `/stats` commands
- Per-chat conversation history (client-side, in-memory)
- Markdown table to image rendering (Pillow)
- Case-law sources with clickable PDF links
- Per-user rate limiting (minute + daily)
- Telegram HTML sanitisation with plain-text fallback
- Optional access control via `ALLOWED_USERS`

## Quick start

```bash
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN and VAQUILL_API_KEY

pip install -r requirements.txt
python bot.py
```

## Docker

```bash
docker build -t vaquill-telegram-bot .
docker run --env-file .env vaquill-telegram-bot
```

## Configuration

All settings are loaded from environment variables (or `.env`). See
`.env.example` for the full list.

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |
| `VAQUILL_API_KEY` | Yes | Vaquill API key (`vq_key_...`) |
| `VAQUILL_API_URL` | No | API base URL (default: `https://api.vaquill.ai/api/v1`) |
| `VAQUILL_MODE` | No | RAG tier: `standard` or `deep` (default: `standard`) |
| `VAQUILL_COUNTRY_CODE` | No | Country code for jurisdiction filtering (e.g. `IN`, `US`) |
| `ALLOWED_USERS` | No | Comma-separated Telegram user IDs for access control |

## Architecture

```
User message
  -> rate_limiter.check()
  -> vaquill_client.ask(question, chatHistory=[...])
  -> sanitize_for_telegram(answer)
  -> extract tables -> generate_table_image()
  -> send text chunks (HTML) + table images + sources keyboard
```

The bot maintains an in-memory `chat_histories` dict keyed by `chat_id`.
History is passed to the Vaquill API as `chatHistory` for follow-up context.
No external state store (Redis/DB) is required.
