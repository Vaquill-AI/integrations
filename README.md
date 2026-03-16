# Vaquill Integrations

MCP servers and integrations for [Vaquill AI](https://vaquill.ai) — self-hosted legal research tools, chatbots, and platform connectors.

## Hosted MCP Endpoints

These servers are hosted by Vaquill and available for anyone to connect:

| Server | Endpoint | Auth |
|--------|----------|------|
| **CourtListener** | `https://courtlistener-mcp.vaquill.ai/mcp/` | None required |
| **CanLII** | `https://canlii-mcp.vaquill.ai/mcp` | Bearer token required |

## Connect to Your AI Tools

### Claude Desktop / Claude Code

Add to `~/.claude.json` or your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "courtlistener": {
      "url": "https://courtlistener-mcp.vaquill.ai/mcp/"
    },
    "canlii": {
      "url": "https://canlii-mcp.vaquill.ai/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

### Cursor

Go to **Settings > MCP** and add:

**CourtListener:**
- Type: `streamableHttp`
- URL: `https://courtlistener-mcp.vaquill.ai/mcp/`

**CanLII:**
- Type: `streamableHttp`
- URL: `https://canlii-mcp.vaquill.ai/mcp`
- Headers: `Authorization: Bearer YOUR_TOKEN`

### Windsurf

Add to your MCP config:

```json
{
  "mcpServers": {
    "courtlistener": {
      "serverUrl": "https://courtlistener-mcp.vaquill.ai/mcp/"
    },
    "canlii": {
      "serverUrl": "https://canlii-mcp.vaquill.ai/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

### ChatGPT (via MCP Bridge)

ChatGPT doesn't natively support MCP yet. Use an MCP-to-OpenAI bridge like [mcp-openai-bridge](https://github.com/nicobailon/mcp-openai-bridge):

```bash
pip install mcp-openai-bridge
mcp-bridge --mcp-url https://courtlistener-mcp.vaquill.ai/mcp/ --port 8080
```

### Self-Hosting

If you prefer to run your own instance:

```bash
git clone https://github.com/Vaquill-AI/integrations.git
cd integrations

# CourtListener
cd courtlistener-mcp
cp .env.example .env  # add your COURT_LISTENER_API_KEY
docker-compose up -d  # runs on port 8000

# CanLII
cd ../canlii-mcp
cp .env.example .env  # add your CANLII_API key
docker build -t canlii-mcp . && docker run -p 3000:3000 --env-file .env canlii-mcp
```

## MCP Servers

### courtlistener-mcp

US federal and state court opinions, dockets, PACER data, and eCFR federal regulations via the [CourtListener API v4](https://www.courtlistener.com/api/).

- **Language**: Python (FastMCP)
- **Transport**: `streamable_http` at `/mcp/` (default), `sse`, `stdio`
- **Docker**: `docker-compose up -d` (port 8000)
- **Upstream**: Forked from [Travis-Prall/court-listener-mcp](https://github.com/Travis-Prall/court-listener-mcp)
- **API key**: Free from [courtlistener.com/api](https://www.courtlistener.com/api/)

**19 tools:**

| Category | Tools |
|----------|-------|
| Search | `search_opinions`, `search_dockets`, `search_dockets_with_documents`, `search_recap_documents`, `search_audio`, `search_people` |
| Get by ID | `get_opinion`, `get_docket`, `get_audio`, `get_cluster`, `get_person`, `get_court` |
| Citations | `citation_lookup_citation`, `citation_batch_lookup_citations`, `citation_verify_citation_format`, `citation_parse_citation_with_citeurl`, `citation_extract_citations_from_text`, `citation_enhanced_citation_lookup` |
| System | `status` |

### canlii-mcp

Canadian federal and provincial court decisions and legislation via the [CanLII API](https://www.canlii.org/en/api/).

- **Language**: TypeScript (MCP SDK + Hono)
- **Transport**: `streamable_http` at `/mcp` (stateless), `stdio`
- **Docker**: `docker run -e CANLII_API=key -p 3000:3000` (port 3000)
- **Upstream**: Forked from [tomilashy/canlii-mcp](https://github.com/tomilashy/canlii-mcp)
- **API key**: Apply at [canlii.org/en/api](https://www.canlii.org/en/api/)

**7 tools:**

| Tool | Description |
|------|-------------|
| `list_case_databases` | List all courts and tribunals |
| `list_cases` | Browse decisions from a specific court |
| `get_case` | Case metadata (title, citation, date, keywords) |
| `get_case_citations` | Citation graph — cited cases, citing cases, cited legislation |
| `list_legislation_databases` | List all statute/regulation databases |
| `list_legislation` | Browse statutes from a specific database |
| `get_legislation` | Legislation metadata |

Bilingual (English/French). **Rate limits (CanLII API):** 1 concurrent request, 2 req/sec, **5,000 req/day hard cap**. Metadata only (no full document text).

## Planned Integrations

- Slack bot
- Discord bot
- WordPress plugin
- WhatsApp chatbot

## License

Each integration retains its upstream license. See individual subdirectories.
