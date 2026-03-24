/**
 * Vaquill Server-Side API Client
 *
 * Used exclusively in Next.js API routes (server-side).
 * Never import this module from client components.
 */

import { VAQUILL_CONFIG } from "@/config/constants";

// ============================================
// Request / Response Types
// ============================================

export type VaquillMode = "standard" | "deep";

export interface ChatHistoryEntry {
  role: "user" | "assistant";
  content: string;
}

export interface VaquillAskRequest {
  question: string;
  mode?: VaquillMode;
  sources?: string[];
  chatHistory?: ChatHistoryEntry[];
}

export interface VaquillSource {
  caseName: string;
  citation: string;
  court: string;
  excerpt: string;
  pdfUrl: string | null;
  relevanceScore: number;
}

export interface VaquillAskData {
  answer: string;
  sources: VaquillSource[];
  questionInterpreted: string;
  mode: VaquillMode;
}

export interface VaquillMeta {
  requestId: string;
  processingTimeMs: number;
  model: string;
  tokensUsed?: number;
}

export interface VaquillAskResponse {
  data: VaquillAskData;
  meta: VaquillMeta;
}

// ============================================
// Client Class
// ============================================

export class VaquillClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;

  constructor(apiKey?: string, baseUrl?: string) {
    this.apiKey = apiKey ?? VAQUILL_CONFIG.apiKey;
    this.baseUrl = baseUrl ?? VAQUILL_CONFIG.apiBaseUrl;

    if (!this.apiKey) {
      throw new Error(
        "VAQUILL_API_KEY is not configured. Set it in your environment variables."
      );
    }
  }

  private get headers(): HeadersInit {
    return {
      accept: "application/json",
      "content-type": "application/json",
      authorization: `Bearer ${this.apiKey}`,
    };
  }

  /**
   * Send a question to the Vaquill /ask endpoint (non-streaming).
   */
  async ask(payload: VaquillAskRequest): Promise<VaquillAskResponse> {
    const url = `${this.baseUrl}/ask`;

    const body: VaquillAskRequest = {
      question: payload.question,
      mode: payload.mode ?? VAQUILL_CONFIG.defaultMode,
      sources: payload.sources,
      chatHistory: payload.chatHistory ?? [],
    };

    const response = await fetch(url, {
      method: "POST",
      headers: this.headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const err = await response.json();
        detail = err?.detail ?? err?.message ?? detail;
      } catch {
        // ignore parse error
      }
      throw new Error(`Vaquill API error: ${detail}`);
    }

    return response.json() as Promise<VaquillAskResponse>;
  }

  /**
   * Send a question to the Vaquill /ask/stream endpoint (SSE).
   * Returns the raw Response object so the caller can pipe it.
   */
  async askStream(payload: VaquillAskRequest): Promise<Response> {
    const url = `${this.baseUrl}/ask/stream`;

    const body: VaquillAskRequest = {
      question: payload.question,
      mode: payload.mode ?? VAQUILL_CONFIG.defaultMode,
      sources: payload.sources,
      chatHistory: payload.chatHistory ?? [],
    };

    const response = await fetch(url, {
      method: "POST",
      headers: this.headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const err = await response.json();
        detail = err?.detail ?? err?.message ?? detail;
      } catch {
        // ignore parse error
      }
      throw new Error(`Vaquill API error (stream): ${detail}`);
    }

    return response;
  }
}

// Singleton instance — re-used across API route invocations
export const vaquillClient = new VaquillClient();
