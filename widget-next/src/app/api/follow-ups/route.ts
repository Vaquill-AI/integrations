/**
 * POST /api/follow-ups
 *
 * Generates 3 short, contextual follow-up questions for the last Q&A
 * using OpenAI gpt-5-mini. Falls back to a generic list when the key
 * is unset or the call fails — the UI must always have *something*
 * to render under the assistant message.
 *
 * Request body:
 *   { question: string; answer: string }
 *
 * Response:
 *   { followUps: string[] }   // always length 3, never throws to client
 */

import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 15;

const FALLBACK_FOLLOW_UPS = [
  "Are there later cases that distinguish this holding?",
  "How have circuits split on this issue?",
  "What's the standard of review on appeal?",
];

const SYSTEM_PROMPT = `You generate short follow-up questions for a legal-research assistant.

Given a user question and the assistant's answer, return exactly 3 follow-up questions a legal researcher would naturally ask next. Each question must:
- be specific to the doctrine, statute, or facts in the answer (not generic boilerplate)
- be a single sentence, under 90 characters
- be phrased as something the user would type, not a heading
- avoid repeating the original question

Return JSON only: {"followUps": ["...", "...", "..."]}`;

interface OpenAIChatResponse {
  choices?: Array<{
    message?: { content?: string | null };
  }>;
}

async function generateFollowUps(
  question: string,
  answer: string,
  apiKey: string
): Promise<string[] | null> {
  // Cap the answer length we send — the full answer can be 4-6k tokens
  // and we only need the gist for follow-up generation. The first 2k
  // characters reliably cover the "Key Findings" + "Direct Answer"
  // sections.
  const trimmedAnswer = answer.length > 2000 ? answer.slice(0, 2000) + "…" : answer;

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-5-mini",
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content: `Question:\n${question}\n\nAnswer:\n${trimmedAnswer}`,
        },
      ],
      response_format: { type: "json_object" },
    }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    console.error(
      `[follow-ups] OpenAI ${response.status}: ${detail.slice(0, 200)}`
    );
    return null;
  }

  const data = (await response.json()) as OpenAIChatResponse;
  const content = data.choices?.[0]?.message?.content;
  if (!content) return null;

  try {
    const parsed = JSON.parse(content) as { followUps?: unknown };
    if (!Array.isArray(parsed.followUps)) return null;
    const clean = parsed.followUps
      .filter((q): q is string => typeof q === "string" && q.trim().length > 0)
      .map((q) => q.trim())
      .slice(0, 3);
    return clean.length === 3 ? clean : null;
  } catch {
    return null;
  }
}

export async function POST(request: NextRequest) {
  try {
    const { question, answer } = (await request.json()) as {
      question?: string;
      answer?: string;
    };

    if (
      !question ||
      typeof question !== "string" ||
      !answer ||
      typeof answer !== "string"
    ) {
      return NextResponse.json({ followUps: FALLBACK_FOLLOW_UPS });
    }

    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return NextResponse.json({ followUps: FALLBACK_FOLLOW_UPS });
    }

    const generated = await generateFollowUps(question, answer, apiKey);
    return NextResponse.json({
      followUps: generated ?? FALLBACK_FOLLOW_UPS,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "unknown";
    console.error("[follow-ups] error:", message);
    return NextResponse.json({ followUps: FALLBACK_FOLLOW_UPS });
  }
}
