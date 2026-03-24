# Vaquill Legal AI -- Telegram Bot

A Telegram bot that answers legal questions using the [Vaquill](https://vaquill.ai)
Legal AI API. It renders markdown tables as images, shows case-law sources
with clickable inline keyboard buttons, and maintains per-chat conversation
history for follow-up questions.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Telegram Bot Setup (BotFather)](#telegram-bot-setup-botfather)
4. [Quick Start (Local Development)](#quick-start-local-development)
5. [Webhook Mode (Production)](#webhook-mode-production)
6. [Docker Deployment](#docker-deployment)
7. [Render / Railway Deployment](#render--railway-deployment)
8. [Bot Commands](#bot-commands)
9. [Features](#features)
10. [Environment Variable Reference](#environment-variable-reference)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The bot connects your Telegram chat to the Vaquill `/ask` API. When a user
sends a question the bot forwards it (along with conversation history) to
Vaquill, then formats the answer for Telegram:

```
User message
  -> rate_limiter.check()
  -> vaquill_client.ask(question, chatHistory=[...])
  -> sanitize_for_telegram(answer)
  -> extract tables -> generate_table_image()
  -> send text chunks (HTML) + table images + sources keyboard
```

Conversation history is kept in-memory per `chat_id`. No external state
store (Redis, database) is required for a single-instance deployment.

---

## Prerequisites

| Requirement | Where to get it |
|---|---|
| **Python 3.10+** | [python.org](https://www.python.org/downloads/) |
| **Telegram account** | [telegram.org](https://telegram.org/) |
| **Telegram Bot Token** | [@BotFather](https://t.me/botfather) -- see the next section |
| **Vaquill API key** | [app.vaquill.ai](https://app.vaquill.ai) -- Settings > API Keys |

---

## Telegram Bot Setup (BotFather)

This section walks through creating a new Telegram bot from scratch.

### Step 1 -- Open BotFather

1. Open Telegram (desktop or mobile).
2. Search for **@BotFather** or open [t.me/botfather](https://t.me/botfather).
3. Press **Start** if this is your first interaction.

### Step 2 -- Create the bot

1. Send `/newbot`.
2. BotFather will ask for a **display name** (e.g., `Vaquill Legal AI`).
3. Then it asks for a **username**. This must end in `bot`
   (e.g., `vaquill_legal_bot`).
4. BotFather replies with your **API token** -- a string that looks like
   `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`. Copy this; you will use
   it as `TELEGRAM_BOT_TOKEN`.

### Step 3 -- Set description and about text (optional but recommended)

```
/setdescription
```

BotFather will ask you to choose the bot, then type the description:

> Ask legal questions about Indian and US law. Powered by Vaquill Legal AI.

```
/setabouttext
```

> Legal research assistant powered by vaquill.ai

### Step 4 -- Set bot commands

```
/setcommands
```

Choose your bot, then paste the following block:

```
start - Start a new conversation
help - Show help information
examples - Show example questions
stats - View your usage statistics
clear - Clear conversation history
```

This registers the command hints that Telegram shows in the "/" menu. The
bot also sets these programmatically on startup via `set_my_commands`, but
doing it manually ensures they appear even before the first run.

### Step 5 -- Set bot profile picture (optional)

```
/setuserpic
```

Upload a square image (at least 512x512 px). A Vaquill logo works well.

---

## Quick Start (Local Development)

Local development uses **polling mode** -- the bot opens a long-lived
connection to the Telegram API and pulls updates. No public URL or HTTPS
certificate is needed.

```bash
# 1. Clone the repo (if you haven't already)
cd integrations/telegram-bot/

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and fill in TELEGRAM_BOT_TOKEN and VAQUILL_API_KEY

# 5. Run the bot
python bot.py
```

You should see:

```
INFO - Vaquill Telegram bot starting (mode=standard)
```

Open Telegram, search for your bot by username, press **Start**, and send a
question.

### Development workflow

1. Edit `bot.py`, `vaquill_client.py`, etc.
2. Stop the bot with Ctrl+C.
3. Re-run `python bot.py`.
4. Test in Telegram.

> **Tip:** Create a separate test bot via BotFather for development so you do
> not disturb production users.

---

## Webhook Mode (Production)

In production you typically want **webhook mode**: Telegram pushes updates to
a public HTTPS endpoint instead of the bot polling for them. This is more
efficient and avoids long-lived connections.

### 1. Deploy the bot behind HTTPS

Any platform that gives you an HTTPS URL works (Render, Railway, a VPS with
nginx + Let's Encrypt, etc.). The bot must be reachable at a URL like:

```
https://your-domain.example.com/webhook
```

### 2. Register the webhook with Telegram

Use curl (replace the placeholders):

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://your-domain.example.com/webhook"}'
```

Or with Python:

```python
import requests

BOT_TOKEN = "your-token"
WEBHOOK_URL = "https://your-domain.example.com/webhook"

resp = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    json={"url": WEBHOOK_URL},
)
print(resp.json())
```

### 3. Verify the webhook

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

You should see `"url": "https://..."` and `"pending_update_count": 0`.

### 4. Switch back to polling (if needed)

To remove the webhook and go back to polling:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook"
```

> **Note:** The current `bot.py` starts in polling mode by default. To run in
> webhook mode you need to add a small HTTP server (e.g., with `aiohttp` or
> `starlette`) that receives POST requests at `/webhook` and feeds them into
> `application.update_queue`. This is a straightforward extension -- see the
> [python-telegram-bot webhook example](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Webhooks).

---

## Docker Deployment

The included `Dockerfile` builds a slim Python 3.11 image with DejaVu fonts
(for table-image rendering) and runs the bot as a non-root user.

### Build and run

```bash
docker build -t vaquill-telegram-bot .
docker run --env-file .env vaquill-telegram-bot
```

### Build with docker compose

Create a `docker-compose.yml` alongside the Dockerfile:

```yaml
services:
  telegram-bot:
    build: .
    env_file: .env
    restart: unless-stopped
```

```bash
docker compose up -d
```

### What the Dockerfile does

```dockerfile
FROM python:3.11-slim
# Installs DejaVu fonts for Pillow table rendering
# Creates a non-root 'botuser'
# Runs: python bot.py
```

---

## Render / Railway Deployment

### Render

The repository includes a `render.yaml` blueprint. To deploy:

1. Push this directory to a GitHub or GitLab repository.
2. In the [Render dashboard](https://dashboard.render.com/), click
   **New > Blueprint** and connect the repository.
3. Render reads `render.yaml` and creates a **Background Worker** service.
4. In the service settings, fill in the secret environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `VAQUILL_API_KEY`
5. Deploy. The bot starts in polling mode automatically.

#### render.yaml

```yaml
services:
  - type: worker
    name: vaquill-telegram-bot
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python bot.py
    envVars:
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: VAQUILL_API_KEY
        sync: false
      - key: VAQUILL_API_URL
        value: https://api.vaquill.ai/api/v1
      - key: VAQUILL_MODE
        value: standard
      - key: RATE_LIMIT_PER_USER_PER_DAY
        value: 100
      - key: RATE_LIMIT_PER_USER_PER_MINUTE
        value: 5
```

> **Why a worker and not a web service?** The bot uses polling, not webhooks.
> A Render worker process runs continuously without needing an HTTP port.

### Railway

1. Install the Railway CLI:

   ```bash
   npm install -g @railway/cli
   ```

2. Deploy:

   ```bash
   railway login
   railway init
   railway up
   ```

3. Add environment variables in the Railway dashboard:
   - `TELEGRAM_BOT_TOKEN`
   - `VAQUILL_API_KEY`
   - Any optional variables from the reference table below.

### VPS / systemd

For a plain Linux server:

```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv
python3 -m venv /opt/vaquill-telegram-bot/.venv
source /opt/vaquill-telegram-bot/.venv/bin/activate
pip install -r requirements.txt
```

Create `/etc/systemd/system/vaquill-telegram-bot.service`:

```ini
[Unit]
Description=Vaquill Legal AI Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/vaquill-telegram-bot
EnvironmentFile=/opt/vaquill-telegram-bot/.env
ExecStart=/opt/vaquill-telegram-bot/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vaquill-telegram-bot
```

### Deployment comparison

| Platform | Best for | Cost | Persistent state | Timeout |
|---|---|---|---|---|
| **Docker** | Self-hosted | Free (+ infra) | Yes | None |
| **Render** | Managed worker | Free tier available | No (in-memory) | None |
| **Railway** | Managed worker | Usage-based | Optional (add Redis) | None |
| **VPS + systemd** | Full control | Varies | Yes | None |

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message with inline category buttons (Indian Law, US Law, General). Clears any existing conversation history. |
| `/help` | Shows the list of available commands and tips (daily message limit, etc.). |
| `/examples` | Displays category buttons. Tapping a category shows example questions as inline buttons; tapping a question sends it as a query. |
| `/stats` | Shows your current usage: messages used today, daily remaining, per-minute limit. |
| `/clear` | Wipes conversation history for the current chat so the next question starts fresh. |

All commands are registered with Telegram on bot startup so they appear in
the "/" autocomplete menu.

---

## Features

### Conversation history

The bot maintains a rolling window of the last N exchanges (configurable via
`MAX_CONVERSATION_HISTORY`, default 10) per chat. History is sent to the
Vaquill API as `chatHistory` so follow-up questions ("What about Section 304?"
after asking about IPC) work naturally. Use `/clear` to reset.

### Markdown table rendering

When the Vaquill API returns a markdown table, the bot:

1. Extracts the table from the answer text.
2. Renders it as a styled PNG image using Pillow (blue header row, alternating
   row colours, word-wrapped cells).
3. Sends the image alongside the text answer.

If Pillow is not installed, tables are converted to a mobile-friendly
"card" layout in plain text.

### Source citations

Each API response can include case-law sources. The bot displays them in two
ways:

- **Inline text** at the bottom of the answer (`Sources:` block with
  clickable hyperlinks to PDFs).
- **Inline keyboard buttons** -- each button opens the source PDF directly
  in the user's browser.

### Telegram HTML sanitisation

The answer text goes through `sanitize_for_telegram()` which:

- Strips raw HTML tags.
- Escapes special characters.
- Converts markdown headings, bold, italic, strikethrough, links, and code
  blocks into Telegram-safe HTML (`<b>`, `<i>`, `<s>`, `<a>`, `<code>`,
  `<pre>`).
- Falls back to plain text if Telegram rejects the HTML.

### Message chunking

Telegram has a 4096-character message limit. Long answers are split at
natural boundaries (paragraph breaks > newlines > sentence ends > spaces)
and sent as multiple messages.

### Rate limiting

Built-in per-user rate limiting with two windows:

| Window | Default | Configurable via |
|---|---|---|
| Per minute | 5 messages | `RATE_LIMIT_PER_USER_PER_MINUTE` |
| Per day | 100 messages | `RATE_LIMIT_PER_USER_PER_DAY` |

Limits are tracked in-memory and reset on process restart.

### Access control

Set `ALLOWED_USERS` to a comma-separated list of Telegram user IDs to
restrict who can use the bot. When unset, the bot is open to everyone.

To find your Telegram user ID, message [@userinfobot](https://t.me/userinfobot).

---

## Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | **Yes** | -- | Bot token from @BotFather |
| `VAQUILL_API_KEY` | **Yes** | -- | Vaquill API key (starts with `vq_key_...`) |
| `VAQUILL_API_URL` | No | `https://api.vaquill.ai/api/v1` | Vaquill API base URL |
| `VAQUILL_MODE` | No | `standard` | RAG tier: `standard` or `deep` |
| `VAQUILL_COUNTRY_CODE` | No | -- | Jurisdiction filter (e.g. `IN`, `US`, `CA`) |
| `RATE_LIMIT_PER_USER_PER_DAY` | No | `100` | Max messages per user per day |
| `RATE_LIMIT_PER_USER_PER_MINUTE` | No | `5` | Max messages per user per minute |
| `MAX_MESSAGE_LENGTH` | No | `4000` | Max allowed input message length (chars) |
| `ALLOWED_USERS` | No | -- | Comma-separated Telegram user IDs for access control |
| `MAX_CONVERSATION_HISTORY` | No | `10` | Number of exchange pairs to keep in context |
| `MAX_SOURCES_PER_RESPONSE` | No | `5` | Max case-law sources shown per answer |
| `LOG_LEVEL` | No | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `SENTRY_DSN` | No | -- | Sentry DSN for error tracking |
| `ENVIRONMENT` | No | `development` | Environment label (`development`, `production`) |

---

## Troubleshooting

### Bot does not respond to messages

| Check | Fix |
|---|---|
| Is the bot process running? | Run `python bot.py` and look for the startup log line. |
| Is `TELEGRAM_BOT_TOKEN` correct? | Copy the token from BotFather again. Tokens do not contain spaces. |
| Is `VAQUILL_API_KEY` valid? | Test it with `curl -H "Authorization: Bearer vq_key_..." https://api.vaquill.ai/api/v1/health`. |
| Did you message the right bot? | Search for your bot's exact username in Telegram. |
| Is another instance running? | Only one process can poll with the same token. Stop duplicates. |

### "Unauthorized" / 401 errors

Your `VAQUILL_API_KEY` is invalid or expired. Generate a new one at
[app.vaquill.ai](https://app.vaquill.ai) under Settings > API Keys.

### "Insufficient credits" / 402 errors

The API key's account has run out of credits. Top up at
[app.vaquill.ai](https://app.vaquill.ai) or contact the bot administrator.

### Rate limit messages appear immediately

You may have hit the per-minute limit (default: 5). Wait 60 seconds or raise
`RATE_LIMIT_PER_USER_PER_MINUTE`.

### Tables render as text instead of images

Pillow is not installed or a font is missing. Verify with:

```bash
python -c "from PIL import Image; print('Pillow OK')"
```

In Docker, the `Dockerfile` installs `fonts-dejavu-core` automatically. On
macOS, the bot falls back to Helvetica or the Pillow default font.

### SSL certificate errors (macOS)

The bot uses `certifi` for SSL verification, which should handle this
automatically. If you still see SSL errors:

```bash
pip install --upgrade certifi
```

### HTML parse errors in Telegram

The bot catches `BadRequest` exceptions from Telegram and falls back to
plain text. If you see `HTML parse failed, falling back to plain text` in
the logs, the Vaquill API likely returned unusual formatting. This is
handled gracefully -- no action needed unless it happens on every message.

### Webhook is set but bot does not respond

```bash
# Check webhook status
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Remove webhook to go back to polling
curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"
```

If `pending_update_count` is growing, your webhook endpoint is not
reachable or is returning errors.

### Debug logging

Set `LOG_LEVEL=DEBUG` in `.env` to see detailed request/response logs from
both the Telegram library and the Vaquill client.

---

## Project Structure

```
integrations/telegram-bot/
  bot.py              # Main bot: commands, message handler, table rendering
  config.py           # Pydantic settings, starter questions, message templates
  vaquill_client.py   # Async Vaquill API client (ask, ask_stream, sources)
  rate_limiter.py     # In-memory per-user rate limiter
  requirements.txt    # Python dependencies
  Dockerfile          # Production container image
  render.yaml         # Render.com deployment blueprint
  .env.example        # Template for environment variables
```

---

## License

MIT
