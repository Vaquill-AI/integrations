# Vaquill Widget — Next.js

An embeddable AI legal research chat widget built with Next.js 15, TypeScript, and Tailwind CSS.
It proxies questions to the [Vaquill API](https://api.vaquill.ai) and renders structured legal sources with case names, citations, court details, excerpts, and PDF links.

## Features

- Full chat interface with word-by-word streaming animation
- Structured legal sources panel (case name, citation, court, excerpt, PDF link)
- Standard vs Deep RAG mode toggle
- Optional TTS playback (OpenAI tts-1)
- Optional STT voice input (OpenAI Whisper)
- Dark / light theme via CSS custom properties
- Embeddable in iframes (CORS headers configured)
- Production-ready with standalone Next.js output and Vercel support

## Quick Start

```bash
cp .env.example .env.local
# Edit .env.local and set VAQUILL_API_KEY

npm install
npm run dev
# Open http://localhost:3000
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `VAQUILL_API_KEY` | Yes | — | Your Vaquill API key (`vq_key_...`) |
| `VAQUILL_API_URL` | No | `https://api.vaquill.ai/api/v1` | Override API base URL |
| `NEXT_PUBLIC_DEFAULT_MODE` | No | `standard` | Default RAG mode: `standard` or `deep` |
| `NEXT_PUBLIC_THEME` | No | `dark` | Widget theme: `dark` or `light` |
| `NEXT_PUBLIC_AGENT_NAME` | No | `Vaquill Legal Assistant` | Display name in the header |
| `OPENAI_API_KEY` | No | — | Enables TTS and STT features |
| `OPENAI_TTS_MODEL` | No | `tts-1` | OpenAI TTS model |
| `OPENAI_TTS_VOICE` | No | `nova` | OpenAI TTS voice |
| `STT_MODEL` | No | `gpt-4o-mini-transcribe` | OpenAI STT model |

## API Routes

| Route | Method | Description |
|---|---|---|
| `/api/chat` | POST | Proxy to Vaquill `/ask` (non-streaming) |
| `/api/chat/stream` | POST | Proxy to Vaquill `/ask/stream` (SSE) |
| `/api/chat/transcribe` | POST | Speech-to-text via OpenAI Whisper |
| `/api/agent/capabilities` | GET | Feature flags based on env config |
| `/api/tts/speak` | POST | Text-to-speech via OpenAI |

### POST `/api/chat`

```json
{
  "question": "What is Article 21?",
  "mode": "standard",
  "chatHistory": [
    { "role": "user", "content": "Previous question" },
    { "role": "assistant", "content": "Previous answer" }
  ]
}
```

Response:

```json
{
  "success": true,
  "answer": "Article 21 of the Indian Constitution...",
  "sources": [
    {
      "caseName": "Maneka Gandhi v. Union of India",
      "citation": "AIR 1978 SC 597",
      "court": "Supreme Court of India",
      "excerpt": "The right to life under Article 21...",
      "pdfUrl": "https://...",
      "relevanceScore": 0.92
    }
  ],
  "questionInterpreted": "Explain the right to life under Article 21",
  "mode": "standard",
  "meta": { "requestId": "...", "processingTimeMs": 1240 }
}
```

## Embedding

The widget can be embedded in any page via an `<iframe>`:

```html
<iframe
  src="https://your-widget.vercel.app"
  width="400"
  height="600"
  style="border: none; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.2);"
  title="Vaquill Legal Assistant"
></iframe>
```

## Deploy to Vercel

```bash
vercel --prod
```

Set `VAQUILL_API_KEY` in the Vercel dashboard under Project Settings > Environment Variables.

## Architecture

```
src/
  app/
    page.tsx                     # Root page — renders ChatWidget
    layout.tsx                   # HTML shell, theme setup
    globals.css                  # Global styles + Tailwind
    api/
      chat/
        route.ts                 # POST /api/chat  →  Vaquill /ask
        stream/route.ts          # POST /api/chat/stream  →  Vaquill /ask/stream (SSE)
        transcribe/route.ts      # POST /api/chat/transcribe  →  OpenAI Whisper
      agent/
        capabilities/route.ts    # GET /api/agent/capabilities
      tts/
        speak/route.ts           # POST /api/tts/speak  →  OpenAI TTS
  components/
    ChatWidget.tsx               # Main chat UI component
  config/
    constants.ts                 # All env-driven config
  hooks/
    useCapabilities.ts           # Fetches feature flags from /api/agent/capabilities
    useTTS.ts                    # TTS playback hook
  lib/
    vaquill.ts                   # Server-side Vaquill API client
    markdown.ts                  # Markdown post-processing utilities
  styles/
    design-tokens.css            # CSS custom properties (dark + light themes)
```
