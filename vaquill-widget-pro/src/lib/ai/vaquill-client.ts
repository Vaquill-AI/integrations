/**
 * Vaquill API Client
 *
 * Talks to the public Vaquill chat API at api.vaquill.ai. The legacy
 * project-id / session-based RAG service this client originally
 * targeted has been replaced by Vaquill's stateless `/ask` and
 * `/ask/stream` endpoints. To keep the existing widget UI + route
 * handlers working without rewiring every component, this module:
 *
 *   1. Maintains a process-local Map<sessionId, MessageData[]> that
 *      mimics the upstream's "fetch all messages for a session" call.
 *      The client sends prior turns to /ask as `chatHistory` so
 *      Vaquill can resolve "compare it with X" style follow-ups.
 *   2. Exposes the same class methods (`createConversation`,
 *      `sendMessage`, `sendMessageStream`, `getConversationMessages`,
 *      etc.) the existing `/api/chat/*` routes import.
 *   3. Stubs methods that have no Vaquill equivalent
 *      (`uploadFile`, per-message insights, citation-by-id lookup) so
 *      they don't throw — they degrade gracefully.
 *
 * Caveat: the in-memory session map is per Node process. On
 * Vercel/serverless cold starts it resets. The widget's own
 * client-side persistence (IndexedDB + localStorage) is the source
 * of truth for users — this server cache only smooths over the
 * route-handler contract during a single request lifecycle.
 */

import { VAQUILL_CONFIG } from '@/config/constants';

const BASE_URL = VAQUILL_CONFIG.apiBaseUrl;
const API_KEY = VAQUILL_CONFIG.apiKey;
const COUNTRY_CODE = VAQUILL_CONFIG.countryCode;
const MODE: 'standard' | 'deep' = VAQUILL_CONFIG.mode;

if (typeof window === 'undefined' && !API_KEY) {
  console.warn(
    '[Vaquill] VAQUILL_API_KEY is not set. Chat will return errors until configured.'
  );
}

// ============================================================================
// Public types — kept compatible with the legacy contract so route handlers
// and React components don't need refactoring.
// ============================================================================

export interface ConversationData {
  id: number;
  session_id: string;
  project_id: number;
  created_at: string;
}

export interface CustomerIntelligence {
  user_location?: string;
  language?: string;
  user_id?: number;
  external_id?: string;
  content_source?: string;
  user_emotion?: string;
  user_intent?: string;
  risk_fidelity?: string;
  risk_jailbreak?: string;
  risk_prompt_leakage?: string;
  risk_profanity?: string;
  country?: string;
  location?: string;
}

export interface MessageData {
  id: number;
  user_query: string;
  openai_response: string;
  citations?: number[];
  created_at: string;
  response_feedback?: {
    created_at: string;
    updated_at: string;
    user_id: number;
    reaction: 'liked' | 'disliked' | null;
  };
  customer_intelligence?: CustomerIntelligence;
}

export interface ApiResponse<T> {
  status: 'success' | 'error';
  data: T;
  message?: string;
}

export interface StreamData {
  status: 'progress' | 'finish' | 'error';
  message?: string;
  error?: string;
}

/**
 * Capability tier — maps to Vaquill's `mode` parameter.
 * fastest/optimal → standard (faster, fewer techniques)
 * advanced/complex → deep    (35+ techniques, hallucination detection)
 */
export type AgentCapability =
  | 'fastest-responses'
  | 'optimal-choice'
  | 'advanced-reasoning'
  | 'complex-tasks';

export const AGENT_CAPABILITIES: { value: AgentCapability; label: string; description: string }[] = [
  { value: 'fastest-responses', label: 'Fastest', description: 'Quick responses for simple queries' },
  { value: 'optimal-choice', label: 'Optimal', description: 'Balanced speed and quality' },
  { value: 'advanced-reasoning', label: 'Advanced', description: 'Enhanced reasoning capabilities' },
  { value: 'complex-tasks', label: 'Complex', description: 'Most capable for complex tasks' },
];

function capabilityToMode(cap: AgentCapability | undefined): 'standard' | 'deep' {
  if (cap === 'advanced-reasoning' || cap === 'complex-tasks') return 'deep';
  if (cap === 'fastest-responses' || cap === 'optimal-choice') return 'standard';
  return MODE;
}

export interface AgentSettings {
  chatbot_avatar: string | null;
  chatbot_background_type?: string;
  chatbot_background?: string;
  chatbot_background_color?: string;
  default_prompt?: string;
  example_questions: string[];
  response_source?: string;
  chatbot_msg_lang?: string;
  chatbot_color?: string;
  chatbot_toolbar_color?: string;
  persona_instructions?: string;
  citations_answer_source_label_msg?: string;
  citations_sources_label_msg?: string;
  hang_in_there_msg?: string;
  chatbot_siesta_msg?: string;
  is_loading_indicator_enabled?: boolean;
  enable_citations?: number;
  enable_feedbacks?: boolean;
  citations_view_type?: string;
  image_citation_display?: string;
  no_answer_message?: string;
  ending_message?: string;
  try_asking_questions_msg?: string;
  view_more_msg?: string;
  view_less_msg?: string;
  remove_branding?: boolean;
  private_deployment?: boolean;
  enable_recaptcha_for_public_chatbots?: boolean;
  chatbot_model?: string;
  is_selling_enabled?: boolean;
  license_slug?: boolean;
  selling_url?: string;
  can_share_conversation?: boolean;
  can_export_conversation?: boolean;
  hide_sources_from_responses?: boolean;
  input_field_addendum?: string;
  user_avatar?: string;
  spotlight_avatar_enabled?: boolean;
  spotlight_avatar?: string;
  spotlight_avatar_shape?: string;
  spotlight_avatar_type?: string;
  user_avatar_orientation?: string;
  chatbot_title: string;
  chatbot_title_color?: string;
  enable_inline_citations_api?: boolean;
  conversation_time_window?: boolean;
  conversation_retention_period?: string;
  conversation_retention_days?: number;
  enable_agent_knowledge_base_awareness?: boolean;
  markdown_enabled?: boolean;
}

export interface AgentDetails {
  id: number;
  project_name: string;
  sitemap_path?: string;
  is_chat_active: boolean;
  user_id: number;
  team_id: number;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  type: string;
  is_shared: boolean;
  shareable_slug?: string;
  shareable_link?: string;
  embed_code?: string;
  live_chat_code?: string;
  are_licenses_allowed?: boolean;
}

export interface SourcePage {
  id: number;
  page_url: string;
  page_url_hash: string;
  project_id: number;
  s3_path: string;
  crawl_status: 'queued' | 'crawled' | 'failed';
  index_status: 'queued' | 'indexed' | 'failed';
  is_file: boolean;
  is_refreshable: boolean;
  is_file_kept: boolean;
  filename: string;
  filesize: number;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

export interface SourceData {
  id: number;
  created_at: string;
  updated_at: string;
  type: 'sitemap' | 'upload';
  settings: {
    executive_js?: boolean;
    data_refresh_frequency?: string;
    create_new_pages?: boolean;
    remove_unexist_pages?: boolean;
    refresh_existing_pages?: string;
    sitemap_path?: string;
  };
  pages: SourcePage[];
}

// ============================================================================
// Vaquill /ask response shape (subset we use).
// ============================================================================

interface VaquillAskSource {
  sourceIndex: number;
  citation: string | null;
  caseName: string | null;
  court: string | null;
  year: number | null;
  excerpt: string;
  relevanceScore: number;
  pdfUrl: string | null;
  externalUrl: string | null;
  sourceType?: string | null;
  corpusType?: string | null;
  htmlUrl?: string | null;
  statutePdfUrl?: string | null;
  xmlUrl?: string | null;
  govInfoHtmlUrl?: string | null;
  govInfoPdfUrl?: string | null;
}

interface VaquillAskResponse {
  data: {
    answer: string;
    sources: VaquillAskSource[];
    questionInterpreted?: string;
    mode: 'standard' | 'deep';
  };
  meta?: {
    processingTimeMs?: number;
    creditsConsumed?: number;
    creditsRemaining?: number;
  };
}

// ============================================================================
// Server-side session cache. Each entry is the chronological list of
// MessageData for that session. This is process-local and resets on
// cold start — the React UI maintains its own durable copy in
// IndexedDB / localStorage, so a cache miss here just means "no prior
// turns sent to Vaquill on this request" rather than data loss.
// ============================================================================

const sessionStore = new Map<string, MessageData[]>();
let nextMessageId = 1;
let nextConversationId = 1;
const sessionSources = new Map<number, VaquillAskSource>(); // messageId -> sources for citation lookup
const messageSourceIndex = new Map<number, VaquillAskSource[]>(); // messageId -> source list

function nowIso(): string {
  return new Date().toISOString();
}

function makeSessionId(): string {
  // RFC4122 v4 via crypto. Falls back to Math.random in environments
  // where crypto.randomUUID isn't available (very old Node).
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function buildChatHistory(sessionId: string): { role: 'user' | 'assistant'; content: string }[] {
  const messages = sessionStore.get(sessionId) ?? [];
  const history: { role: 'user' | 'assistant'; content: string }[] = [];
  for (const m of messages) {
    history.push({ role: 'user', content: m.user_query });
    if (m.openai_response) history.push({ role: 'assistant', content: m.openai_response });
  }
  // Vaquill caps history at 20 entries.
  return history.slice(-20);
}

function recordMessage(
  sessionId: string,
  userMessage: string,
  answer: string,
  sources: VaquillAskSource[]
): MessageData {
  const id = nextMessageId++;
  const sourceIndices = sources.map((s) => s.sourceIndex);

  // Cache sources keyed by both messageId and individual citation index
  // so getCitationDetails / getMessageWithInsights can look them up.
  messageSourceIndex.set(id, sources);
  for (const s of sources) sessionSources.set(s.sourceIndex, s);

  const message: MessageData = {
    id,
    user_query: userMessage,
    openai_response: answer,
    citations: sourceIndices,
    created_at: nowIso(),
  };
  const list = sessionStore.get(sessionId) ?? [];
  list.push(message);
  sessionStore.set(sessionId, list);
  return message;
}

// ============================================================================
// Client class
// ============================================================================

export class VaquillClient {
  private baseUrl: string;
  private apiKey: string;

  constructor() {
    this.baseUrl = BASE_URL;
    this.apiKey = API_KEY;
  }

  isConfigured(): boolean {
    return !!this.apiKey;
  }

  private ensureConfigured(): void {
    if (!this.isConfigured()) {
      throw new Error('Vaquill is not configured: VAQUILL_API_KEY is missing.');
    }
  }

  private getHeaders(): HeadersInit {
    return {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      Authorization: `Bearer ${this.apiKey}`,
    };
  }

  // --------------------------------------------------------------------------
  // Conversation lifecycle — synthetic on the server, real on the client.
  // --------------------------------------------------------------------------

  async createConversation(): Promise<ConversationData> {
    const sessionId = makeSessionId();
    sessionStore.set(sessionId, []);
    return {
      id: nextConversationId++,
      session_id: sessionId,
      project_id: 0,
      created_at: nowIso(),
    };
  }

  async deleteConversation(sessionId: string): Promise<boolean> {
    sessionStore.delete(sessionId);
    return true;
  }

  async getConversationMessages(sessionId: string): Promise<MessageData[]> {
    return sessionStore.get(sessionId) ?? [];
  }

  // --------------------------------------------------------------------------
  // Chat — the only routes that actually hit Vaquill's API.
  // --------------------------------------------------------------------------

  async sendMessage(
    sessionId: string,
    userMessage: string,
    agentCapability?: AgentCapability
  ): Promise<MessageData> {
    this.ensureConfigured();

    // Make sure the session exists so getConversationMessages can find it later.
    if (!sessionStore.has(sessionId)) sessionStore.set(sessionId, []);

    const chatHistory = buildChatHistory(sessionId);
    const body = {
      question: userMessage,
      mode: capabilityToMode(agentCapability),
      countryCode: COUNTRY_CODE,
      chatHistory,
    };

    const res = await fetch(`${this.baseUrl}/ask`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const err = await res.json();
        detail = err?.detail ?? err?.message ?? detail;
      } catch {
        // ignore
      }
      throw new Error(`Vaquill /ask failed: ${detail}`);
    }

    const json = (await res.json()) as VaquillAskResponse;
    const answer = json?.data?.answer ?? '';
    const sources = json?.data?.sources ?? [];
    return recordMessage(sessionId, userMessage, answer, sources);
  }

  /**
   * Streaming chat — yields answer-text chunks as they arrive from
   * Vaquill `/ask/stream`. The full answer + sources are persisted to
   * the session map once the stream finishes so subsequent
   * `getConversationMessages` calls return the new turn.
   */
  async *sendMessageStream(
    sessionId: string,
    userMessage: string,
    agentCapability?: AgentCapability
  ): AsyncGenerator<string, void, unknown> {
    this.ensureConfigured();
    if (!sessionStore.has(sessionId)) sessionStore.set(sessionId, []);

    const chatHistory = buildChatHistory(sessionId);
    const body = {
      question: userMessage,
      mode: capabilityToMode(agentCapability),
      countryCode: COUNTRY_CODE,
      chatHistory,
    };

    const res = await fetch(`${this.baseUrl}/ask/stream`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(body),
    });

    if (!res.ok || !res.body) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const err = await res.json();
        detail = err?.detail ?? err?.message ?? detail;
      } catch {
        // ignore
      }
      throw new Error(`Vaquill /ask/stream failed: ${detail}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let assembled = '';
    let finalSources: VaquillAskSource[] = [];

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const dataStr = trimmed.slice(5).trim();
          if (!dataStr) continue;

          let event: any;
          try {
            event = JSON.parse(dataStr);
          } catch {
            continue;
          }

          if (event.type === 'chunk' && typeof event.content === 'string') {
            assembled += event.content;
            yield event.content;
          } else if (event.type === 'sources' && Array.isArray(event.sources)) {
            finalSources = event.sources as VaquillAskSource[];
          } else if (event.type === 'error') {
            throw new Error(event.error ?? 'Vaquill stream error');
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    // Persist the assembled turn so it shows up in conversation history.
    recordMessage(sessionId, userMessage, assembled, finalSources);
  }

  // --------------------------------------------------------------------------
  // Per-message extras — Vaquill's API doesn't store messages
  // server-side, so feedback / insights / citation lookups operate on
  // the local session cache.
  // --------------------------------------------------------------------------

  async updateMessageReaction(
    sessionId: string,
    messageId: number,
    reaction: 'liked' | 'disliked' | null
  ): Promise<MessageData> {
    // Vaquill has no server-side feedback endpoint, so we record the
    // reaction on the local session-cached message and echo it back.
    // The UI can also persist client-side if it wants durability.
    const messages = sessionStore.get(sessionId) ?? [];
    const idx = messages.findIndex((m) => m.id === messageId);
    if (idx === -1) {
      throw new Error(`Message ${messageId} not found in session ${sessionId}`);
    }
    const updated: MessageData = {
      ...messages[idx],
      response_feedback: {
        created_at: messages[idx].response_feedback?.created_at ?? nowIso(),
        updated_at: nowIso(),
        user_id: 0,
        reaction,
      },
    };
    messages[idx] = updated;
    sessionStore.set(sessionId, messages);
    return updated;
  }

  async getMessageWithInsights(sessionId: string, messageId: number): Promise<MessageData> {
    const messages = sessionStore.get(sessionId) ?? [];
    const found = messages.find((m) => m.id === messageId);
    if (!found) {
      throw new Error(`Message ${messageId} not found in session ${sessionId}`);
    }
    return found;
  }

  async getCitationDetails(citationId: number): Promise<VaquillAskSource | null> {
    return sessionSources.get(citationId) ?? null;
  }

  // --------------------------------------------------------------------------
  // Agent metadata — Vaquill is a hosted multi-tenant API, so there's no
  // per-deployment agent "settings" object. Return sensible defaults.
  // --------------------------------------------------------------------------

  async getAgentSettings(): Promise<AgentSettings> {
    return {
      chatbot_avatar: null,
      example_questions: [
        'What is qualified immunity under 42 USC 1983?',
        'What are the elements of a Rule 10b-5 securities-fraud claim?',
        "What's the standard for granting a preliminary injunction?",
      ],
      chatbot_title: 'Vaquill Legal Assistant',
      chatbot_color: '#6e3730',
      chatbot_toolbar_color: '#6e3730',
      chatbot_msg_lang: 'en',
      enable_citations: 3,
      enable_feedbacks: true,
      citations_view_type: 'cards',
      markdown_enabled: true,
      hide_sources_from_responses: false,
      can_share_conversation: false,
      can_export_conversation: true,
      remove_branding: false,
      input_field_addendum: 'Information only, not legal advice. Verify all citations.',
      no_answer_message:
        "I couldn't find authoritative US legal sources for that. Try rephrasing or narrowing the question.",
      try_asking_questions_msg: 'Try asking:',
      view_more_msg: 'View more',
      view_less_msg: 'View less',
    };
  }

  async getAgentDetails(): Promise<AgentDetails> {
    return {
      id: 0,
      project_name: 'Vaquill Legal Assistant',
      is_chat_active: true,
      user_id: 0,
      team_id: 0,
      created_at: nowIso(),
      updated_at: nowIso(),
      type: 'chatbot',
      is_shared: false,
      are_licenses_allowed: false,
    };
  }

  // --------------------------------------------------------------------------
  // Source upload — not supported by Vaquill /ask. The widget's upload
  // UI is preserved for future RAG-ingestion work; for now we throw a
  // clear, recoverable error so the UI can show "uploads not available".
  // --------------------------------------------------------------------------

  async uploadFile(_file: File): Promise<SourceData> {
    throw new Error(
      'File uploads are not supported by the Vaquill chat API. Use the Vaquill matter-document endpoints to ingest files.'
    );
  }
}

export const vaquillClient = new VaquillClient();
