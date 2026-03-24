# Vaquill Discord Bot

A Discord bot that connects your server to the Vaquill Legal AI engine. Members can ask legal questions and receive answers with source citations, multi-turn conversation memory, and interactive pagination -- all from within Discord.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Discord Bot Setup](#discord-bot-setup)
- [Quick Start (Local Development)](#quick-start-local-development)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Commands](#commands)
- [Features](#features)
- [Environment Variable Reference](#environment-variable-reference)
- [Troubleshooting](#troubleshooting)

## Overview

The bot forwards questions from Discord to the Vaquill API, which runs a retrieval-augmented generation (RAG) pipeline over Indian, US, and Canadian legal corpora. Answers come back with numbered source citations (cases, statutes, sections) that users can reveal with a button click. Conversation history is kept per-channel so follow-up questions work naturally.

## Prerequisites

Before you begin, make sure you have:

1. **A Discord account** -- [Sign up at discord.com](https://discord.com) if you do not have one.
2. **Administrator access to a Discord server** -- You need the "Manage Server" permission to invite bots. Create your own server if needed (free).
3. **A Vaquill API key** -- Sign up at [vaquill.ai](https://vaquill.ai) and generate an API key from your dashboard. Keys follow the format `vq_key_...`.
4. **Python 3.10 or higher** -- Required for local development. Docker handles this automatically if you deploy with containers.

## Discord Bot Setup

Follow these steps exactly to create a Discord application, configure the bot user, and invite it to your server.

### Step 1: Create a Discord Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** in the top-right corner.
3. Enter a name (e.g., "Vaquill Legal AI") and click **Create**.

### Step 2: Create the Bot User

1. In the left sidebar of your new application, click **Bot**.
2. Click **Add Bot**, then confirm with **Yes, do it!**.
3. Under the bot's username, click **Reset Token** to generate a new token.
4. Click **Copy** to copy the token. Save it somewhere safe -- you will need it for the `DISCORD_BOT_TOKEN` environment variable. You cannot view this token again after leaving the page.

### Step 3: Enable the Message Content Intent

This step is required. Without it, the bot cannot read message content and will silently ignore all commands.

1. On the same **Bot** page, scroll down to **Privileged Gateway Intents**.
2. Find **Message Content Intent** and toggle it **ON**.
3. Click **Save Changes** at the bottom of the page.

### Step 4: Generate the Invite URL

1. In the left sidebar, click **OAuth2**, then **URL Generator**.
2. Under **Scopes**, check:
   - `bot`
   - `applications.commands`
3. Under **Bot Permissions**, check:
   - Send Messages
   - Embed Links
   - Read Message History
   - Use Slash Commands
   - Add Reactions
4. Copy the generated URL at the bottom of the page.

### Step 5: Add the Bot to Your Server

1. Open the URL you copied in a browser.
2. Select the server you want to add the bot to from the dropdown. You must have "Manage Server" permission on that server.
3. Click **Authorize** and complete the CAPTCHA.
4. The bot will appear in your server's member list (offline until you start it).

## Quick Start (Local Development)

```bash
# Clone and enter the directory
git clone https://github.com/vaquill/integrations.git
cd integrations/discord-bot

# Create a virtual environment
python -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Open `.env` in your editor and fill in the two required values:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
VAQUILL_API_KEY=vq_key_your_api_key_here
```

Start the bot:

```bash
python bot.py
```

The bot will log `VaquillBot has connected to Discord!` when it is ready. Go to your Discord server and type `!help` to verify.

## Docker Deployment

### Build and Run

```bash
docker build -t vaquill-discord-bot .
docker run -d --name vaquill-discord-bot --env-file .env vaquill-discord-bot
```

### View Logs

```bash
docker logs -f vaquill-discord-bot
```

### Stop and Remove

```bash
docker stop vaquill-discord-bot
docker rm vaquill-discord-bot
```

### Docker Compose

Create a `docker-compose.yml` alongside the Dockerfile:

```yaml
version: "3.8"

services:
  bot:
    build: .
    restart: unless-stopped
    env_file:
      - .env
```

Then run:

```bash
docker compose up -d
docker compose logs -f
```

## Cloud Deployment

### Railway

Railway offers a simple Git-based deploy workflow.

1. Sign up at [railway.app](https://railway.app).
2. Install the CLI:
   ```bash
   npm install -g @railway/cli
   ```
3. Deploy:
   ```bash
   cd discord-bot
   railway login
   railway init
   railway up
   ```
4. Set environment variables in the Railway dashboard under your service's **Variables** tab. Add `DISCORD_BOT_TOKEN` and `VAQUILL_API_KEY` at minimum.
5. Check logs:
   ```bash
   railway logs
   ```

### Render

1. Sign up at [render.com](https://render.com).
2. Create a **New Web Service** and connect your GitHub repository.
3. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
4. Add `DISCORD_BOT_TOKEN` and `VAQUILL_API_KEY` under **Environment** in the dashboard.
5. Deploy. Render auto-deploys on every push to the connected branch.

### VPS (Self-Hosted)

On any Linux VPS with Docker installed:

```bash
git clone https://github.com/vaquill/integrations.git
cd integrations/discord-bot
cp .env.example .env
nano .env   # fill in your values

docker compose up -d
```

For systemd-based deployments without Docker, create a service file:

```ini
[Unit]
Description=Vaquill Discord Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/vaquill-discord-bot
ExecStart=/opt/vaquill-discord-bot/venv/bin/python bot.py
Restart=always
RestartSec=10
EnvironmentFile=/opt/vaquill-discord-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo cp vaquill-discord-bot.service /etc/systemd/system/
sudo systemctl enable vaquill-discord-bot
sudo systemctl start vaquill-discord-bot

# Check status
sudo systemctl status vaquill-discord-bot
sudo journalctl -u vaquill-discord-bot -f
```

## Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `!ask [question]` | `!a`, `!q` | Ask a legal question. Supports follow-ups using channel conversation history. |
| `!starters` | `!start`, `!questions` | Show starter questions as interactive buttons. Click a button to ask that question. |
| `!reset` | | Clear the conversation history for the current channel. |
| `!help` | | Show the help menu with available commands. |

The command prefix defaults to `!` and can be changed with the `DISCORD_COMMAND_PREFIX` environment variable.

## Features

### Source Citations

When the Vaquill API returns source references (cases, statutes, sections), the bot adds a "Show Sources" button to the response. Clicking it reveals the list of cited sources. This can be disabled with `ENABLE_SOURCES=False`.

### Multi-Turn Conversations

The bot maintains per-channel conversation history so you can ask follow-up questions without repeating context. History is capped at the most recent `MAX_CHAT_HISTORY` question/answer pairs (default: 20). Use `!reset` to clear history for the current channel.

### Pagination

Long responses are automatically split across pages. The bot sends an embedded message with Previous/Next buttons for navigation. Only the original requester can page through their response.

### Starter Questions

The `!starters` command shows a set of pre-configured legal questions as clickable buttons. Clicking a button sends that question through the same pipeline as `!ask`. Disable with `ENABLE_STARTER_QUESTIONS=False`.

### Rate Limiting

Two independent limits are enforced:

- **Per-user**: Maximum queries per user within a sliding time window.
- **Per-channel**: Maximum queries per channel within the same window.

Limits use in-memory storage by default. Set `REDIS_URL` for persistent, distributed rate limiting across bot restarts or multiple instances.

### Access Control

Restrict the bot to specific channels or roles:

- `ALLOWED_CHANNELS`: Comma-separated list of Discord channel IDs. If empty, all channels are allowed.
- `ALLOWED_ROLES`: Comma-separated list of Discord role IDs. If empty, all roles are allowed.

### Typing Indicator

The bot shows a typing indicator while waiting for the Vaquill API response. Disable with `TYPING_INDICATOR=False`.

## Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | -- | Bot token from the Discord Developer Portal. |
| `VAQUILL_API_KEY` | Yes | -- | Vaquill API key (format: `vq_key_...`). |
| `VAQUILL_API_URL` | No | `https://api.vaquill.ai/api/v1` | Vaquill API base URL. Override for self-hosted or staging. |
| `VAQUILL_MODE` | No | `standard` | RAG tier. `standard` for faster responses, `deep` for more thorough analysis. |
| `VAQUILL_COUNTRY_CODE` | No | *(empty)* | Jurisdiction filter: `IN` (India), `US` (United States), `CA` (Canada). Empty means all. |
| `DISCORD_COMMAND_PREFIX` | No | `!` | Character(s) that prefix bot commands. |
| `RATE_LIMIT_PER_USER` | No | `10` | Maximum queries per user within the rate limit window. |
| `RATE_LIMIT_PER_CHANNEL` | No | `30` | Maximum queries per channel within the rate limit window. |
| `RATE_LIMIT_WINDOW` | No | `60` | Rate limit sliding window in seconds. |
| `MAX_CHAT_HISTORY` | No | `20` | Maximum question/answer pairs retained per channel. |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis connection URL. Only needed for distributed rate limiting. Falls back to in-memory if Redis is unavailable. |
| `ALLOWED_CHANNELS` | No | *(empty)* | Comma-separated Discord channel IDs. Empty allows all channels. |
| `ALLOWED_ROLES` | No | *(empty)* | Comma-separated Discord role IDs. Empty allows all roles. |
| `ENABLE_SOURCES` | No | `True` | Show source citation buttons on responses. |
| `ENABLE_STARTER_QUESTIONS` | No | `True` | Enable the `!starters` command. |
| `TYPING_INDICATOR` | No | `True` | Show typing indicator while processing. |

## Troubleshooting

### Bot appears offline in the server

- Verify `DISCORD_BOT_TOKEN` is correct. Regenerate it in the Developer Portal if unsure.
- Check that `python bot.py` is running without errors. Look at the console or container logs.
- If deploying on a cloud platform, confirm the service is not sleeping or out of free-tier hours.

### Bot is online but does not respond to commands

- **Message Content Intent not enabled.** This is the most common cause. Go to [Discord Developer Portal](https://discord.com/developers/applications) > your application > Bot > Privileged Gateway Intents and confirm **Message Content Intent** is toggled ON. Save changes and restart the bot.
- Check that you are using the correct prefix (default: `!`). Type `!help` exactly.
- If `ALLOWED_CHANNELS` or `ALLOWED_ROLES` is set, make sure your channel/role is included.

### "Privileged intent provided is not enabled or whitelisted" error on startup

This means Message Content Intent is not enabled. Follow the instructions in [Step 3: Enable the Message Content Intent](#step-3-enable-the-message-content-intent).

### "Missing Permissions" error when sending messages

The bot needs these permissions in the channel: Send Messages, Embed Links, Read Message History. Either:
- Re-invite the bot using the URL from [Step 4](#step-4-generate-the-invite-url) which includes the correct permissions.
- Manually grant the permissions to the bot's role in Server Settings > Roles.

### API errors ("Sorry, I couldn't process your request")

- Verify `VAQUILL_API_KEY` is valid and has not been revoked.
- Check that `VAQUILL_API_URL` is reachable from the machine running the bot.
- If using `VAQUILL_MODE=deep`, confirm your API plan supports deep-tier queries.

### Rate limit messages appearing too quickly

Adjust `RATE_LIMIT_PER_USER`, `RATE_LIMIT_PER_CHANNEL`, or `RATE_LIMIT_WINDOW` in your `.env` file. For example, to allow 20 queries per user per 2 minutes:

```env
RATE_LIMIT_PER_USER=20
RATE_LIMIT_WINDOW=120
```

### Redis connection errors in logs

Redis is optional. If `REDIS_URL` points to an unavailable Redis instance, the bot falls back to in-memory rate limiting. To silence the warnings, either start a Redis server or remove the `REDIS_URL` variable from your `.env`.
