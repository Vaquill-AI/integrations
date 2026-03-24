/**
 * GET /api/agent/capabilities
 *
 * Returns a capabilities object the client uses to toggle features like TTS/STT.
 * Derived from server-side environment variables so the browser never sees secrets.
 */

import { NextResponse } from "next/server";
import { getCapabilities } from "@/config/constants";

export const runtime = "nodejs";

export async function GET() {
  const capabilities = getCapabilities();

  return NextResponse.json({
    status: "success",
    data: {
      ...capabilities,
      provider_info: {
        ai: "Vaquill",
        tts: capabilities.tts_enabled
          ? process.env.OPENAI_TTS_MODEL ?? "tts-1"
          : undefined,
        stt: capabilities.stt_enabled
          ? process.env.STT_MODEL ?? "gpt-4o-mini-transcribe"
          : undefined,
      },
    },
  });
}
