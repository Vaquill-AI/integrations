# Vaquill Signal Bot

Signal messenger bot for [Vaquill AI](https://vaquill.ai) legal research. Uses [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) + [signalbot](https://github.com/signalbot-org/signalbot) framework.

## Architecture

```
User on Signal -> Signal Network -> signal-cli-rest-api (Docker)
                                          |
                                    WebSocket (json-rpc)
                                          |
                                    signalbot (Python)
                                          |
                                    Vaquill /ask API
                                          |
                                    RAG Pipeline
```

## Setup

### 1. Register your phone number (one-time)

```bash
# Start signal-cli-rest-api
docker compose up signal-cli -d

# Register (replace with your number)
curl -X POST "http://localhost:8080/v1/register/+91XXXXXXXXXX" \
  -H "Content-Type: application/json" \
  -d '{"use_voice": false}'

# Verify with SMS code
curl -X POST "http://localhost:8080/v1/register/+91XXXXXXXXXX/verify/CODE"
```

Alternative: link as secondary device (keeps your phone active):
```bash
# Get QR code link URI
curl "http://localhost:8080/v1/qrcodelink?device_name=vaquill-bot"
# Scan the QR code with your Signal app (Settings > Linked Devices)
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Run

```bash
# Both services
docker compose up -d

# Or just the bot (if signal-cli is already running)
docker compose up signal-bot -d
```

### 4. Verify

```bash
# Check signal-cli is connected
curl http://localhost:8080/v1/about

# Check registered accounts
curl http://localhost:8080/v1/accounts

# Send a test message to yourself
curl -X POST "http://localhost:8080/v2/send" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from Vaquill!", "number": "+91YOUR_NUMBER", "recipients": ["+91RECIPIENT"]}'
```

## Commands

| Command | Description |
|---------|-------------|
| help | Show available commands |
| examples | Show example legal questions |
| stats | View usage statistics |
| clear | Clear conversation history |
| hi/hello | Start fresh conversation |

Any other text is treated as a legal question and sent to the Vaquill RAG pipeline.

## Deployment (Dokploy)

Deploy as two separate applications in the `vaquill-integrations` project:

1. **signal-cli**: Docker image `bbernhard/signal-cli-rest-api`, env `MODE=json-rpc`, persistent volume for `/home/.local/share/signal-cli`
2. **signal-bot**: Build from this directory's Dockerfile, env vars from `.env`

## Risks

- **No official Signal bot API**. This uses the unofficial signal-cli project.
- **Account ban risk** if Signal detects bot-like behavior. Keep volume low.
- **signal-cli updates** can break on Signal protocol changes. Pin image versions in production.
- The phone number registration is tied to the persistent volume. Back it up.
