# Vaquill Widget -- Next.js

An embeddable AI legal research chat widget built with Next.js 15, TypeScript, and Tailwind CSS. It proxies questions to the [Vaquill API](https://api.vaquill.ai) and renders structured legal sources with case names, citations, court details, excerpts, and PDF links.

---

## Overview

This widget provides a full-featured chat interface that can be deployed as a standalone page or embedded via an iframe on any website. It includes:

- Word-by-word streaming animation for responses
- Inline `[N]` citation links that anchor to the matching source card
- Structured legal sources panel: case name, citation, court, year, disposition, docket number, citation count, excerpt
- Per-source link priority: Vaquill-hosted statute URLs (`htmlUrl` / `statutePdfUrl` / `xmlUrl`) first, then govinfo.gov, then external court PDFs
- Standard vs Deep RAG mode toggle
- US-only: every request is pinned to `countryCode: "US"` server-side
- Dark / light theme via CSS custom properties
- Embeddable in iframes with CORS headers pre-configured
- Production-ready with standalone Next.js output and Vercel support

---

## Prerequisites

- Node.js 18+ ([download](https://nodejs.org/))
- A Vaquill API key (`vq_key_...`) from [app.vaquill.ai/settings/api](https://app.vaquill.ai/settings/api)

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

Only the API key lives in env (it's the only secret). Everything else
(agent name, mode, example questions, animation speed) is hardcoded in
[`src/config/constants.ts`](src/config/constants.ts) so embedders edit
one file and redeploy.

### `.env.local`

```bash
# Required: your Vaquill API key (starts with vq_key_)
VAQUILL_API_KEY=vq_key_your_key_here
```

### Customising in code

Open `src/config/constants.ts`:

```ts
export const VAQUILL_CONFIG = {
  apiBaseUrl: "https://api.vaquill.ai/api/v1",
  defaultMode: "standard" as "standard" | "deep",  // or "deep"
  countryCode: "US" as const,                       // US-only
};

export const UI_CONFIG = {
  agentName: "Vaquill Legal Assistant",
  wordAnimationDelayMs: 25,
  textareaMaxHeightPx: 200,
};

export const EXAMPLE_QUESTIONS = [
  "What is qualified immunity under 42 USC 1983?",
  // …
];
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
| `/api/chat` | POST | Proxy to Vaquill `/ask` (non-streaming, US-pinned) |
| `/api/chat/stream` | POST | Proxy to Vaquill `/ask/stream` (SSE, US-pinned) |

### POST `/api/chat`

**Request:**
```json
{
  "question": "What is qualified immunity under 42 USC 1983?",
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
  "answer": "Qualified immunity is a defense available to government officials [1][2]...",
  "sources": [
    {
      "sourceIndex": 1,
      "caseName": "Harlow v. Fitzgerald",
      "citation": "457 U.S. 800",
      "court": "Supreme Court of the United States",
      "year": 1982,
      "sourceType": "us_case",
      "excerpt": "Government officials performing discretionary functions generally are shielded from liability...",
      "pdfUrl": "https://...",
      "externalUrl": "https://...",
      "relevanceScore": 0.94
    }
  ],
  "questionInterpreted": "What is qualified immunity under § 1983?",
  "mode": "standard",
  "meta": { "processingTimeMs": 1240, "creditsConsumed": 5 }
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

Then set `VAQUILL_API_KEY` in the Vercel dashboard under **Project Settings > Environment Variables**.

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
        route.ts                 # POST /api/chat  ->  Vaquill /ask (US-pinned)
        stream/route.ts          # POST /api/chat/stream  ->  Vaquill /ask/stream (SSE, US-pinned)
  components/
    ChatWidget.tsx               # Main chat UI component
  config/
    constants.ts                 # All env-driven config
  lib/
    vaquill.ts                   # Server-side Vaquill API client
    markdown.ts                  # Citation linkifier + markdown post-processing
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

### Browser compatibility

| Browser | Support |
|---|---|
| Chrome / Edge | Full support (recommended) |
| Firefox | Full support |
| Safari / iOS | Full support |

---

## Legal Disclaimer

Vaquill provides legal information, not legal advice. Users should consult a qualified lawyer for advice on their specific circumstances.
