/**
 * Vaquill Widget — Centralized Configuration
 *
 * All environment-driven config lives here.
 * Never import process.env directly in components — use these constants.
 */

// ============================================
// Helper parsers
// ============================================

function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (value === undefined) return defaultValue;
  return value.toLowerCase() === "true";
}

function parseNumber(value: string | undefined, defaultValue: number): number {
  if (value === undefined) return defaultValue;
  const parsed = parseInt(value, 10);
  return isNaN(parsed) ? defaultValue : parsed;
}

// ============================================
// Vaquill API
// ============================================

export const VAQUILL_CONFIG = {
  /** Server-side API key — NEVER expose to the browser */
  apiKey: process.env.VAQUILL_API_KEY ?? "",
  apiBaseUrl:
    process.env.VAQUILL_API_URL ?? "https://api.vaquill.ai/api/v1",
  /** Default RAG mode sent to /ask. Can be overridden per-request. */
  defaultMode: (process.env.NEXT_PUBLIC_DEFAULT_MODE ?? "standard") as
    | "standard"
    | "deep",
} as const;

// ============================================
// OpenAI (TTS / STT — optional)
// ============================================

export const OPENAI_CONFIG = {
  apiKey: process.env.OPENAI_API_KEY ?? "",
  ttsModel: process.env.OPENAI_TTS_MODEL ?? "tts-1",
  ttsVoice: process.env.OPENAI_TTS_VOICE ?? "nova",
  sttModel: process.env.STT_MODEL ?? "gpt-4o-mini-transcribe",
} as const;

// ============================================
// Widget UI (client-safe NEXT_PUBLIC_* values)
// ============================================

export const UI_CONFIG = {
  agentName:
    process.env.NEXT_PUBLIC_AGENT_NAME ?? "Vaquill Legal Assistant",
  theme: (process.env.NEXT_PUBLIC_THEME ?? "dark") as "dark" | "light",
  wordAnimationDelayMs: parseNumber(
    process.env.NEXT_PUBLIC_WORD_ANIMATION_DELAY_MS,
    25
  ),
  textareaMaxHeightPx: parseNumber(
    process.env.NEXT_PUBLIC_TEXTAREA_MAX_HEIGHT,
    200
  ),
} as const;

// ============================================
// Feature flags (derived)
// ============================================

export function getCapabilities() {
  const hasTTS = !!(OPENAI_CONFIG.apiKey);
  const hasSTT = !!(OPENAI_CONFIG.apiKey);
  return {
    tts_enabled: hasTTS,
    stt_enabled: hasSTT,
    voice_mode_enabled: hasTTS && hasSTT,
    ai_completions_enabled: !!(VAQUILL_CONFIG.apiKey),
  };
}

// ============================================
// Validation
// ============================================

export function validateConfig(): void {
  const errors: string[] = [];

  if (!VAQUILL_CONFIG.apiKey) {
    errors.push("VAQUILL_API_KEY is required");
  }

  if (errors.length > 0) {
    throw new Error(
      `Vaquill widget configuration error:\n${errors.map((e) => `  - ${e}`).join("\n")}`
    );
  }
}
