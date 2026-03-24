# Vaquill Slack Bot

A Slack bot that brings Vaquill Legal AI into your workspace. Ask legal
research questions via @mentions, direct messages, or slash commands and get
AI-powered answers backed by cited case law and statutes.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Slack App Setup](#slack-app-setup)
4. [Socket Mode vs HTTP Mode](#socket-mode-vs-http-mode)
5. [Quick Start (Local Development)](#quick-start-local-development)
6. [Docker Deployment](#docker-deployment)
7. [Cloud Deployment](#cloud-deployment)
8. [Slash Commands](#slash-commands)
9. [Features](#features)
10. [Environment Variable Reference](#environment-variable-reference)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The bot connects your Slack workspace to the Vaquill API (`POST /api/v1/ask`).
When a user asks a question the bot sends it to Vaquill, formats the answer
with cited legal sources, and replies in-thread.

```
User message
  -> Slack Event API / Socket Mode
  -> bot.py (slack_bolt AsyncApp)
  -> vaquill_client.py (POST /api/v1/ask)
  -> Format answer + legal sources
  -> Reply in thread with feedback buttons
```

Chat history is maintained client-side in `conversation_manager.py` as
`[{role, content}, ...]` arrays and passed to the Vaquill API on each request.
No server-side sessions are created on Vaquill's side.

---

## Prerequisites

Before you begin, make sure you have:

- **Python 3.10+** installed
- **Slack workspace admin access** (or permission to install apps)
- **Vaquill API key** -- get one at [vaquill.ai](https://vaquill.ai). Keys
  start with `vq_key_`.
- (Optional) **Docker** and **Docker Compose** for containerised deployment
- (Optional) **Redis** for distributed rate limiting (an in-memory fallback is
  used when Redis is not available)

---

## Slack App Setup

Follow these steps exactly to create and configure your Slack app.

### Step 1 -- Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps).
2. Click **Create New App**.
3. Choose **From scratch**.
4. Enter an app name (e.g. "Vaquill Legal AI").
5. Select your workspace.
6. Click **Create App**.

### Step 2 -- Configure Bot Token Scopes

Navigate to **OAuth & Permissions** in the left sidebar and scroll down to
**Bot Token Scopes**. Add every scope listed below:

| Scope | Why it is needed |
|---|---|
| `app_mentions:read` | Read @mentions of the bot |
| `channels:history` | View messages in public channels the bot is in |
| `channels:read` | View basic channel info |
| `chat:write` | Send messages and replies |
| `commands` | Register slash commands (`/vaquill`, `/vaquill-help`) |
| `groups:history` | View messages in private channels the bot is in |
| `groups:read` | View basic private channel info |
| `im:history` | View direct messages with the bot |
| `im:read` | View basic DM info |
| `im:write` | Start direct message conversations |
| `users:read` | Look up user info (for bot-message filtering) |

### Step 3 -- Enable Event Subscriptions

1. Go to **Event Subscriptions** in the left sidebar.
2. Toggle **Enable Events** to On.
3. Under **Subscribe to bot events**, add:
   - `app_mention` -- fires when someone @mentions the bot
   - `message.im` -- fires on direct messages to the bot
   - `message.channels` -- (optional) fires on all channel messages the bot
     can see
4. If you are using **HTTP mode**, enter your Request URL now
   (`https://your-domain.com/slack/events`). For **Socket Mode** you can skip
   this field.
5. Click **Save Changes**.

### Step 4 -- Create Slash Commands

Go to **Slash Commands** and create two commands:

| Command | Request URL (HTTP mode only) | Short Description |
|---|---|---|
| `/vaquill` | `https://your-domain.com/slack/events` | Ask a legal question |
| `/vaquill-help` | `https://your-domain.com/slack/events` | Show help and usage info |

For Socket Mode the Request URL is not needed.

### Step 5 -- Enable Interactivity (HTTP mode only)

1. Go to **Interactivity & Shortcuts**.
2. Toggle **Interactivity** to On.
3. Set the Request URL to `https://your-domain.com/slack/events`.
4. Click **Save Changes**.

This lets Slack deliver feedback-button clicks back to the bot.

### Step 6 -- (Optional) Enable Socket Mode

If you want to run the bot without a public URL (recommended for local
development):

1. Go to **Socket Mode** in the left sidebar.
2. Toggle **Enable Socket Mode** to On.
3. You will be prompted to create an **App-Level Token**. Give it a name (e.g.
   "socket-token") and the scope `connections:write`.
4. Copy the token (starts with `xapp-`). This is your `SLACK_APP_TOKEN`.

### Step 7 -- Install App to Workspace

1. Go to **OAuth & Permissions**.
2. Click **Install to Workspace**.
3. Authorize the requested permissions.
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`). This is your
   `SLACK_BOT_TOKEN`.

### Step 8 -- Copy the Signing Secret

1. Go to **Basic Information**.
2. Under **App Credentials**, find **Signing Secret**.
3. Click **Show** and copy it. This is your `SLACK_SIGNING_SECRET`.

---

## Socket Mode vs HTTP Mode

The bot supports two connection methods. Choose the one that fits your setup.

| | Socket Mode | HTTP Mode |
|---|---|---|
| **How it works** | WebSocket connection from bot to Slack (outbound only) | Slack sends HTTP POST requests to your server |
| **Public URL needed?** | No | Yes (HTTPS required) |
| **Best for** | Local development, firewalled environments | Production, cloud deployments |
| **Token needed** | `SLACK_APP_TOKEN` (`xapp-...`) | Not needed |
| **Setup** | Enable Socket Mode in Slack app settings | Set Request URLs for Events, Commands, Interactivity |

**The bot auto-detects the mode.** If `SLACK_APP_TOKEN` is set in the
environment, it uses Socket Mode. Otherwise it starts an HTTP server on the
port defined by `PORT` (default `3000`).

---

## Quick Start (Local Development)

Get the bot running locally in under five minutes using Socket Mode.

### 1. Clone and install

```bash
cd integrations/slack-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with the values you collected during Slack App Setup:

```dotenv
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token      # enables Socket Mode
VAQUILL_API_KEY=vq_key_your-api-key
```

### 3. Run the bot

```bash
python bot.py
```

You should see:

```
Bot initialised with user ID: U0XXXXXXX
```

### 4. Test it

- **@mention**: In any channel the bot has been added to, type
  `@Vaquill what is Section 498A of the IPC?`
- **DM**: Send a direct message to the bot.
- **Slash command**: Type `/vaquill what are the grounds for divorce in India?`

### 5. Debug mode

For verbose logging:

```bash
LOG_LEVEL=DEBUG python bot.py
```

---

## Docker Deployment

The repository includes a `Dockerfile` and a `docker-compose.yml` that bundles
the bot with a Redis instance for distributed rate limiting.

### Using Docker Compose (recommended)

```bash
# 1. Create and fill in .env
cp .env.example .env
# edit .env ...

# 2. Build and start
docker compose up -d

# 3. View logs
docker compose logs -f bot

# 4. Stop
docker compose down
```

The compose file defines two services:

| Service | Image | Purpose |
|---|---|---|
| `bot` | Built from `./Dockerfile` | The Slack bot |
| `redis` | `redis:7-alpine` | Distributed rate limiting and caching |

Redis data is persisted in a named volume (`redis_data`).

### docker-compose.yml

```yaml
version: "3.8"

services:
  bot:
    build: .
    container_name: vaquill-slack-bot
    ports:
      - "3000:3000"
    environment:
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
      - SLACK_SIGNING_SECRET=${SLACK_SIGNING_SECRET}
      - VAQUILL_API_KEY=${VAQUILL_API_KEY}
      - VAQUILL_API_URL=${VAQUILL_API_URL:-https://api.vaquill.ai/api/v1}
      - VAQUILL_MODE=${VAQUILL_MODE:-standard}
      - VAQUILL_COUNTRY_CODE=${VAQUILL_COUNTRY_CODE:-IN}
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - RATE_LIMIT_PER_USER=${RATE_LIMIT_PER_USER:-20}
      - RATE_LIMIT_PER_CHANNEL=${RATE_LIMIT_PER_CHANNEL:-100}
    depends_on:
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c",
        "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  redis:
    image: redis:7-alpine
    container_name: vaquill-slack-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  redis_data:
    driver: local
```

### Standalone Docker (no Compose)

```bash
docker build -t vaquill-slack-bot .

docker run -d \
  --name vaquill-slack-bot \
  -e SLACK_BOT_TOKEN="xoxb-your-token" \
  -e SLACK_SIGNING_SECRET="your-secret" \
  -e VAQUILL_API_KEY="vq_key_your-key" \
  -p 3000:3000 \
  vaquill-slack-bot
```

---

## Cloud Deployment

For production you will typically run in **HTTP mode** (no `SLACK_APP_TOKEN`)
behind a reverse proxy with TLS.

### General steps

1. Deploy the Docker image (or Python app) to your hosting provider.
2. Expose port 3000 behind HTTPS (use Cloudflare, Caddy, nginx + Let's
   Encrypt, or your provider's built-in TLS).
3. Set all required environment variables as secrets.
4. Update the Slack app Request URLs:
   - **Event Subscriptions**: `https://your-domain.com/slack/events`
   - **Slash Commands**: `https://your-domain.com/slack/events`
   - **Interactivity**: `https://your-domain.com/slack/events`

### Railway

```bash
# Push to GitHub, then deploy via railway.app dashboard
# Set environment variables in Railway's UI
# Railway provides a public HTTPS domain automatically
```

### Render

1. Connect your GitHub repository at [render.com](https://render.com).
2. Create a new **Web Service**.
3. Set Build Command to `pip install -r requirements.txt` and Start Command to
   `python bot.py`.
4. Add environment variables.
5. Render provides a `.onrender.com` domain with auto-TLS.

Note: Render's free tier spins down after 15 minutes of inactivity. Slash
commands may time out on cold starts.

### Fly.io

```bash
fly auth login
fly apps create vaquill-slack-bot

fly secrets set SLACK_BOT_TOKEN=xoxb-...
fly secrets set SLACK_SIGNING_SECRET=...
fly secrets set VAQUILL_API_KEY=vq_key_...

fly deploy
```

### VPS with nginx

If you run on a plain VPS, put nginx in front:

```nginx
server {
    listen 443 ssl;
    server_name slack-bot.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/slack-bot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/slack-bot.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Slash Commands

Register these in your Slack app configuration under **Slash Commands**.

| Command | Usage | Description |
|---|---|---|
| `/vaquill` | `/vaquill <question>` | Ask a legal research question. The answer is posted in the channel. |
| `/vaquill-help` | `/vaquill-help` | Display help text with usage instructions, available commands, and tips. |

Slack requires a response within 3 seconds. The bot immediately sends a
"Thinking..." message and then updates the thread with the full answer once the
Vaquill API responds.

---

## Features

### @Mention Responses

Mention the bot in any channel it has been added to:

```
@Vaquill what are the essential elements of a valid contract under Indian law?
```

The bot replies in a thread with the answer, cited sources, and feedback
buttons.

### Direct Messages

Send a DM to the bot. No @mention needed -- just type your question directly.

### Thread Context

The bot maintains conversation history per thread. After the initial @mention,
you can ask follow-up questions in the same thread without mentioning the bot
again:

```
User: @Vaquill what is Section 302 of the IPC?
Bot:  Section 302 deals with punishment for murder...

User: what is the maximum sentence?        (no @mention needed)
Bot:  The maximum sentence under Section 302 is...
```

Thread follow-ups expire after 1 hour of inactivity (configurable via
`THREAD_FOLLOW_UP_TIMEOUT`) and are capped at 50 messages per thread
(`THREAD_FOLLOW_UP_MAX_MESSAGES`).

### Legal Sources

Each response includes a "Sources" block showing up to 5 cited cases or
statutes with case name, citation, and court. Disable with `SHOW_SOURCES=false`.

### Feedback Buttons

Every response includes **Helpful** and **Not Helpful** buttons. Clicks are
tracked in the analytics module and the buttons are replaced with a
confirmation message.

### Starter Questions

Mention the bot without a question to see a list of suggested starter
questions. Each question is an interactive button -- click it to ask that
question immediately.

### Rate Limiting

Per-user (20/min) and per-channel (100/hour) rate limits are enforced.
Limits use an in-memory sliding window by default. When `REDIS_URL` is set,
Redis is used for distributed rate limiting across multiple bot instances.

### Security

- User allow-lists and block-lists (`ALLOWED_CHANNELS`, `BLOCKED_USERS`)
- Input validation and sanitisation
- Safe error messages that do not leak internal details
- Bot-message filtering to prevent infinite loops

---

## Environment Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| **Slack** | | | |
| `SLACK_BOT_TOKEN` | Yes | -- | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Yes | -- | Signing secret from Basic Information |
| `SLACK_APP_TOKEN` | No | -- | App-level token for Socket Mode (`xapp-...`). When set, the bot uses Socket Mode instead of HTTP. |
| **Vaquill API** | | | |
| `VAQUILL_API_KEY` | Yes | -- | Vaquill API key (`vq_key_...`) |
| `VAQUILL_API_URL` | No | `https://api.vaquill.ai/api/v1` | Vaquill API base URL |
| `VAQUILL_MODE` | No | `standard` | RAG tier: `standard` (faster, 18 techniques) or `deep` (35 techniques, more thorough) |
| `VAQUILL_COUNTRY_CODE` | No | -- | Jurisdiction country code (e.g. `IN` for India, `US` for United States) |
| **Rate Limiting** | | | |
| `RATE_LIMIT_PER_USER` | No | `20` | Max requests per user per minute |
| `RATE_LIMIT_PER_CHANNEL` | No | `100` | Max requests per channel per hour |
| `REDIS_URL` | No | -- | Redis URL for distributed rate limiting (e.g. `redis://localhost:6379`) |
| **Bot Behaviour** | | | |
| `MAX_MESSAGE_LENGTH` | No | `4000` | Max input message length (characters) |
| `SHOW_SOURCES` | No | `true` | Show legal source citations in responses |
| `ENABLE_THREADING` | No | `true` | Maintain per-thread conversation context |
| `THREAD_FOLLOW_UP_ENABLED` | No | `true` | Respond to follow-ups in threads without requiring @mentions |
| `THREAD_FOLLOW_UP_TIMEOUT` | No | `3600` | Seconds of inactivity before thread follow-up expires |
| `THREAD_FOLLOW_UP_MAX_MESSAGES` | No | `50` | Max bot responses per thread |
| `IGNORE_BOT_MESSAGES` | No | `true` | Ignore messages from other bots (prevents loops) |
| **Security** | | | |
| `ALLOWED_CHANNELS` | No | -- | Comma-separated channel IDs the bot is restricted to |
| `BLOCKED_USERS` | No | -- | Comma-separated user IDs blocked from using the bot |
| **Server** | | | |
| `PORT` | No | `3000` | HTTP server port (only used in HTTP mode) |
| `LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| **Analytics** | | | |
| `ENABLE_ANALYTICS` | No | `true` | Enable usage tracking |
| `ANALYTICS_ENDPOINT` | No | -- | External analytics endpoint URL |
| **Conversation** | | | |
| `CONVERSATION_TIMEOUT` | No | `86400` | Seconds before a conversation session expires (default 24 hours) |
| `MAX_CONTEXT_MESSAGES` | No | `10` | Max messages to include as chat history in API calls |

---

## Troubleshooting

### Bot is not responding to @mentions

1. **Check that the bot is in the channel.** In Slack, open the channel
   details and look under "Integrations" or "Apps". If the bot is not listed,
   invite it with `/invite @Vaquill`.
2. **Verify Event Subscriptions are enabled.** Go to your Slack app settings
   and confirm that `app_mention` is listed under bot events.
3. **Check the Request URL (HTTP mode).** The URL must be HTTPS and must
   respond to Slack's verification challenge. Look for errors in the Slack app
   settings event subscriptions page.
4. **Check the bot logs.** Run with `LOG_LEVEL=DEBUG` and look for incoming
   events. If no events appear, the issue is on the Slack side.
5. **Confirm tokens are correct.** A wrong `SLACK_BOT_TOKEN` or
   `SLACK_SIGNING_SECRET` will silently drop events.

### Bot is not responding to DMs

1. Ensure `im:history`, `im:read`, and `im:write` scopes are added.
2. Ensure `message.im` is subscribed under Event Subscriptions.
3. Reinstall the app to the workspace after adding new scopes.

### "You've reached the rate limit" message

The bot enforces per-user and per-channel rate limits. If you hit this during
testing, either:
- Wait for the window to expire (1 minute for user limits, 1 hour for channel
  limits).
- Increase the limits via `RATE_LIMIT_PER_USER` and `RATE_LIMIT_PER_CHANNEL`.

### Slash command says "This app responded with an error"

Slack requires a response within 3 seconds. If the bot is slow to start (cold
start on free hosting tiers), the command will time out. Solutions:
- Use a hosting provider that keeps the process warm.
- Use Socket Mode instead of HTTP mode (Socket Mode does not have this issue).

### Permission errors from Slack API

If the bot logs show `missing_scope` or `not_in_channel` errors:
1. Go to **OAuth & Permissions** and verify all scopes from the table above
   are added.
2. **Reinstall the app** to the workspace. Scope changes only take effect
   after reinstallation.

### Vaquill API errors

- **401 Unauthorized**: Your `VAQUILL_API_KEY` is invalid or expired. Generate
  a new one at [vaquill.ai](https://vaquill.ai).
- **429 Too Many Requests**: You have exceeded your Vaquill API rate limit.
  Check your plan's usage limits.
- **5xx errors**: The Vaquill API is temporarily unavailable. The bot will show
  a generic error message to the user.

### Redis connection issues

If `REDIS_URL` is set but Redis is unreachable, the bot falls back to
in-memory rate limiting. You will see a warning in the logs. This is safe for
single-instance deployments but means rate limits are not shared across
multiple bot instances.

### Bot responds to its own messages (infinite loop)

This should not happen if `IGNORE_BOT_MESSAGES=true` (the default). If it
does, check that the bot's user ID is being detected correctly at startup. The
log line `Bot initialised with user ID: U0XXXXXXX` should appear.

---

## Project Structure

```
integrations/slack-bot/
  bot.py                  # Entry point, Slack event handlers
  vaquill_client.py       # Vaquill API wrapper
  config.py               # Environment variable management
  conversation_manager.py # Thread-aware session tracking
  rate_limiter.py         # Sliding window rate limiter (Redis or in-memory)
  security_manager.py     # Input validation, user auth, safe error messages
  starter_questions.py    # Suggested starter questions
  analytics.py            # Usage tracking
  Dockerfile              # Container image
  docker-compose.yml      # Bot + Redis stack
  .env.example            # Template for environment variables
  requirements.txt        # Python dependencies
```

---

## License

MIT
