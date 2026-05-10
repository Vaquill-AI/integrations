/**
 * Vaquill Widget — Configuration
 *
 * Only `VAQUILL_API_KEY` is read from the environment (it's the one
 * sensitive value). Everything else is hardcoded so embedders can ship
 * the widget without juggling env vars.
 *
 * To customise UI copy, mode, or animation: edit the values below and
 * redeploy. Don't add new env vars unless they're actually secrets.
 */

// ============================================
// Vaquill API (server-side only)
// ============================================

/**
 * Server-side env-driven knobs. Browser never reads these — the proxy
 * routes enforce them on the upstream call, ignoring whatever the
 * client sends.
 */
function resolveMode(): "standard" | "deep" {
  return process.env.VAQUILL_MODE === "deep" ? "deep" : "standard";
}

function resolveCountry(): "US" | "IN" {
  return process.env.VAQUILL_COUNTRY_CODE === "IN" ? "IN" : "US";
}

function resolveMaxSources(): number {
  // Upstream API allows 1-30, default 5. We clamp here so a typo in
  // .env can't push the request out of range.
  const raw = Number(process.env.VAQUILL_MAX_SOURCES);
  if (!Number.isFinite(raw)) return 5;
  return Math.max(1, Math.min(30, Math.floor(raw)));
}

/**
 * `inline` (default): visiting `/` renders the chat directly. Customers
 * iframe `/` to embed the chat as a full-page panel.
 *
 * `floating`: visiting `/` renders a tiny landing page that auto-loads
 * `embed.js` so the widget appears as a floating bubble. Customers paste
 * the `<script>` tag on their own site to get the same behavior.
 *
 * The `?embed=1` query param (set by `embed.js` on the iframe it loads)
 * always renders the chat — independent of this setting — to avoid
 * infinite recursion when floating mode is active.
 */
function resolveEmbedMode(): "inline" | "floating" {
  return process.env.VAQUILL_EMBED_MODE === "floating" ? "floating" : "inline";
}

export const VAQUILL_CONFIG = {
  /** Server-side API key — NEVER expose to the browser. */
  apiKey: process.env.VAQUILL_API_KEY ?? "",
  /** Vaquill API base URL. Hosted endpoint, not customer-specific. */
  apiBaseUrl: "https://api.vaquill.ai/api/v1",
  /** Mode. Set `VAQUILL_MODE=deep` in `.env` to switch. */
  mode: resolveMode(),
  /** Jurisdiction. Set `VAQUILL_COUNTRY_CODE=IN` to switch (default US). */
  countryCode: resolveCountry(),
  /** Source citations per answer (1–30). Set `VAQUILL_MAX_SOURCES` in `.env`. */
  maxSources: resolveMaxSources(),
  /** `inline` | `floating`. Set `VAQUILL_EMBED_MODE` in `.env`. */
  embedMode: resolveEmbedMode(),
} as const;

// ============================================
// Widget UI
// ============================================

export const UI_CONFIG = {
  /** Display name in the header. */
  agentName: "Vaquill Legal Assistant",
  /** Word-by-word reveal speed for assistant answers (ms per word). */
  wordAnimationDelayMs: 25,
  /** Max textarea height before scrolling kicks in (px). */
  textareaMaxHeightPx: 200,
} as const;

/**
 * Starter prompts shown on the empty chat. Pick questions the API can
 * actually ground in real US case law / statutes — random pop-culture
 * questions will fall back to ungrounded model output.
 */
export const EXAMPLE_QUESTIONS: readonly string[] = [
  "What is qualified immunity under 42 USC 1983?",
  "What are the elements of a Rule 10b-5 securities-fraud claim?",
  "What is the standard for granting a preliminary injunction in federal court?",
];
