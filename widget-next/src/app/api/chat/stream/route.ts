/**
 * POST /api/chat/stream
 *
 * SSE proxy to Vaquill POST /ask/stream.
 *
 * Emits Server-Sent Events:
 *   data: { type: "chunk", text: string }
 *   data: { type: "done", sources: VaquillSource[], questionInterpreted: string, mode: string }
 *   data: { type: "error", error: string }
 *
 * Request body:
 *   { question: string; mode?: "standard"|"deep"; chatHistory?: {role,content}[] }
 */

import { NextRequest, NextResponse } from "next/server";
import { vaquillClient, ChatHistoryEntry } from "@/lib/vaquill";
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

    // Mode, country, and maxSources enforced server-side. Client-sent
    // values are ignored.
    const upstreamResponse = await vaquillClient.askStream({
      question: question.trim(),
      mode: VAQUILL_CONFIG.mode,
      countryCode: VAQUILL_CONFIG.countryCode,
      maxSources: VAQUILL_CONFIG.maxSources,
      sources,
      chatHistory: chatHistory ?? [],
    });

    if (!upstreamResponse.body) {
      throw new Error("Upstream stream body is null");
    }

    const encoder = new TextEncoder();
    const upstreamReader = upstreamResponse.body.getReader();

    const stream = new ReadableStream({
      async start(controller) {
        const decoder = new TextDecoder();
        let buffer = "";

        const enqueue = (data: object) => {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
        };

        try {
          while (true) {
            const { done, value } = await upstreamReader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";

            for (const line of lines) {
              if (!line.trim()) continue;

              if (!line.startsWith("data: ")) continue;

              const dataStr = line.slice(6);

              try {
                const event = JSON.parse(dataStr);

                // Upstream Vaquill /ask/stream event types:
                //   stream_init       — first event, ignore
                //   thinking          — progress messages, ignore for now
                //   thinking_complete — ignore
                //   sources           — { sources: [...] } pre-stream
                //   chunk             — { content: "<token>" } answer text
                //   done              — final marker (may carry meta)
                //   error             — { error: "<msg>" }
                //
                // We normalise to a smaller set the client understands.
                if (event.type === "chunk" && typeof event.content === "string") {
                  enqueue({ type: "chunk", text: event.content });
                } else if (event.type === "thinking" && typeof event.message === "string") {
                  enqueue({ type: "status", message: event.message });
                } else if (event.type === "sources" && Array.isArray(event.sources)) {
                  enqueue({ type: "sources", sources: event.sources });
                } else if (event.type === "done") {
                  enqueue({
                    type: "done",
                    questionInterpreted: event.questionInterpreted ?? event.question_interpreted ?? "",
                  });
                  controller.close();
                  return;
                } else if (event.type === "error") {
                  enqueue({ type: "error", error: event.error ?? "Stream error" });
                  controller.close();
                  return;
                }
                // stream_init / thinking_complete are dropped
              } catch {
                // Malformed SSE line — skip
              }
            }
          }

          // Upstream closed without a done event — signal completion
          controller.close();
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : "Stream error";
          enqueue({ type: "error", error: message });
          controller.close();
        } finally {
          upstreamReader.releaseLock();
        }
      },
    });

    return new NextResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[Vaquill API] /api/chat/stream error:", message);
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
