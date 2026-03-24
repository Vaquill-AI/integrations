# Vaquill Widget -- Next.js

An embeddable AI legal research chat widget built with Next.js 15, TypeScript, and Tailwind CSS. It proxies questions to the [Vaquill API](https://api.vaquill.ai) and renders structured legal sources with case names, citations, court details, excerpts, and PDF links.

---

## Overview

This widget provides a full-featured chat interface that can be deployed as a standalone page or embedded via an iframe on any website. It includes:

- Word-by-word streaming animation for responses
- Structured legal sources panel (case name, citation, court, excerpt, PDF link)
- Standard vs Deep RAG mode toggle
- Optional TTS playback (OpenAI tts-1)
- Optional STT voice input (OpenAI Whisper)
- Dark / light theme via CSS custom properties
- Embeddable in iframes with CORS headers pre-configured
- Production-ready with standalone Next.js output and Vercel support

---

## Prerequisites

- Node.js 18+ ([download](https://nodejs.org/))
- A Vaquill API key (`vq_key_...`) from [app.vaquill.ai/settings/api](https://app.vaquill.ai/settings/api)
- (Optional) OpenAI API key for TTS and STT features

---

## Setup / Installation

### Step 1: Install dependencies

```bash
npm install
```

### Step 2: Configure environment variables

```bash
cp .env.example .env.local
```

Edit `.env.local` and set your API keys (see the Configuration section below for all options).

### Step 3: Run the development server

```bash
npm run dev
```

### Step 4: Open your browser

Navigate to [http://localhost:3000](http://localhost:3000) to see the widget.

---

## Configuration

Create a `.env.local` file with the following variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `VAQUILL_API_KEY` | Yes | -- | Your Vaquill API key (`vq_key_...`) |
| `VAQUILL_API_URL` | No | `https://api.vaquill.ai/api/v1` | Override the API base URL |
| `NEXT_PUBLIC_DEFAULT_MODE` | No | `standard` | Default RAG mode: `standard` or `deep` |
| `NEXT_PUBLIC_THEME` | No | `dark` | Widget theme: `dark` or `light` |
| `NEXT_PUBLIC_AGENT_NAME` | No | `Vaquill Legal Assistant` | Display name shown in the chat header |
| `OPENAI_API_KEY` | No | -- | Enables TTS and STT features |
| `OPENAI_TTS_MODEL` | No | `tts-1` | OpenAI TTS model (`tts-1` or `tts-1-hd`) |
| `OPENAI_TTS_VOICE` | No | `nova` | OpenAI TTS voice: alloy, echo, fable, onyx, nova, shimmer |
| `STT_MODEL` | No | `gpt-4o-mini-transcribe` | OpenAI speech-to-text model |

### Example `.env.local`

```bash
# Required
VAQUILL_API_KEY=vq_key_your_key_here

# Optional -- TTS and STT
OPENAI_API_KEY=sk-your-key-here

# Optional -- UI
NEXT_PUBLIC_DEFAULT_MODE=standard
NEXT_PUBLIC_THEME=dark
NEXT_PUBLIC_AGENT_NAME=Vaquill Legal Assistant
```

---

## Development Commands

```bash
# Development server with hot reload
npm run dev

# Production build
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

---

## API Routes

The Next.js app exposes the following serverless API routes:

| Route | Method | Description |
|---|---|---|
| `/api/chat` | POST | Proxy to Vaquill `/ask` (non-streaming) |
| `/api/chat/stream` | POST | Proxy to Vaquill `/ask/stream` (SSE) |
| `/api/chat/transcribe` | POST | Speech-to-text via OpenAI Whisper |
| `/api/agent/capabilities` | GET | Feature flags based on env config |
| `/api/tts/speak` | POST | Text-to-speech via OpenAI |

### POST `/api/chat`

**Request:**
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

**Response:**
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

---

## Deployment

### Deploy to Vercel (Recommended)

**Option 1: Vercel CLI**

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

Then set `VAQUILL_API_KEY` (and optionally `OPENAI_API_KEY`) in the Vercel dashboard under **Project Settings > Environment Variables**.

**Option 2: GitHub Integration**

1. Push code to GitHub
2. Import the project in the Vercel dashboard
3. Configure environment variables
4. Deploys automatically on every git push

**Option 3: Deploy to Railway**

```bash
npm i -g @railway/cli
railway login
railway up

# Set environment variables
railway variables set VAQUILL_API_KEY=vq_key_...
```

### Production Environment Variables

Set these in your deployment platform:

```
VAQUILL_API_KEY=vq_key_your_key_here
OPENAI_API_KEY=sk-your-key-here     # optional, for TTS/STT
NEXT_PUBLIC_DEFAULT_MODE=standard
NEXT_PUBLIC_THEME=dark
```

---

## Embedding on Your Website

The widget can be embedded on any page via an `<iframe>`:

```html
<iframe
  src="https://your-widget.vercel.app"
  width="400"
  height="600"
  style="border: none; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.2);"
  title="Vaquill Legal Assistant"
></iframe>
```

Replace `your-widget.vercel.app` with your actual deployment URL.

### Embedding in frameworks

**Next.js / React:**

```jsx
export default function LegalWidget() {
  return (
    <iframe
      src={process.env.NEXT_PUBLIC_WIDGET_URL}
      width="400"
      height="600"
      style={{ border: 'none', borderRadius: '12px' }}
      title="Vaquill Legal Assistant"
    />
  );
}
```

**WordPress:**
1. Install the "Insert Headers and Footers" plugin
2. Add the `<iframe>` snippet in the desired page or widget area
3. Save and clear cache

**Shopify:**
1. Go to Online Store > Themes > Edit Code
2. Open the relevant template (e.g., `page.liquid`)
3. Add the `<iframe>` snippet where you want it to appear
4. Save

---

## Architecture

```
src/
  app/
    page.tsx                     # Root page -- renders ChatWidget
    layout.tsx                   # HTML shell, theme setup
    globals.css                  # Global styles + Tailwind
    api/
      chat/
        route.ts                 # POST /api/chat  ->  Vaquill /ask
        stream/route.ts          # POST /api/chat/stream  ->  Vaquill /ask/stream (SSE)
        transcribe/route.ts      # POST /api/chat/transcribe  ->  OpenAI Whisper
      agent/
        capabilities/route.ts    # GET /api/agent/capabilities
      tts/
        speak/route.ts           # POST /api/tts/speak  ->  OpenAI TTS
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

---

## Troubleshooting

### Build issues

**"Module not found" errors:**
```bash
rm -rf node_modules package-lock.json
npm install
```

**TypeScript errors:**
```bash
npm run build
# Fix reported errors, then rebuild
```

### Runtime issues

**No response from chat:**
- Verify `VAQUILL_API_KEY` is set in `.env.local` (or in your deployment platform).
- Check the browser console and server logs for error details.
- Test the API key directly: `curl -H "Authorization: Bearer vq_key_..." https://api.vaquill.ai/api/v1/health`

**TTS not playing:**
- Verify `OPENAI_API_KEY` is configured.
- Check the browser console for errors.
- Ensure the `/api/agent/capabilities` endpoint returns `ttsEnabled: true`.

**STT / microphone not working:**
- The page must be served over HTTPS (required for microphone access).
- Grant microphone permissions when prompted by the browser.
- Check that `OPENAI_API_KEY` is set (STT depends on it).

### Browser compatibility

| Browser | Support |
|---|---|
| Chrome / Edge | Full support (recommended) |
| Firefox | Full support |
| Safari / iOS | WebM not supported; automatic fallback to MP4. Microphone requires HTTPS. |

---

## Legal Disclaimer

Vaquill provides legal information, not legal advice. Users should consult a qualified lawyer for advice on their specific circumstances.
