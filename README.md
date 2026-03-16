# Vaquill Integrations

MCP servers and integrations for [Vaquill AI](https://vaquill.com) — self-hosted legal research tools, chatbots, and platform connectors.

## MCP Servers

### courtlistener-mcp

US federal and state court opinions, dockets, PACER data, and eCFR federal regulations via the [CourtListener API v4](https://www.courtlistener.com/api/).

- **Language**: Python (FastMCP)
- **Transport**: `streamable_http` at `/mcp/` (default), `sse`, `stdio`
- **Docker**: `docker-compose up -d` (port 8000)
- **Upstream**: Forked from [Travis-Prall/court-listener-mcp](https://github.com/Travis-Prall/court-listener-mcp)
- **API key**: Free from [courtlistener.com/api](https://www.courtlistener.com/api/)

30+ tools: opinion search, docket search, citation lookup/verification, judge profiles, oral arguments, eCFR regulations.

### canlii-mcp

Canadian federal and provincial court decisions and legislation via the [CanLII API](https://www.canlii.org/en/api/).

- **Language**: TypeScript (MCP SDK + Hono)
- **Transport**: `streamable_http` at `/mcp` (stateless), `stdio`
- **Docker**: `docker run -e CANLII_API=key -p 3000:3000` (port 3000)
- **Upstream**: Forked from [tomilashy/canlii-mcp](https://github.com/tomilashy/canlii-mcp)
- **API key**: Apply at [canlii.org/en/api](https://www.canlii.org/en/api/)

7 tools: case databases, case listing, case metadata, citation graph, legislation databases, legislation listing, legislation metadata. Bilingual (en/fr).

**Rate limits (CanLII API):** 1 concurrent request, 2 req/sec, **5,000 req/day hard cap**. The server enforces these automatically — requests exceeding the daily limit return an error without hitting the upstream API. Metadata only (no full document text).

## Planned Integrations

- Slack bot
- Discord bot
- WordPress plugin
- WhatsApp chatbot

## License

Each integration retains its upstream license. See individual subdirectories.
