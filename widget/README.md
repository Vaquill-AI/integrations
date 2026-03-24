# Vaquill Chat Widget

An embeddable legal AI chat widget powered by the Vaquill API. Deploy it with
Docker Compose and embed it on any website via a single script tag or an inline
iframe embed.

---

## Quick start

```bash
# 1. Copy and fill in the environment file
cp .env.example .env
# Edit .env and set VAQUILL_API_KEY=vq_key_...

# 2. Start the widget
docker-compose up -d

# 3. Open the widget in your browser
open http://localhost:8000
```

---

## Configuration

All configuration is via environment variables (`.env` file):

| Variable | Default | Description |
|---|---|---|
| `VAQUILL_API_KEY` | — | **Required.** Your Vaquill API key (`vq_key_...`) |
| `VAQUILL_API_URL` | `https://api.vaquill.ai/api/v1` | Vaquill API base URL |
| `WIDGET_MODE` | `standard` | Default RAG mode: `standard` or `deep` |
| `WIDGET_TITLE` | `Vaquill Legal AI` | Title shown in the chat header |
| `HOST_PORT` | `8000` | Host port the container is exposed on |
| `ALLOWED_ORIGINS` | `*` | CORS origins (comma-separated or `*`) |

---

## Embedding on your website

### Option 1 — Floating chatbot (Intercom style)

Add one script tag before `</body>`:

```html
<script
  src="https://your-widget-host/embed/script-floating-chatbot.js"
  data-api-url="https://your-widget-host"
  data-primary-color="#1a56db"
></script>
```

A floating button appears in the bottom-right corner. Clicking it opens a
slide-in chat panel.

**Script attributes:**

| Attribute | Default | Description |
|---|---|---|
| `data-api-url` | `http://localhost:8000` | Widget backend URL |
| `data-primary-color` | `#1a56db` | Brand accent colour |
| `data-button-size` | `60px` | Floating button diameter |
| `data-chat-width` | `400px` | Panel width on desktop |
| `data-chat-height` | `600px` | Panel height |

### Option 2 — Inline embed

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

Returns `{"status": "ok"}` — used by Docker health checks.

---

## Development

```bash
# Backend (Python 3.10+)
cd backend
pip install -r requirements.txt
VAQUILL_API_KEY=vq_key_... uvicorn main:app --reload --port 8000

# Frontend (Node 18+)
cd frontend
yarn install
yarn dev     # proxies /api to http://localhost:8000
```

---

## Project structure

```
widget/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                # FastAPI app, static serving
│   ├── vaquill_client.py      # Async Vaquill API client
│   ├── markdown_processor.py  # LLM markdown fixups
│   └── routes/
│       └── chat.py            # POST /api/chat
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── index.css
│       ├── components/
│       │   ├── ChatContainer.tsx
│       │   └── ChatContainer.css
│       ├── hooks/
│       │   └── useWidgetInfo.ts
│       ├── types/
│       │   └── index.ts
│       └── utils/
│           ├── api.ts
│           └── markdownPreprocessor.ts
└── examples/
    ├── embed-scripts/
    │   ├── script-floating-chatbot.js
    │   └── script-inline-embed.js
    └── test-pages/
        ├── test-floating-chatbot.html
        └── test-inline-embed.html
```

---

## Legal disclaimer

Vaquill provides legal information, not legal advice. Users should consult a
qualified lawyer for advice on their specific circumstances.
