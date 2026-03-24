/**
 * POST /api/chat/transcribe
 *
 * Speech-to-text via OpenAI Whisper.
 * Requires OPENAI_API_KEY to be set.
 *
 * Request: multipart/form-data with `audio` field (audio file)
 * Response: { success: true; transcript: string }
 */

import { NextRequest, NextResponse } from "next/server";
import { OPENAI_CONFIG } from "@/config/constants";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: NextRequest) {
  try {
    if (!OPENAI_CONFIG.apiKey) {
      return NextResponse.json(
        { success: false, error: "STT is not configured (OPENAI_API_KEY missing)" },
        { status: 503 }
      );
    }

    const formData = await request.formData();
    const audioFile = formData.get("audio") ?? formData.get("file");

    if (!audioFile || !(audioFile instanceof File)) {
      return NextResponse.json(
        { success: false, error: "No audio file provided" },
        { status: 400 }
      );
    }

    // Forward to OpenAI Whisper
    const openaiForm = new FormData();
    openaiForm.append("file", audioFile, audioFile.name || "recording.webm");
    openaiForm.append("model", OPENAI_CONFIG.sttModel);
    openaiForm.append("response_format", "text");

    const response = await fetch(
      "https://api.openai.com/v1/audio/transcriptions",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${OPENAI_CONFIG.apiKey}`,
        },
        body: openaiForm,
      }
    );

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const err = await response.json();
        detail = err?.error?.message ?? detail;
      } catch {
        // ignore
      }
      throw new Error(`OpenAI STT error: ${detail}`);
    }

    // When response_format=text the body is plain text
    const transcript = await response.text();

    return NextResponse.json({ success: true, transcript: transcript.trim() });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Transcription failed";
    console.error("[STT] Error:", message);
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
