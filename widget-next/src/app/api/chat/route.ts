/**
 * POST /api/chat
 *
 * Proxy to Vaquill POST /ask (non-streaming).
 *
 * Request body:
 *   { question: string; mode?: "standard"|"deep"; chatHistory?: {role,content}[] }
 *
 * Response:
 *   { success: true; answer: string; sources: VaquillSource[]; questionInterpreted: string; mode: string }
 */

import { NextRequest, NextResponse } from "next/server";
import { vaquillClient, ChatHistoryEntry } from "@/lib/vaquill";
import { processMarkdown } from "@/lib/markdown";
import { VAQUILL_CONFIG } from "@/config/constants";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      question,
      sources,
      chatHistory,
    }: {
      question?: string;
      sources?: string[];
      chatHistory?: ChatHistoryEntry[];
    } = body;

    if (!question || typeof question !== "string" || !question.trim()) {
      return NextResponse.json(
        { success: false, error: "question is required" },
        { status: 400 }
      );
    }

    const startTime = performance.now();

    // Mode, country, and maxSources are enforced server-side from env.
    // Client-sent values are intentionally ignored.
    const result = await vaquillClient.ask({
      question: question.trim(),
      mode: VAQUILL_CONFIG.mode,
      countryCode: VAQUILL_CONFIG.countryCode,
      maxSources: VAQUILL_CONFIG.maxSources,
      sources,
      chatHistory: chatHistory ?? [],
    });

    const durationS = ((performance.now() - startTime) / 1000).toFixed(3);
    console.log(
      `[Vaquill API] /ask completed in ${durationS}s (mode: ${result.data.mode})`
    );

    return NextResponse.json({
      success: true,
      answer: processMarkdown(result.data.answer),
      sources: result.data.sources,
      questionInterpreted: result.data.questionInterpreted,
      mode: result.data.mode,
      meta: result.meta,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[Vaquill API] /api/chat error:", message);
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
