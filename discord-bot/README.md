# Vaquill Discord Bot

A Discord bot that integrates with the Vaquill Legal AI API to answer legal questions with source citations.

## Features

- **Legal AI Responses**: Powered by the Vaquill legal research engine
- **Conversation Memory**: Maintains per-channel chat history for multi-turn conversations
- **Source Citations**: Shows cited cases and statutes via toggle button
- **Starter Questions**: Interactive buttons for common legal questions
- **Pagination**: Handles long responses across multiple pages
- **Rate Limiting**: Per-user and per-channel limits with Redis or local fallback
- **Access Control**: Channel and role-based restrictions

## Setup

### 1. Prerequisites

- Python 3.10+
- Discord Bot Token ([Create a bot](https://discord.com/developers/applications))
- Vaquill API Key ([Get from Vaquill](https://vaquill.ai))

### 2. Installation

```bash
cd discord-bot
pip install -r requirements.txt
cp .env.example .env
```

### 3. Configuration

Edit `.env` with your credentials:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
VAQUILL_API_KEY=vq_key_your_api_key
```

### 4. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a New Application
3. Go to Bot section and create a bot
4. Copy the bot token
5. Enable **MESSAGE CONTENT INTENT** under Privileged Gateway Intents
6. Go to OAuth2 > URL Generator
7. Select scopes: `bot`, `applications.commands`
8. Select permissions: `Send Messages`, `Embed Links`, `Read Message History`
9. Use the generated URL to invite the bot to your server

### 5. Run

```bash
python bot.py
```

## Docker

```bash
docker build -t vaquill-discord-bot .
docker run --env-file .env vaquill-discord-bot
```

## Commands

| Command | Description |
|---------|-------------|
| `!ask [question]` | Ask a legal question |
| `!help` | Show help menu |
| `!starters` | Show starter questions |
| `!reset` | Reset channel conversation history |

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | *required* | Discord bot token |
| `VAQUILL_API_KEY` | *required* | Vaquill API key (`vq_key_...`) |
| `VAQUILL_API_URL` | `https://api.vaquill.ai/api/v1` | API base URL |
| `VAQUILL_MODE` | `standard` | RAG tier: `standard` or `deep` |
| `VAQUILL_COUNTRY_CODE` | | Country code: `IN`, `US`, `CA` |
| `DISCORD_COMMAND_PREFIX` | `!` | Bot command prefix |
| `RATE_LIMIT_PER_USER` | `10` | Queries per window per user |
| `RATE_LIMIT_PER_CHANNEL` | `30` | Queries per window per channel |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window (seconds) |
| `MAX_CHAT_HISTORY` | `20` | Max Q/A pairs kept per channel |
| `REDIS_URL` | `redis://localhost:6379` | Redis for distributed rate limiting |
| `ALLOWED_CHANNELS` | | Comma-separated channel IDs |
| `ALLOWED_ROLES` | | Comma-separated role IDs |
| `ENABLE_SOURCES` | `True` | Show source citations |
| `ENABLE_STARTER_QUESTIONS` | `True` | Enable starter questions |
