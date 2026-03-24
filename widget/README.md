# Vaquill Chat Widget

An embeddable legal AI chat widget powered by the Vaquill API. Deploy with Docker Compose and embed on any website via a single script tag or an inline iframe.

---

## Overview

The Vaquill Chat Widget is a self-contained frontend + backend application that:

- Provides a chat interface for legal research questions
- Proxies requests to the Vaquill API and renders structured answers with case citations, court details, excerpts, and PDF links
- Supports two embed modes: floating chatbot (Intercom-style) and inline embed
- Runs in Docker for easy deployment on any server

---

## Prerequisites

**For Docker deployment:**
- Docker 20.10+ and Docker Compose ([download](https://www.docker.com/get-started))
- A Vaquill API key (`vq_key_...`) from [app.vaquill.ai/settings/api](https://app.vaquill.ai/settings/api)

**For local development:**
- Python 3.10+
- Node.js 18+
- Yarn (`npm install -g yarn`)
- A Vaquill API key

---

## Setup / Installation

### Quick Start (Docker)

```bash
# 1. Copy and fill in the environment file
cp .env.example .env
# Edit .env and set VAQUILL_API_KEY=vq_key_...

# 2. Start the widget
docker-compose up -d

# 3. Open the widget in your browser
open http://localhost:8000
```

### Local Development

**Backend (Python 3.10+):**

```bash
cd backend
pip install -r requirements.txt
VAQUILL_API_KEY=vq_key_... uvicorn main:app --reload --port 8000
```

Backend available at `http://localhost:8000`.

**Frontend (Node 18+):**

```bash
cd frontend
yarn install
yarn dev     # proxies /api to http://localhost:8000
```

Frontend available at `http://localhost:5173`.

**Development commands:**

| Command | Description |
|---|---|
| `uvicorn main:app --reload` | Backend with hot reload |
| `yarn dev` | Frontend dev server with hot reload |
| `yarn build` | Production frontend build |
| `yarn lint` | Run ESLint |
| `yarn preview` | Preview production build |

---

## Configuration

All configuration is via environment variables (`.env` file):

| Variable | Required | Default | Description |
|---|---|---|---|
| `VAQUILL_API_KEY` | Yes | -- | Your Vaquill API key (`vq_key_...`) |
| `VAQUILL_API_URL` | No | `https://api.vaquill.ai/api/v1` | Vaquill API base URL |
| `WIDGET_MODE` | No | `standard` | Default RAG mode: `standard` or `deep` |
| `WIDGET_TITLE` | No | `Vaquill Legal AI` | Title shown in the chat header |
| `HOST_PORT` | No | `8000` | Host port the container is exposed on |
| `ALLOWED_ORIGINS` | No | `*` | CORS origins (comma-separated or `*`) |

### Example `.env`

```bash
VAQUILL_API_KEY=vq_key_your_key_here
VAQUILL_API_URL=https://api.vaquill.ai/api/v1
WIDGET_MODE=standard
WIDGET_TITLE=Vaquill Legal AI
HOST_PORT=8000
ALLOWED_ORIGINS=*
```

---

## Deployment

### Docker Compose (Recommended)

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f
```

### Production with Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### SSL with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com

# Verify auto-renewal
sudo certbot renew --dry-run
```

### CORS Configuration

By default, `ALLOWED_ORIGINS=*` allows requests from any domain. For production, restrict to your website's domain:

```bash
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

---

## Embedding on Your Website

### Option 1 -- Floating Chatbot (Intercom style)

Add one script tag before `</body>`:

```html
<script
  src="https://your-widget-host/embed/script-floating-chatbot.js"
  data-api-url="https://your-widget-host"
  data-primary-color="#1a56db"
></script>
```

A floating button appears in the bottom-right corner. Clicking it opens a slide-in chat panel.

**Script attributes:**

| Attribute | Default | Description |
|---|---|---|
| `data-api-url` | `http://localhost:8000` | Widget backend URL |
| `data-primary-color` | `#1a56db` | Brand accent colour |
| `data-button-size` | `60px` | Floating button diameter |
| `data-chat-width` | `400px` | Panel width on desktop |
| `data-chat-height` | `600px` | Panel height |

### Option 2 -- Inline Embed

```html
<!-- Place this div where you want the chat -->
<div id="vaquill-widget-embed"></div>

<!-- Then include the script -->
<script
  src="https://your-widget-host/embed/script-inline-embed.js"
  data-api-url="https://your-widget-host"
  data-height="640px"
></script>
```

### Platform-Specific Instructions

**WordPress:**
1. Install the "Insert Headers and Footers" plugin
2. Paste the script tag in the footer section
3. Save and clear cache

**Shopify:**
1. Go to Online Store > Themes > Edit Code
2. Open `theme.liquid`
3. Add the script tag before `</body>`
4. Save

**Wix:**
1. Add a "Custom Code" element
2. Paste the script tag
3. Position the element on your page

**Next.js / React:**

```jsx
import { useEffect } from 'react';

export default function MyApp() {
  useEffect(() => {
    const script = document.createElement('script');
    script.src = `${process.env.NEXT_PUBLIC_WIDGET_URL}/embed/script-floating-chatbot.js`;
    script.setAttribute('data-api-url', process.env.NEXT_PUBLIC_WIDGET_URL);
    script.defer = true;
    document.body.appendChild(script);

    return () => document.body.removeChild(script);
  }, []);

  return <YourApp />;
}
```

### Working Examples

See the [`examples/`](examples/) directory for complete integration examples:

- **[Floating Widget Example](examples/test-pages/test-floating-chatbot.html)** -- floating chatbot interface
- **[Inline Embed Example](examples/test-pages/test-inline-embed.html)** -- inline page embedding

---

## API

The backend exposes the following HTTP endpoints:

### `POST /api/chat`

Send a message and receive an answer with legal sources.

**Request body:**
```json
{
  "message": "What is Section 302 of the IPC?",
  "chatHistory": [
    { "role": "user", "content": "Tell me about IPC." },
    { "role": "assistant", "content": "The Indian Penal Code..." }
  ],
  "mode": "standard"
}
```

**Response:**
```json
{
  "answer": "Section 302 of the IPC prescribes...",
  "sources": [
    {
      "caseName": "State of Maharashtra v. Prakash",
      "citation": "2023 SCC 412",
      "court": "Supreme Court of India",
      "excerpt": "...relevant excerpt...",
      "pdfUrl": "https://...",
      "relevanceScore": 0.94
    }
  ],
  "questionInterpreted": "What is the punishment for murder under IPC?",
  "mode": "standard",
  "processingTimeMs": 1240
}
```

### `GET /api/widget/info`

Returns widget display configuration (title, branding, suggested questions).

### `GET /health`

Returns `{"status": "ok"}` -- used by Docker health checks.

---

## Project Structure

```
widget/
  docker-compose.yml
  .env.example
  backend/
    Dockerfile
    requirements.txt
    main.py                # FastAPI app, static serving
    vaquill_client.py      # Async Vaquill API client
    markdown_processor.py  # LLM markdown fixups
    routes/
      chat.py              # POST /api/chat
  frontend/
    index.html
    package.json
    vite.config.ts
    src/
      App.tsx
      main.tsx
      index.css
      components/
        ChatContainer.tsx
        ChatContainer.css
      hooks/
        useWidgetInfo.ts
      types/
        index.ts
      utils/
        api.ts
        markdownPreprocessor.ts
  examples/
    embed-scripts/
      script-floating-chatbot.js
      script-inline-embed.js
    test-pages/
      test-floating-chatbot.html
      test-inline-embed.html
```

---

## Troubleshooting

### Widget not loading

- **Cause**: Container is not running or port is misconfigured.
- **Fix**: Run `docker-compose ps` to verify the container is up. Check `HOST_PORT` in `.env` matches the port you are visiting.

### "Failed to fetch" or CORS errors

- **Cause**: The `data-api-url` in the embed script does not match the widget backend URL, or `ALLOWED_ORIGINS` is too restrictive.
- **Fix**: Ensure `data-api-url` points to your deployed widget backend. For testing, set `ALLOWED_ORIGINS=*`.

### No sources in responses

- **Cause**: The query did not match any indexed legal documents, or the API key is invalid.
- **Fix**: Try a more specific legal query. Verify the API key at [app.vaquill.ai/settings/api](https://app.vaquill.ai/settings/api).

### Docker build fails

- **Cause**: Platform mismatch or insufficient disk space.
- **Fix**: On ARM64 Macs, ensure Docker Desktop supports ARM. Check disk space with `df -h`.

### Health check failing

- **Cause**: Backend cannot reach the Vaquill API.
- **Fix**: Test connectivity: `curl https://api.vaquill.ai/api/v1/health`. Verify `VAQUILL_API_KEY` and `VAQUILL_API_URL` in `.env`.

---

## Legal Disclaimer

Vaquill provides legal information, not legal advice. Users should consult a qualified lawyer for advice on their specific circumstances.
