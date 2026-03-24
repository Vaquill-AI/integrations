/**
 * POST /api/tts/speak
 *
 * Converts text to speech via OpenAI TTS and returns audio/mpeg bytes.
 * Requires OPENAI_API_KEY to be set.
 *
 * Request body: { text: string }
 * Response: audio/mpeg binary
 */

import { NextRequest, NextResponse } from "next/server";
import { OPENAI_CONFIG } from "@/config/constants";

export const runtime = "nodejs";
export const maxDuration = 30;

export async function POST(request: NextRequest) {
  try {
    if (!OPENAI_CONFIG.apiKey) {
      return NextResponse.json(
        { error: "TTS is not configured (OPENAI_API_KEY missing)" },
        { status: 503 }
      );
    }

    const { text } = await request.json();

    if (!text || typeof text !== "string") {
      return NextResponse.json({ error: "text is required" }, { status: 400 });
    }

    const response = await fetch("https://api.openai.com/v1/audio/speech", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENAI_CONFIG.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: OPENAI_CONFIG.ttsModel,
        voice: OPENAI_CONFIG.ttsVoice,
        input: text,
        response_format: "mp3",
      }),
    });

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const err = await response.json();
        detail = err?.error?.message ?? detail;
      } catch {
        // ignore
      }
      throw new Error(`OpenAI TTS error: ${detail}`);
    }

    const audioData = await response.arrayBuffer();

    return new NextResponse(audioData, {
      headers: { "Content-Type": "audio/mpeg" },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "TTS failed";
    console.error("[TTS] Error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
