# Vaquill Integrations

Chatbots, widgets, extensions, MCP servers, and platform connectors for [Vaquill AI](https://vaquill.ai) — the legal research API.

Each integration is **self-contained** — pick any one, deploy it independently.

[![Discord](https://img.shields.io/badge/Discord-Join%20the%20community-5865F2?logo=discord&logoColor=white)](https://discord.gg/GQtnwxf8nQ)

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

Both MCP servers now live in their own dedicated repositories. Each is public and ships with bring-your-own-key (BYOK) auth so you can use Vaquill's hosted endpoint with your own API key (we never see or store it). No Vaquill token is required.

| Server | Repo | Hosted endpoint |
|--------|------|-----------------|
| **CourtListener** (US) | [Vaquill-AI/courtlistener-mcp](https://github.com/Vaquill-AI/courtlistener-mcp) | `https://courtlistener-mcp.vaquill.ai/mcp/` |
| **CanLII** (Canada) | [Vaquill-AI/canlii-mcp](https://github.com/Vaquill-AI/canlii-mcp) | `https://canlii-mcp.vaquill.ai/mcp` |

**Connecting.** Clients that support custom headers (Cursor, VS Code, Claude Code) pass your key as a request header. For header-less clients such as the **Claude Desktop connector UI** and **claude.ai web**, the CanLII endpoint also accepts your key directly in the URL:

```
https://canlii-mcp.vaquill.ai/mcp?token=YOUR_CANLII_API_KEY
```

CanLII rate limits are enforced per key (2 requests/second, 1 concurrent, 5,000/day). See each repo's README for full client setup (Claude Desktop, Cursor, VS Code, Windsurf) and self-hosting instructions.

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

## Community

Questions, ideas, or want to contribute? Join the Vaquill community on [Discord](https://discord.gg/GQtnwxf8nQ).
