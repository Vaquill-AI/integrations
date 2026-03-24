# Vaquill Integrations

Chatbots, widgets, extensions, MCP servers, and platform connectors for [Vaquill AI](https://vaquill.ai) — the legal research API.

Each integration is **self-contained** — pick any one, deploy it independently.

## Quick Start

All chatbots and widgets use the [Vaquill API](https://www.vaquill.ai/docs/api-reference/). You need a Vaquill API key (`vq_key_...`) from [vaquill.ai/dashboard](https://www.vaquill.ai/dashboard).

```bash
git clone https://github.com/Vaquill-AI/integrations.git
cd integrations/<integration-name>
cp .env.example .env   # add your VAQUILL_API_KEY
# follow the integration's README for setup
```

## Chatbots

| Integration | Platform | Language | Deploy |
|-------------|----------|----------|--------|
| [**whatsapp-bot**](whatsapp-bot/) | WhatsApp (via Twilio) | Python (FastAPI) | Docker / Render |
| [**slack-bot**](slack-bot/) | Slack | Python (slack-bolt) | Docker / Heroku |
| [**discord-bot**](discord-bot/) | Discord | Python (discord.py) | Docker / Railway |
| [**telegram-bot**](telegram-bot/) | Telegram | Python (python-telegram-bot) | Docker / Render |
| [**ms-teams-bot**](ms-teams-bot/) | Microsoft Teams | Python (botbuilder) | Docker / Azure |

All chatbots share the same architecture:
- Vaquill API client (`vaquill_client.py`) for legal Q&A
- Per-user/channel conversation history (multi-turn)
- Rate limiting (Redis or in-memory)
- Structured source citations from case law
- Slash commands, feedback buttons, analytics

## Widgets

| Integration | Type | Language | Deploy |
|-------------|------|----------|--------|
| [**widget-next**](widget-next/) | Embeddable chat (Next.js) | TypeScript | Vercel |
| [**widget**](widget/) | Embeddable chat (Docker) | Python + HTML | Docker Compose |

Drop-in chat widgets for any website. Embed with a script tag or iframe.

## Browser Extension

| Integration | Platform | Language |
|-------------|----------|----------|
| [**chrome-extension**](chrome-extension/) | Chrome / Edge / Brave | JavaScript (Manifest V3) |

Chrome extension popup with legal AI chat. Calls the Vaquill API directly.

## Automation

| Integration | Platform | Format |
|-------------|----------|--------|
| [**n8n**](n8n/) | n8n / Make.com | Workflow JSON |

Pre-built workflow templates for batch legal research via spreadsheets.

## MCP Servers

Hosted MCP endpoints for AI tool integration:

| Server | Endpoint | Auth |
|--------|----------|------|
| **CourtListener** | `https://courtlistener-mcp.vaquill.ai/mcp/` | None required |
| **CanLII** | `https://canlii-mcp.vaquill.ai/mcp` | Bearer token required |

### Claude Desktop / Claude Code

```json
{
  "mcpServers": {
    "courtlistener": {
      "url": "https://courtlistener-mcp.vaquill.ai/mcp/"
    },
    "canlii": {
      "url": "https://canlii-mcp.vaquill.ai/mcp",
      "headers": { "Authorization": "Bearer YOUR_TOKEN" }
    }
  }
}
```

### courtlistener-mcp

US federal and state court opinions, dockets, PACER data, and eCFR federal regulations via the [CourtListener API v4](https://www.courtlistener.com/api/).

- **Language**: Python (FastMCP)
- **Transport**: `streamable_http` at `/mcp/` (default), `sse`, `stdio`
- **Docker**: `docker-compose up -d` (port 8000)
- **API key**: Free from [courtlistener.com/api](https://www.courtlistener.com/api/)

### canlii-mcp

Canadian federal and provincial court decisions and legislation via the [CanLII API](https://www.canlii.org/en/api/).

- **Language**: TypeScript (MCP SDK + Hono)
- **Transport**: `streamable_http` at `/mcp` (stateless), `stdio`
- **Docker**: `docker run -e CANLII_API=key -p 3000:3000` (port 3000)
- **API key**: Apply at [canlii.org/en/api](https://www.canlii.org/en/api/)

## Vaquill API

All integrations use the same simple API:

```bash
curl -X POST https://api.vaquill.ai/api/v1/ask \
  -H "Authorization: Bearer vq_key_..." \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Section 302 IPC?"}'
```

Response:
```json
{
  "data": {
    "answer": "Section 302 of the Indian Penal Code deals with...",
    "sources": [
      {
        "sourceIndex": 1,
        "caseName": "State of UP v. Ram Sagar Yadav",
        "citation": "(1985) 1 SCC 552",
        "court": "Supreme Court of India",
        "excerpt": "...",
        "relevanceScore": 0.94
      }
    ],
    "mode": "standard"
  },
  "meta": {
    "processingTimeMs": 2340.5,
    "creditsConsumed": 0.5,
    "creditsRemaining": 4.5
  }
}
```

See the [API Reference](https://www.vaquill.ai/docs/api-reference/) for full documentation.

## License

MIT. Each MCP server retains its upstream license — see individual subdirectories.
