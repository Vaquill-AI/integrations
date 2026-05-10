# Vaquill Widget Pro

A feature-rich Next.js chat widget for Vaquill — multi-thread conversation
history, voice mode (TTS + STT), gamification, citation viewers, and a
floating-or-inline embed surface. Built with TypeScript, React 19, and
Vercel-ready serverless API routes.

For a leaner build (~10 components, US-legal focus, streaming SSE,
inline citation tooltips, persistence, single-file embed loader), see
the sibling [`widget-next/`](../widget-next).

This pro version is the right fit when you need:

- A persistent **conversation sidebar** with rename / delete / search
- **Voice mode** (mic input via VAD, TTS playback)
- **Cross-tab sync** via BroadcastChannel
- **Gamification** progress + engagement features
- Multiple citation display modes (cards / tabs / accordion / pills)
- Configurable **TTS provider** matrix (OpenAI / ElevenLabs / Edge /
  Google / StreamElements)

## Status

This codebase started as a fork of an open-source RAG-widget project
and has been rebranded to Vaquill. The chat-completion plumbing in
`src/lib/ai/vaquill-client.ts` now talks to the real Vaquill API
(`https://api.vaquill.ai/api/v1/ask` and `/ask/stream`) — both
streaming and non-streaming paths are wired and have been smoke-tested
end-to-end. Multi-turn `chatHistory` is preserved server-side via a
process-local session map so follow-up turns reference earlier
context.

What still uses the legacy RAG-API surface (and is stubbed in the
client to avoid runtime errors): per-message feedback persistence,
citation-by-id lookup, file uploads, and the agent-settings /
agent-details endpoints. The UI consumes them but they degrade
gracefully — feedback is recorded only in the local session cache,
agent settings return Vaquill-flavoured defaults, and `uploadFile`
throws a clear "not supported" error.

Caveats to read before shipping:

- The session map lives in process memory. On Vercel cold starts or
  multi-instance deployments it resets — the React UI's IndexedDB /
  localStorage is the durable copy, so users won't lose history,
  but server-side `getConversationMessages` will return empty for a
  cold instance until at least one turn is sent.
- `VAQUILL_PROJECT_ID` is no longer required (left in `.env.example`
  for back-compat with the legacy schema); only `VAQUILL_API_KEY`
  matters.
- The `AgentCapability` enum (`fastest-responses` / `optimal-choice`
  / `advanced-reasoning` / `complex-tasks`) maps onto Vaquill's
  `mode` (`standard` for the first two, `deep` for the latter two).

## Quick Start

```bash
npm install
cp .env.example .env.local       # add your keys
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Prerequisites

- Node.js 18+
- A Vaquill API key (`vq_key_…`) from
  [app.vaquill.ai/developer](https://app.vaquill.ai/developer)
- Optional: an OpenAI API key if you want voice mode (TTS / STT)

## Environment Variables

The full list lives in [`.env.example`](.env.example). The minimum set:

```bash
# Required — Vaquill chat backend
VAQUILL_API_KEY=vq_key_...
VAQUILL_PROJECT_ID=your_project_id   # legacy field; ignore if not used
USE_VAQUILL=true
VAQUILL_STREAM=true

# Optional — voice (set both to enable mic + TTS)
OPENAI_API_KEY=sk-...
TTS_PROVIDER=OPENAI                  # OPENAI | ELEVENLABS | EDGE | GOOGLE | STREAMELEMENTS

# UI knobs (browser-readable)
NEXT_PUBLIC_THEME=light
NEXT_PUBLIC_WIDGET_FLOATING_BUTTON=true
NEXT_PUBLIC_WIDGET_FLOATING_POSITION=bottom-right
NEXT_PUBLIC_CITATION_DISPLAY_MODE=cards   # cards | tabs | accordion | pills | all
```

## Development Commands

```bash
npm run dev      # dev server on :3000
npm run build    # production build
npm run start    # run the built bundle
npm run lint     # eslint
```

## Architecture

```text
src/
├── app/                    # Next.js App Router
│   ├── page.tsx           # main entry
│   ├── layout.tsx         # root layout + theme provider
│   └── api/               # serverless routes
│       ├── chat/          # chat / messages / conversations / citations
│       ├── tts/           # text-to-speech
│       └── agent/         # agent settings + capabilities
├── components/
│   ├── ChatContainer.tsx  # main chat surface
│   ├── ChatHistory/       # multi-thread sidebar
│   └── gamification/      # XP / streaks / progress
├── hooks/                 # voice, persistence, sync, search hooks
├── lib/
│   ├── ai/                # Vaquill client + completion plumbing
│   ├── audio/             # TTS provider implementations + VAD wrapper
│   └── storage/           # IndexedDB + localStorage fallback
├── config/                # centralised config + env parsing
└── styles/                # CSS design tokens
```

## Deployment

### Vercel (recommended)

```bash
npm i -g vercel
vercel
# then set env vars in the Vercel dashboard
```

### Railway

```bash
npm i -g @railway/cli
railway login
railway up
railway variables set VAQUILL_API_KEY=vq_key_...
```

## Embedding

```html
<script>
  window.vaquillConfig = {
    serverUrl: 'https://your-deployment.vercel.app',
    position: 'bottom-right',
    theme: 'light'
  };
</script>
<script src="https://your-deployment.vercel.app/widget.js" defer></script>
```

See [`examples/`](examples/) for WordPress, Shopify, React, and plain
HTML drop-in examples.

## TTS Providers

| Provider       | Quality   | Speed  | Cost |
| -------------- | --------- | ------ | ---- |
| OpenAI         | High      | Fast   | Paid |
| ElevenLabs     | Very High | Medium | Paid |
| Edge TTS       | Good      | Fast   | Free |
| Google TTS     | Medium    | Fast   | Free |
| StreamElements | Medium    | Fast   | Free |

Switch with `TTS_PROVIDER=…` in `.env.local`.

## Troubleshooting

**Voice not working** — ensure HTTPS in production (mic access
requires it), grant browser mic permission, and verify
`OPENAI_API_KEY` is set.

**Chat returns nothing** — verify `VAQUILL_API_KEY` and
`USE_VAQUILL=true`. Inspect `Network` tab for the request to
`/api/inference` or `/api/inference-stream`.

**Build errors** —

```bash
rm -rf node_modules .next package-lock.json
npm install
npm run build
```

## Browser Support

- Chrome / Edge — full
- Firefox — full
- Safari / iOS — MP4 audio fallback (WebM unsupported); mic requires
  HTTPS

## License

MIT.
