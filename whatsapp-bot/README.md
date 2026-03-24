# Vaquill WhatsApp Bot

A WhatsApp bot that connects to the [Vaquill Legal AI](https://vaquill.ai) platform via Twilio, giving users access to AI-powered legal research directly from WhatsApp. Ask questions about Indian law, statutes, and case law and get answers with cited sources.

## Architecture

```
                                     +------------------+
                                     |  Vaquill API     |
                                     |  /ask endpoint   |
                                     +--------+---------+
                                              ^
                                              | 3. POST /ask
                                              |    {question, mode,
                                              |     chatHistory}
+----------+     +---------+     +-----------+----------+     +-------+
|          | 1.  |         | 2.  |                      |     |       |
| WhatsApp +---->+ Twilio  +---->+  FastAPI Bot Server   +---->+ Redis |
|  User    |     | Cloud   |     |  /webhook/whatsapp   |     | (opt) |
|          |<----+         |<----+                      |     |       |
+----------+  6. +---------+  5. +----------+-----------+     +-------+
             Send           Return           |                 Sessions
             reply          TwiML            | 4. Format       Rate limits
                                             |    answer +     Analytics
                                             |    sources
                                             v
                                     +------------------+
                                     | Session Manager  |
                                     | (chat history,   |
                                     |  mode, language)  |
                                     +------------------+
```

**Flow:**

1. User sends a WhatsApp message.
2. Twilio forwards the message as an HTTP POST to your bot's `/webhook/whatsapp` endpoint.
3. The bot calls the Vaquill `/ask` API with the question, research mode, and conversation history.
4. The response (answer + sources) is formatted for WhatsApp.
5. An immediate empty TwiML response is returned to Twilio (prevents retries).
6. The bot sends the formatted reply back to the user via the Twilio Messages API.

**Key design decisions:**

- **Stateless API**: Chat history is maintained client-side (Redis or in-memory) and sent with each `/ask` request. The Vaquill API does not require session or project IDs.
- **Fire-and-forget processing**: The webhook returns an empty TwiML immediately, then processes the message asynchronously. This avoids Twilio's 15-second timeout.
- **Two research modes**: `standard` (18 techniques, gpt-5-mini) and `deep` (35 techniques, gpt-5.2, multi-hop reasoning).

---

## Prerequisites

Before you begin, make sure you have the following:

| Requirement | Details |
|---|---|
| **Python 3.10+** | 3.12 recommended |
| **Vaquill API key** | Obtain from [vaquill.ai](https://vaquill.ai). Starts with `vq_key_` |
| **Twilio account** | Free trial works for development. See [Twilio Setup](#twilio-setup-step-by-step) below |
| **ngrok** (local dev only) | Free account at [ngrok.com](https://ngrok.com) for tunneling webhooks to localhost |
| **Redis** (optional) | Only needed for persistent sessions/rate-limits across restarts or multi-instance deployments |

---

## Twilio Setup (Step by Step)

Twilio is the bridge between WhatsApp and your bot. It receives WhatsApp messages and forwards them as HTTP requests to your server.

### Step 1: Create a Twilio Account

1. Go to [twilio.com/try-twilio](https://www.twilio.com/try-twilio) and sign up. The free trial gives you $15 in credit (enough for thousands of sandbox messages).
2. Verify your email address and phone number.
3. When prompted for your use case, select **"Developer"** or **"WhatsApp"**.

### Step 2: Get Your Credentials

1. Log in to the [Twilio Console](https://console.twilio.com).
2. On the dashboard, locate:
   - **Account SID** -- starts with `AC` (e.g., `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
   - **Auth Token** -- click the eye icon to reveal it
3. Save both values. You will need them for your `.env` file.

### Step 3: Activate the WhatsApp Sandbox

The sandbox lets you test immediately without business verification.

1. In the Twilio Console, navigate to **Messaging** > **Try it out** > **Send a WhatsApp message**.
2. You will see a sandbox number (typically `+1 (415) 523-8886`) and a join code.
3. From your personal WhatsApp, send the message shown (e.g., `join <your-keyword>`) to the sandbox number.
4. You should receive a confirmation: *"You are all set!"*

**Note the sandbox number** -- it will be your `TWILIO_WHATSAPP_NUMBER` value (e.g., `whatsapp:+14155238886`).

### Step 4: Configure the Webhook URL

This tells Twilio where to forward incoming WhatsApp messages.

1. In the Twilio Console, go to **Messaging** > **Try it out** > **Send a WhatsApp message**.
2. Scroll down to **Sandbox Configuration**.
3. In the **"When a message comes in"** field, enter your bot's webhook URL:
   - **Local development**: `https://<your-ngrok-subdomain>.ngrok-free.app/webhook/whatsapp`
   - **Production**: `https://your-domain.com/webhook/whatsapp`
4. Set the method to **POST**.
5. Click **Save**.

### Step 5: Test the Connection

Send any message (e.g., "Hello") from WhatsApp to the sandbox number. If everything is configured correctly, you should receive a response from the bot.

### Sandbox Limitations

The free WhatsApp sandbox has restrictions you should be aware of:

| Limitation | Details |
|---|---|
| **Join required** | Every user must send `join <keyword>` before receiving messages |
| **24-hour window** | You can only reply within 24 hours of the user's last message |
| **Shared number** | Messages come from Twilio's shared sandbox number |
| **Development only** | Not suitable for production use with real customers |
| **Session timeout** | Sandbox sessions expire; users may need to rejoin |

### Upgrading to a Production WhatsApp Number

For production deployments with real users:

1. **Upgrade to a paid Twilio account** (trial accounts cannot register WhatsApp senders).
2. In the Twilio Console, go to **Messaging** > **Senders** > **WhatsApp Senders**.
3. Click **Register a WhatsApp Sender** and follow the guided process:
   - Register your business with Meta/Facebook.
   - Submit your WhatsApp Business Profile for review.
   - Get a dedicated phone number assigned.
   - Submit message templates for approval (required for outbound messages outside the 24-hour window).
4. Verification typically takes 2-5 business days.
5. Once approved, update `TWILIO_WHATSAPP_NUMBER` in your `.env` to your new number.

| Feature | Sandbox (Free) | Production (Paid) |
|---|---|---|
| **Cost** | Free | ~$15/month + $0.005/message |
| **Phone number** | Twilio's shared number | Your own business number |
| **User onboarding** | Must send "join [keyword]" | Direct messaging |
| **Message window** | 24 hours after user message | 24 hours + template messages |
| **Business profile** | Twilio's profile | Your verified business |
| **Setup time** | 5 minutes | 2-5 business days |

---

## Quick Start (Local Development)

### 1. Clone and Install

```bash
cd integrations/whatsapp-bot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# Required
VAQUILL_API_KEY=vq_key_your_key_here
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Optional — adjust as needed
VAQUILL_MODE=standard
VAQUILL_COUNTRY_CODE=IN
RATE_LIMIT_DAILY=100
```

### 3. Start the Bot

You need **two terminals** running simultaneously:

**Terminal 1 -- Run the bot:**

```bash
# Development (auto-reload on file changes)
DEBUG=true python bot.py

# OR production mode
uvicorn bot:app --host 0.0.0.0 --port 8000
```

**Terminal 2 -- Run ngrok** (exposes localhost to the internet):

```bash
# First time only: configure your auth token
ngrok config add-authtoken YOUR_NGROK_AUTH_TOKEN

# Start the tunnel
ngrok http 8000
```

ngrok will display a forwarding URL like `https://abc123.ngrok-free.app`. Copy the HTTPS URL.

### 4. Update Twilio Webhook

1. Go to the Twilio Console > **Messaging** > **Try it out** > **Send a WhatsApp message** > **Sandbox Configuration**.
2. Set the webhook URL to: `https://abc123.ngrok-free.app/webhook/whatsapp`
3. Method: **POST**
4. Save.

> **Note:** ngrok free-tier URLs change every time you restart ngrok. You must update the Twilio webhook URL each time. For a stable URL, use a paid ngrok plan or deploy to a cloud host.

### 5. Test

1. Send "Hi" to the Twilio sandbox number from WhatsApp.
2. You should receive a welcome message.
3. Try a legal question: *"What is Section 302 of the Indian Penal Code?"*

---

## Docker Deployment

### Build and Run

```bash
docker build -t vaquill-whatsapp-bot .
docker run -p 8000:8000 --env-file .env vaquill-whatsapp-bot
```

### With Docker Compose (including Redis)

Create a `docker-compose.yml`:

```yaml
version: "3.9"

services:
  bot:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped

volumes:
  redis-data:
```

```bash
docker compose up -d
```

### Dockerfile Details

The included `Dockerfile` uses `python:3.12-slim`, runs as a non-root user (`botuser`), and includes a health check that polls `/health` every 30 seconds.

---

## Cloud Deployment

Once deployed, update your Twilio webhook URL to point to your production domain (e.g., `https://your-app.example.com/webhook/whatsapp`).

### Option 1: Render

1. Sign up at [render.com](https://render.com) and connect your GitHub repository.
2. Create a **New Web Service**:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
3. Add all environment variables from `.env` under the **Environment** tab.
4. Deploy. Your URL will be `https://your-app.onrender.com`.
5. Set webhook: `https://your-app.onrender.com/webhook/whatsapp`

> **Note:** Render's free tier spins down after inactivity. The first message after a cold start may take 30-60 seconds. Use a paid instance or an uptime monitor (e.g., [UptimeRobot](https://uptimerobot.com)) to keep it warm.

### Option 2: Railway

1. Sign up at [railway.app](https://railway.app) and connect your GitHub repository.
2. Railway auto-detects Python. Click **Deploy**.
3. Go to **Variables** and add all environment variables from `.env`.
4. Go to **Settings** > **Domains** to get your URL.
5. Set webhook: `https://your-app.up.railway.app/webhook/whatsapp`

```bash
# Or deploy via CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

### Option 3: Fly.io

```bash
# Install CLI and sign up
curl -L https://fly.io/install.sh | sh
fly auth signup

# Launch (from the whatsapp-bot directory)
fly launch

# Set secrets
fly secrets set VAQUILL_API_KEY="vq_key_..."
fly secrets set TWILIO_ACCOUNT_SID="AC..."
fly secrets set TWILIO_AUTH_TOKEN="..."
fly secrets set TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886"

# Deploy
fly deploy

# Get URL
fly status
# => https://your-app.fly.dev
```

Set webhook: `https://your-app.fly.dev/webhook/whatsapp`

### Deployment Comparison

| Platform | Free Tier | Cold Start | Persistent Storage | Best For |
|---|---|---|---|---|
| **Render** | 750 hrs/month | Yes (free tier) | Yes | Simple deployments |
| **Railway** | $5 credit/month | No | Yes | Production-ready |
| **Fly.io** | 3 shared VMs | No | Yes | Low-latency, global |

---

## Commands

Users interact with the bot by sending messages to WhatsApp. Slash commands control bot behavior:

| Command | Description |
|---|---|
| `/start` | Start a new conversation and show a welcome message with example questions |
| `/help` | Show all available commands and usage tips |
| `/examples` | List example legal questions by category. Use `/examples criminal` for a specific category |
| `/mode` | Show the current research mode |
| `/mode standard` | Switch to standard mode (18 techniques, fast responses) |
| `/mode deep` | Switch to deep mode (35 techniques, multi-hop reasoning, slower but more thorough) |
| `/stats` | View your usage statistics (messages today, this hour, total) |
| `/language` | Show current language and available options |
| `/language hi` | Change response language (supports: en, hi, es, fr, de, pt, ja, ko, zh, ar) |
| `/clear` | Clear conversation history and start fresh |
| `/feedback <message>` | Send feedback to the bot operators |
| `/about` | Show information about Vaquill |
| `/settings` | View all current settings (language, mode, limits) |

Any message that does not start with `/` is treated as a legal question and sent to the Vaquill API.

---

## Environment Variable Reference

### Required

| Variable | Description | Example |
|---|---|---|
| `VAQUILL_API_KEY` | Your Vaquill API key | `vq_key_abc123...` |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID (starts with `AC`) | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_WHATSAPP_NUMBER` | Twilio WhatsApp number (include `whatsapp:` prefix) | `whatsapp:+14155238886` |

### Vaquill API

| Variable | Default | Description |
|---|---|---|
| `VAQUILL_API_URL` | `https://api.vaquill.ai/api/v1` | Vaquill API base URL |
| `VAQUILL_MODE` | `standard` | Default research mode (`standard` or `deep`) |
| `VAQUILL_COUNTRY_CODE` | `IN` | Default jurisdiction code (`IN`, `US`, `CA`, etc.) |

### Rate Limiting

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_DAILY` | `100` | Maximum messages per user per day |
| `RATE_LIMIT_MINUTE` | `5` | Maximum messages per user per minute |
| `RATE_LIMIT_HOUR` | `30` | Maximum messages per user per hour |

### Security

| Variable | Default | Description |
|---|---|---|
| `ALLOWED_NUMBERS` | *(empty -- all allowed)* | Comma-separated phone numbers to allowlist. Leave empty to allow all |
| `BLOCKED_NUMBERS` | *(empty)* | Comma-separated phone numbers to blocklist |
| `MAX_MESSAGE_LENGTH` | `1000` | Maximum allowed message length in characters |
| `ENABLE_PROFANITY_FILTER` | `false` | Enable profanity filtering (requires `better-profanity` package) |

### Redis (Optional)

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | *(not set)* | Redis connection string. When not set, the bot uses in-memory storage. In-memory storage works for single-instance deployments and development but does not persist across restarts |

### Admin

| Variable | Default | Description |
|---|---|---|
| `ADMIN_API_KEY` | *(not set)* | API key for admin endpoints (`/stats/{phone}`, `/broadcast`) |
| `ADMIN_NUMBERS` | *(not set)* | Comma-separated admin phone numbers (get 10x rate limits) |

### Features

| Variable | Default | Description |
|---|---|---|
| `ENABLE_THINKING_MESSAGE` | `false` | Send a "Thinking..." message while processing. Can cause issues with slow API responses |
| `ENABLE_MEDIA_RESPONSES` | `true` | Accept media attachments (currently responds with a placeholder message) |
| `ENABLE_VOICE_MESSAGES` | `true` | Accept voice messages |
| `ENABLE_LOCATION_SHARING` | `false` | Accept location messages |
| `DEFAULT_LANGUAGE` | `en` | Default response language code |

### Session

| Variable | Default | Description |
|---|---|---|
| `SESSION_TIMEOUT_MINUTES` | `30` | Session expiry time. After this, conversation context is cleared |
| `SESSION_CONTEXT_MESSAGES` | `10` | Number of recent messages to include as context in API calls |

### Analytics

| Variable | Default | Description |
|---|---|---|
| `ENABLE_ANALYTICS` | `true` | Enable usage analytics tracking |
| `ANALYTICS_RETENTION_DAYS` | `30` | Days to retain analytics data |

### Server

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Enable debug mode (auto-reload) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | None | Returns bot name, status, and version |
| `POST` | `/` | None | Redirects to `/webhook/whatsapp` (some Twilio configs hit root) |
| `GET` | `/health` | None | Health check. Returns service status for Vaquill, Redis, and Twilio |
| `POST` | `/webhook/whatsapp` | Twilio | Main webhook. Receives form-encoded data from Twilio (`From`, `Body`, `MessageSid`, `MediaUrl0`, `NumMedia`) |
| `GET` | `/stats/{phone_number}` | `api_key` query param | Admin endpoint. Returns usage statistics for a given phone number |
| `POST` | `/broadcast` | `api_key` in body | Admin endpoint. Sends a message to multiple recipients |

### Webhook Request Format

Twilio sends form-encoded POST data to `/webhook/whatsapp`:

| Field | Example | Description |
|---|---|---|
| `From` | `whatsapp:+919876543210` | Sender's WhatsApp number |
| `Body` | `What is Article 21?` | Message text |
| `MessageSid` | `SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | Unique message identifier |
| `NumMedia` | `0` | Number of media attachments |
| `MediaUrl0` | `https://...` | URL of the first media attachment (if any) |

### Admin Endpoint Examples

```bash
# Get user stats
curl "http://localhost:8000/stats/+919876543210?api_key=your-admin-api-key"

# Broadcast a message
curl -X POST http://localhost:8000/broadcast \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-admin-api-key",
    "message": "Scheduled maintenance tonight at 10 PM IST.",
    "recipients": ["+919876543210", "+919876543211"]
  }'
```

---

## Troubleshooting

### Bot Not Responding at All

**Check that both services are running:**
- The bot (`python bot.py`) must be running in one terminal.
- ngrok (`ngrok http 8000`) must be running in another terminal (for local development).

**Verify the webhook URL in Twilio:**
1. Go to Twilio Console > Messaging > Try it out > Send a WhatsApp message > Sandbox Configuration.
2. Confirm the URL matches your ngrok URL or production domain, ending in `/webhook/whatsapp`.
3. Confirm the method is **POST**.

**Test the bot directly:**

```bash
# Health check
curl http://localhost:8000/health

# Simulate a Twilio webhook
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+919876543210&Body=Hello&MessageSid=test123"
```

If the health check fails, the bot is not running. If the webhook test returns XML but WhatsApp does not respond, the issue is between Twilio and your server.

### Twilio Authentication Errors

- **Account SID must start with `AC`**. Values starting with `US` or other prefixes are not Account SIDs.
- Double-check both `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` in your `.env`.
- Test your credentials directly:

```bash
curl "https://api.twilio.com/2010-04-01/Accounts/YOUR_ACCOUNT_SID.json" \
  -u "YOUR_ACCOUNT_SID:YOUR_AUTH_TOKEN"
```

A `200 OK` means credentials are valid. A `401 Unauthorized` means they are wrong.

### ngrok URL Changed

ngrok free-tier assigns a new URL every time you restart it. After restarting ngrok:
1. Copy the new HTTPS URL from the ngrok terminal output.
2. Update the webhook URL in the Twilio Console.
3. Save the configuration.

For a permanent URL, either use a paid ngrok plan or deploy to a cloud host.

### Messages Arrive but No Reply

Check the bot terminal for errors. Common causes:

- **Invalid Vaquill API key**: Verify `VAQUILL_API_KEY` is correct and starts with `vq_key_`.
- **API credits exhausted**: The bot logs `insufficient_credits` errors. Top up at [vaquill.ai](https://vaquill.ai).
- **Rate limited**: The user has hit their daily/minute limit. Check with the `/stats` command.

### "You Are Not Authorized" Message

- If `ALLOWED_NUMBERS` is set in `.env`, only those numbers can use the bot. Clear it (leave empty) to allow all numbers.
- If `BLOCKED_NUMBERS` contains the user's number, remove it.

### Sandbox Session Expired

If you stop receiving responses after a period of inactivity:
1. Send the sandbox join message again (e.g., `join <your-keyword>`) to the Twilio sandbox number.
2. Try sending a message again.

### Slow Responses

- Switch from `deep` to `standard` mode for faster responses: send `/mode standard`.
- Deep mode uses 35 retrieval techniques and a more powerful model. It is intentionally slower but more thorough.
- Check the Vaquill API status if response times are consistently above 15 seconds.

### Redis Connection Issues

- Redis is **optional**. If `REDIS_URL` is not set, the bot uses in-memory storage.
- If Redis is configured but unavailable, check the `/health` endpoint. The `redis` field will show the connection status.
- In-memory fallback works for single-instance deployments. Data is lost on restart.

### Testing Twilio Message Delivery

Send a test message directly via the Twilio API to confirm message delivery works independently of the bot:

```bash
curl "https://api.twilio.com/2010-04-01/Accounts/YOUR_ACCOUNT_SID/Messages.json" \
  -X POST \
  --data-urlencode "To=whatsapp:+919876543210" \
  --data-urlencode "From=whatsapp:+14155238886" \
  --data-urlencode "Body=Test message from Twilio" \
  -u "YOUR_ACCOUNT_SID:YOUR_AUTH_TOKEN"
```

Expected response: `201 Created` with `"status": "queued"`.

### Common HTTP Status Codes from Twilio

| Code | Meaning | Fix |
|---|---|---|
| `201` | Message queued successfully | No issue |
| `400` | Invalid parameters | Check phone number format (must include country code) |
| `401` | Invalid credentials | Verify Account SID and Auth Token |
| `429` | Rate limit exceeded | Slow down or upgrade your Twilio plan |
| `21608` | Recipient not in sandbox | User must send "join [keyword]" first |

---

## Security Best Practices

### Credentials Management

- **Never commit `.env` files** to version control. The repository includes `.env.example` as a template.
- Use your hosting platform's secret management (Railway Variables, Render Environment, Fly Secrets) for production.
- Rotate `TWILIO_AUTH_TOKEN` and `VAQUILL_API_KEY` periodically.

### Webhook Validation

The bot currently accepts all incoming POST requests to `/webhook/whatsapp`. For production, consider validating Twilio request signatures to ensure requests genuinely come from Twilio:

```python
from twilio.request_validator import RequestValidator

validator = RequestValidator(auth_token)
is_valid = validator.validate(url, params, signature)
```

See [Twilio's Security documentation](https://www.twilio.com/docs/usage/security) for details.

### Access Control

- Use `ALLOWED_NUMBERS` to restrict the bot to specific phone numbers during testing or private deployments.
- Use `BLOCKED_NUMBERS` to block abusive users.
- Admin numbers (set via `ADMIN_NUMBERS`) receive 10x rate limits but are not exempt from security checks.

### Rate Limiting

Rate limiting is always active and applies per phone number:
- **Minute limit**: Prevents burst abuse.
- **Hourly limit**: Prevents sustained abuse.
- **Daily limit**: Caps total usage per user per day.

For production, enable Redis-backed rate limiting (`REDIS_URL`) so limits persist across restarts.

### Input Validation

The `SecurityManager` validates all incoming messages against:
- SQL injection patterns
- XSS (cross-site scripting) patterns
- Command injection patterns
- Message length limits
- Optional profanity filtering

Messages that fail validation receive a generic "Invalid message format" response. The specific attack type is logged server-side but never exposed to the user.

### Data Privacy

- The bot does not log full message contents by default. Only the first 50 characters are logged for debugging.
- Conversation history is stored in memory (or Redis) and expires after `SESSION_TIMEOUT_MINUTES`.
- No message data is sent to third parties beyond the Vaquill API and Twilio.

---

## Project Structure

```
whatsapp-bot/
  bot.py                 # FastAPI application, webhook handler, message processing
  config.py              # Pydantic settings, response templates, starter questions
  vaquill_client.py      # Async HTTP client for the Vaquill /ask API
  command_handler.py     # Slash-command routing and handlers
  session_manager.py     # Conversation history and user preferences (Redis or in-memory)
  rate_limiter.py        # Per-user rate limiting (Redis or in-memory)
  security_manager.py    # Phone allowlist/blocklist, input validation, injection detection
  analytics.py           # Usage tracking and statistics
  starter_questions.py   # Follow-up question suggestions
  requirements.txt       # Python dependencies
  Dockerfile             # Production container image
  .env.example           # Environment variable template
```

---

## Why Twilio?

WhatsApp requires all bots to connect through either the WhatsApp Business API directly (complex setup, business verification, 2-4 weeks) or through an official Business Solution Provider like Twilio (minutes to set up, free sandbox for testing). Twilio is the simplest path.

**Alternatives to Twilio:** MessageBird, Vonage (Nexmo), 360dialog, CM.com, and WATI all provide similar WhatsApp Business API access.

## Why Redis Is Optional

The bot includes built-in in-memory storage that works for:
- Development and testing
- Single-instance deployments
- Small user bases (under 100 users)

Redis is only necessary when you need:
- Persistent rate limits and sessions across restarts
- Multiple bot instances behind a load balancer
- High-volume deployments (over 1,000 users)

---

## License

MIT
