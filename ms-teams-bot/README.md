# Vaquill Microsoft Teams Bot

A production-ready Microsoft Teams bot that brings AI-powered legal research into Teams conversations via the [Vaquill API](https://www.vaquill.ai/docs/api-reference/).

> **Quick Links**: [Prerequisites](#prerequisites) | [Getting Credentials](#getting-credentials) | [Setup](#quick-setup) | [Deployment](#deployment) | [Troubleshooting](#troubleshooting)

---

## Features

- AI-powered legal Q&A via Vaquill API (standard and deep research modes)
- Multi-turn conversation with context (client-side chat history)
- Rich Adaptive Cards with source citations (case name, court, citation, PDF links)
- Rate limiting (per-user, per-channel, per-tenant) with Redis or in-memory
- Security controls: tenant/channel allowlists, user blocklists
- Slash commands: `/help`, `/clear`, `/status`
- Thread support with @mentions in channels

---

## Prerequisites

| Requirement | Free Tier | Purpose |
|-------------|-----------|---------|
| [Azure Account](https://azure.microsoft.com/free/) | Yes | Bot registration and hosting |
| [Vaquill API Key](https://www.vaquill.ai/dashboard) | Trial | Legal AI API (`vq_key_...`) |
| Microsoft Teams Admin | - | Install bot in Teams |
| Python 3.10+ | Yes | Runtime |
| Redis (Optional) | Yes | Distributed rate limiting |

---

## Getting Credentials

You need 3 credentials to run the bot.

### 1. Microsoft Teams Credentials (Azure Portal)

#### Step 1: Create App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Search for **"Microsoft Entra ID"** > **"App registrations"** > **"+ New registration"**
3. Fill in:
   ```
   Name: vaquill-teams-bot
   Supported account types: Single tenant (recommended) or Multi-tenant
   Redirect URI: Leave blank
   ```
4. Click **"Register"**
5. **Copy the Application (Client) ID** — save as `TEAMS_APP_ID`

#### Step 2: Create Client Secret

1. Left menu > **"Certificates & secrets"** > **"Client secrets"** tab
2. Click **"+ New client secret"**
3. Description: `Teams Bot Secret`, Expires: **24 months**
4. Click **"Add"**
5. **Immediately copy the Value** — save as `TEAMS_APP_PASSWORD`

> Copy the **Value**, not the "Secret ID". You can only see it once.

#### Step 3: Create Azure Bot Resource

1. [Azure Portal](https://portal.azure.com) > **"Create a resource"** > **"Azure Bot"**
2. Fill in:
   - Bot handle: `vaquill-teams-bot`
   - Pricing tier: **F0 (Free)**
   - Microsoft App ID: Enter the ID from Step 1
3. **"Review + Create"** > **"Create"**

#### Step 4: Enable Teams Channel

1. Go to your Azure Bot > **"Channels"** > **"Microsoft Teams"** icon > **"Apply"**

### 2. Vaquill API Key

1. Go to [Vaquill Dashboard](https://www.vaquill.ai/dashboard)
2. Generate an API key (starts with `vq_key_`)
3. Save as `VAQUILL_API_KEY`

---

## Quick Setup

### Step 1: Clone and Install

```bash
git clone https://github.com/Vaquill-AI/integrations.git
cd integrations/ms-teams-bot

python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# OR: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
cp .env.example .env
nano .env  # or any text editor
```

**Required Configuration**:
```env
# Microsoft Teams (from Azure Portal)
TEAMS_APP_ID=12345678-1234-1234-1234-123456789abc
TEAMS_APP_PASSWORD=abc123~XYZ456.789def-GHI012_JKL345
TEAMS_APP_TYPE=MultiTenant

# Vaquill API
VAQUILL_API_KEY=vq_key_your_key_here
```

### Step 3: Start the Bot

```bash
source venv/bin/activate
python3 app.py
```

**Expected Output**:
```
INFO - Vaquill client initialized
INFO - Rate limiter initialized
INFO - Bot initialization complete
 * Running on http://0.0.0.0:3978
```

### Step 4: Verify Health

```bash
curl http://localhost:3978/health
```

---

## Configuration

### Rate Limiting

```env
RATE_LIMIT_PER_USER=20      # Messages per minute per user
RATE_LIMIT_PER_CHANNEL=100  # Messages per hour per channel
RATE_LIMIT_PER_TENANT=500   # Messages per hour per organization
```

### Security & Access Control

```env
ALLOWED_TENANTS=tenant-id-1,tenant-id-2    # Restrict to specific orgs
ALLOWED_CHANNELS=channel-id-1,channel-id-2  # Restrict to specific channels
BLOCKED_USERS=user-id-1,user-id-2           # Block specific users
```

### Conversation Settings

```env
CONVERSATION_TIMEOUT=86400   # 24 hours (seconds)
MAX_CONTEXT_MESSAGES=10      # Messages to keep in chat history
ENABLE_THREADING=true
```

### Vaquill Settings

```env
VAQUILL_API_URL=https://api.vaquill.ai/api/v1    # API base URL
VAQUILL_MODE=standard                             # standard or deep
VAQUILL_COUNTRY_CODE=IN                           # ISO country code (optional)
SHOW_SOURCES=true                                 # Show case citations
```

### Bot Behavior

```env
MAX_MESSAGE_LENGTH=4000
REQUIRE_MENTION_IN_CHANNELS=true
ENABLE_ADAPTIVE_CARDS=true
RESPONSE_TIMEOUT=30
LOG_LEVEL=INFO
PORT=3978
```

---

## Deployment

### Local Development with ngrok

1. **Start your bot**:
   ```bash
   source venv/bin/activate
   python3 app.py
   ```

2. **In another terminal, start ngrok**:
   ```bash
   ngrok http 3978
   ```

3. **Copy the HTTPS URL** from ngrok output and add `/api/messages`:
   ```
   https://631af35e4e38.ngrok-free.app/api/messages
   ```

4. **Update Azure Bot messaging endpoint**:
   - Azure Portal > Your Bot > Configuration
   - Paste the URL in **Messaging endpoint**
   - Click **"Apply"**

> Free ngrok URLs change on restart — you'll need to update Azure each time.

### Docker

```bash
docker build -t vaquill-teams-bot .
docker run -d --name teams-bot -p 3978:3978 --env-file .env vaquill-teams-bot
docker logs -f teams-bot
```

### Azure Web App

```bash
az webapp up \
  --name vaquill-teams-bot \
  --resource-group vaquill-rg \
  --runtime "PYTHON:3.12" \
  --sku B1

# Set env vars in Azure Portal > Web App > Configuration > Application settings
# Set messaging endpoint to: https://vaquill-teams-bot.azurewebsites.net/api/messages
```

### Free Cloud Hosting

**Railway.app**: Fork repo > [railway.app](https://railway.app) > New project from GitHub > Add env vars > Deploy > Copy URL > Update Azure endpoint.

**Render.com**: Create Web Service > Connect GitHub > Set env vars > Deploy.

---

## Install in Microsoft Teams

### Step 1: Create Teams App Package

1. Create a `deployment/` folder with:
   - `manifest.json` — set `botId` to your `TEAMS_APP_ID`
   - `color.png` — 192x192px icon
   - `outline.png` — 32x32px icon

2. Create ZIP:
   ```bash
   cd deployment
   zip -r vaquill-bot.zip manifest.json color.png outline.png
   ```

### Step 2: Upload to Teams

**Direct Upload**:
1. Open Teams > **Apps** > **Manage your apps** > **Upload an app**
2. Choose **"Upload a custom app"**
3. Select `vaquill-bot.zip`

**Developer Portal** (if you hit duplicate errors):
1. Visit https://dev.teams.microsoft.com/apps
2. Click **"Import app"** > Upload ZIP
3. Click **"Publish"** > **"Publish to org"**

### Step 3: Test

- **Personal Chat**: Send a direct message to the bot
- **Channel**: `@Vaquill Bot what is Section 302 IPC?`
- **Commands**: Try `/help`

---

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/clear` | Clear conversation history |
| `/status` | Check rate limits and bot status |

## Usage

**Personal Chat**:
```
You: What is the test for negligence under tort law?
Bot: [Adaptive Card with answer + source citations]
```

**In Channels** (requires @mention):
```
You: @Vaquill Bot compare murder and culpable homicide under IPC
Bot: [Detailed comparison with case law citations]
```

**In Threads**:
```
You: Tell me about Section 302 IPC
Bot: Section 302 deals with punishment for murder...
You: (reply in thread) How does that compare to Section 304?
Bot: (continues in thread with context) Section 304 covers...
```

---

## Architecture

```
app.py                  Flask entry point, Bot Framework adapter
bot.py                  VaquillTeamsBot (ActivityHandler)
vaquill_client.py       Async Vaquill API client (POST /api/v1/ask)
conversation_manager.py Client-side chat history (Redis or in-memory)
rate_limiter.py         Sliding-window rate limiter
adaptive_cards.py       Adaptive Card templates for responses/sources
auth_handler.py         Teams JWT / tenant validation
input_validator.py      Input sanitization and injection detection
config.py               Environment-based configuration
```

---

## Troubleshooting

### Bot Not Responding

1. **Check messaging endpoint**: Azure Portal > Bot > Configuration — must end with `/api/messages`
2. **Check bot is installed**: Teams > Apps > Manage your apps
3. **Check logs**: `docker logs teams-bot` or terminal output
4. **Try personal chat first** to isolate channel permission issues

### Authentication Errors

1. Verify `TEAMS_APP_ID` matches Azure Portal > Bot > Configuration
2. Regenerate client secret if expired (Azure > Certificates & secrets)
3. Restart bot after updating credentials

### Vaquill API Errors

Test the API directly:
```bash
curl -X POST https://api.vaquill.ai/api/v1/ask \
  -H "Authorization: Bearer vq_key_your_key" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Section 302 IPC?"}'
```

Common errors:
- **401**: Invalid API key — check `VAQUILL_API_KEY`
- **402**: Insufficient credits — top up at [vaquill.ai/dashboard](https://www.vaquill.ai/dashboard)
- **429**: Rate limited — wait and retry

### Rate Limit Issues

Increase limits in `.env`:
```env
RATE_LIMIT_PER_USER=30
RATE_LIMIT_PER_CHANNEL=200
```

Or use Redis for distributed rate limiting:
```env
REDIS_URL=redis://localhost:6379
```

### Debug Mode

```env
LOG_LEVEL=DEBUG
```

---

## Security Best Practices

- Never commit `.env` or secrets
- Enable tenant restrictions in production: `ALLOWED_TENANTS=your-tenant-id`
- Use Azure Key Vault for production credential management
- Rotate secrets every 3-6 months
- Always use HTTPS for the messaging endpoint

---

## License

MIT
