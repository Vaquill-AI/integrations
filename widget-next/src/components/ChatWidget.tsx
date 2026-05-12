"use client";

import { memo, useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import type { VaquillSource } from "@/lib/vaquill";
import { UI_CONFIG } from "@/config/constants";
import { linkifyCitations } from "@/lib/markdown";

// ============================================
// Types
// ============================================

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  sources?: VaquillSource[];
  questionInterpreted?: string;
  /** LLM-generated follow-ups, fetched after the answer streams in. */
  followUps?: string[];
  /**
   * Local error placeholder (not a real assistant answer). These must
   * never be sent back to the upstream API in chatHistory — the API has
   * been observed to 422 on a payload polluted by repeated error
   * placeholders.
   */
  isError?: boolean;
}

interface ChatWidgetProps {
  /** Override the display name shown in the header */
  agentName?: string;
  /** Initial placeholder questions shown before first message */
  exampleQuestions?: string[];
  /**
   * True when the widget is loaded inside the floating embed iframe.
   * The outer floating window already shows the title + close button,
   * so we hide the widget's own header to avoid a duplicate.
   */
  embedded?: boolean;
}

// ============================================
// Source card
// ============================================

/**
 * Force `http://` URLs onto HTTPS so browsers don't refuse to navigate
 * from a secure page (mixed-content block). Most US court PDFs are
 * served over HTTPS too — the API just returns the canonical HTTP
 * variant for some courts.
 */
function upgradeHttp(url: string | null | undefined): string | null {
  if (!url) return null;
  return url.startsWith("http://") ? "https://" + url.slice(7) : url;
}

/**
 * Public Vaquill statute viewer. Sections live at
 *   https://statutes.vaquill.ai/section/{actId}
 * and render readable HTML for free — no auth, no app login. This is
 * the right link to surface to chatbot embedders (the app at
 * app.vaquill.ai requires an account).
 */
const VAQUILL_STATUTE_VIEWER = "https://statutes.vaquill.ai";

/**
 * Derive the canonical Vaquill viewer URL.
 *
 * USC actId is `USC_T{title}_C{chapter}_S{section}`. The chapter
 * isn't in the citation string — it's encoded in the API's `htmlUrl`
 * (and the govinfo `externalUrl`) as `…-chap{N}-…`. We parse from
 * those URLs first; the citation alone can't reconstruct it.
 *
 *   htmlUrl "/USCODE-2024-title12-chap22-sec1972.htm"
 *     → /section/USC_T12_C22_S1972
 *
 *   htmlUrl "/USCODE-2024-title12-chap53-subchapII-sec5390.htm"
 *     → /section/USC_T12_C53_S5390   (subchapter dropped — viewer
 *                                      uses chapter only)
 *
 * CFR actId is `CFR_T{title}_P{part}_S{section}`. The citation has
 * everything we need.
 *
 *   "17 C.F.R. § 240.10b-5"
 *     → /section/CFR_T17_P240_S240_10b_5
 */
function buildStatuteViewerUrl(source: VaquillSource): string | null {
  // ── USC ──
  if (source.corpusType === "USC") {
    // Try every URL-shaped field that might encode the chapter.
    const probes = [source.htmlUrl, source.pdfUrl, source.externalUrl].filter(
      (u): u is string => typeof u === "string" && u.length > 0
    );
    for (const url of probes) {
      // Match the canonical USCODE path:
      //   …title{N}-chap{X}[-subchap…]-sec{Y}[.ext]
      const m =
        /title(\d+)[\s\S]*?chap(\w+?)(?:-subchap\w+)?-sec([\w-]+?)(?:\.(?:htm|html|pdf|xml))?(?:[/?#]|$)/i.exec(
          url
        );
      if (m) {
        return `${VAQUILL_STATUTE_VIEWER}/section/USC_T${m[1]}_C${m[2]}_S${m[3]}`;
      }
    }
    // Couldn't reconstruct chapter — caller will fall back to the
    // raw R2 htmlUrl, which is still readable HTML.
    return null;
  }

  // ── CFR ──
  if (source.corpusType === "CFR") {
    const citation = source.citation;
    if (!citation) return null;
    const cfr = /^\s*(\d+)\s*C\.?\s*F\.?\s*R\.?\s*§?\s*([\d\w.-]+)/i.exec(citation);
    if (!cfr) return null;
    const title = cfr[1];
    const fullSection = cfr[2];
    const partMatch = /^(\d+)/.exec(fullSection);
    if (!partMatch) return null;
    const part = partMatch[1];
    // 380.23 → 380_23, 240.10b-5 → 240_10b_5
    const safeSection = fullSection.replace(/[.\-]/g, "_");
    return `${VAQUILL_STATUTE_VIEWER}/section/CFR_T${title}_P${part}_S${safeSection}`;
  }

  return null;
}

/**
 * Resolve the link list for a source by `sourceType`. Vaquill-hosted
 * URLs are the only thing we surface for statutes — external fallbacks
 * (govinfo, ecfr) are dropped when any Vaquill URL is present, since
 * we host the canonical content ourselves at `statutes-us.vaquill.ai`.
 * External is used only when the Vaquill copy is genuinely unavailable.
 *
 * For case-law sources Vaquill doesn't host opinions, so the court CDN
 * `pdfUrl` and (if no PDF) the external opinion link are the only
 * options.
 *
 * All URLs are upgraded to HTTPS so secure pages don't refuse the
 * navigation as mixed content.
 */
function resolveSourceLinks(
  source: VaquillSource
): Array<{ label: string; href: string; primary?: boolean }> {
  const links: Array<{ label: string; href: string; primary?: boolean }> = [];
  const pdfUrl = upgradeHttp(source.pdfUrl);
  const externalUrl = upgradeHttp(source.externalUrl);
  const htmlUrl = upgradeHttp(source.htmlUrl);
  const statutePdfUrl = upgradeHttp(source.statutePdfUrl);
  const xmlUrl = upgradeHttp(source.xmlUrl);

  if (source.sourceType === "us_statute") {
    // Primary: the Vaquill app viewer (readable HTML page) derived
    // from the citation. If we can't parse the citation, fall back to
    // the raw R2 `.htm` (which still works, just less polished).
    const viewerUrl = buildStatuteViewerUrl(source);
    if (viewerUrl) {
      links.push({ label: "Read on Vaquill", href: viewerUrl, primary: true });
    } else if (htmlUrl) {
      links.push({ label: "Read on Vaquill", href: htmlUrl, primary: true });
    }
    // Secondary: a PDF download for offline use. Skip the raw XML —
    // it's machine-readable, not user-readable.
    if (statutePdfUrl) {
      links.push({ label: "PDF", href: statutePdfUrl, primary: !links.length });
    }
    // Last-resort fallback: only if we have no Vaquill resource at all
    // do we surface the official source (govinfo / ecfr).
    if (links.length === 0 && externalUrl) {
      links.push({ label: "Official source", href: externalUrl, primary: true });
    }
    void xmlUrl; // intentionally unused — XML is not user-facing
    return links.slice(0, 3);
  }

  // US case opinions — Vaquill doesn't host these; the court's own CDN
  // PDF is the canonical link.
  if (pdfUrl) links.push({ label: "View opinion PDF", href: pdfUrl, primary: true });
  if (externalUrl)
    links.push({ label: "Open opinion", href: externalUrl, primary: !links.length });
  return links.slice(0, 3);
}

function formatYear(source: VaquillSource): string | null {
  if (source.year) return String(source.year);
  if (source.decisionDate) {
    const m = /^(\d{4})/.exec(source.decisionDate);
    if (m) return m[1];
  }
  return null;
}

function SourceCard({ source, msgId }: { source: VaquillSource; msgId: string }) {
  const isStatute = source.sourceType === "us_statute";
  const links = resolveSourceLinks(source);
  const year = formatYear(source);
  const meta: string[] = [];
  if (source.court) meta.push(source.court);
  if (year) meta.push(year);
  if (source.disposition) meta.push(source.disposition);

  return (
    <div className="source-card" id={`src-${msgId}-${source.sourceIndex}`}>
      <span
        className="source-index"
        aria-label={`Source ${source.sourceIndex}`}
      >
        {source.sourceIndex}
      </span>

      <div className="source-card-header">
        <span className="source-case-name">
          {source.caseName ?? source.citation ?? "Untitled source"}
        </span>
      </div>

      <div className="source-meta">
        {isStatute && (
          <span className="source-badge source-badge--statute">
            {source.corpusType ?? "Statute"}
          </span>
        )}
        {source.citation && <span className="source-citation">{source.citation}</span>}
        {meta.length > 0 && source.citation && <span className="source-separator">·</span>}
        {meta.length > 0 && (
          <span className="source-court">{meta.join(" · ")}</span>
        )}
      </div>

      {source.docketNumber && (
        <div className="source-meta source-meta--secondary">
          <span>Docket: {source.docketNumber}</span>
        </div>
      )}

      {source.excerpt && (
        <p className="source-excerpt">&ldquo;{source.excerpt}&rdquo;</p>
      )}

      {links.length > 0 && (
        <div className="source-links">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              target="_blank"
              rel="noopener noreferrer"
              className={`source-pdf-link${l.primary ? " source-pdf-link--primary" : ""}`}
            >
              {l.label}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// Citation verification — count `[N]` markers in the answer, check that
// every one resolves to a real source.sourceIndex. Used for the
// "All N citations grounded" badge on the assistant header.
// ============================================

function verifyCitations(
  content: string,
  sources: VaquillSource[] | undefined
): { total: number; matched: number; allGrounded: boolean } {
  const indices = new Set<number>();
  const re = /\[(\d+)\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(content)) !== null) {
    indices.add(Number(m[1]));
  }
  const sourceSet = new Set((sources ?? []).map((s) => s.sourceIndex));
  let matched = 0;
  for (const i of indices) if (sourceSet.has(i)) matched++;
  return {
    total: indices.size,
    matched,
    allGrounded: indices.size > 0 && matched === indices.size,
  };
}

// Fallback follow-ups used until the LLM-generated set lands (and if
// the /api/follow-ups call fails entirely). Generic prompts that work
// after any legal answer.
const FALLBACK_FOLLOW_UPS: readonly string[] = [
  "Are there later cases that distinguish this holding?",
  "How have circuits split on this issue?",
  "What's the standard of review on appeal?",
];

// ============================================
// Persistence — localStorage so chat survives refresh + close-reopen.
// Keep the last MAX_PERSISTED messages (50 user+assistant turns) to
// avoid unbounded growth. Schema-versioned so we can evolve later.
// ============================================

const STORAGE_KEY = "vaquill-widget-messages-v1";
const MAX_PERSISTED = 50;

function loadStoredMessages(): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Light validation — drop anything missing required shape.
    return parsed.filter(
      (m) =>
        m &&
        typeof m.id === "string" &&
        (m.role === "user" || m.role === "assistant") &&
        typeof m.content === "string"
    );
  } catch {
    return [];
  }
}

function saveStoredMessages(messages: Message[]): void {
  if (typeof window === "undefined") return;
  try {
    const trimmed = messages.slice(-MAX_PERSISTED);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    // Quota exceeded or storage disabled — silently skip.
  }
}

function clearStoredMessages(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

// ============================================
// Citation link — replaces ReactMarkdown's default `<a>` rendering for
// `[N]` markers. Provides:
//   - Hover popover with case name, court, year, and a 240-char excerpt
//   - Click → jump to source card (expands the source panel if collapsed,
//     scrolls into view, briefly highlights via :target)
// ============================================

interface CitationLinkProps {
  href: string;
  children: React.ReactNode;
  source: VaquillSource | undefined;
  onJump: () => void;
}

// Popover dimensions used for viewport-edge clamping. Must match the
// CSS `.cite-popover` width / approximate height — the JS pre-computes
// position so the popover never spills off-screen.
const CITE_POPOVER_WIDTH = 320;
const CITE_POPOVER_VPAD = 16;

function CitationLink({ href, children, source, onJump }: CitationLinkProps) {
  const wrapRef = useRef<HTMLSpanElement>(null);
  const [hovered, setHovered] = useState(false);
  const [coords, setCoords] = useState<{ left: number; top: number } | null>(null);
  const [mounted, setMounted] = useState(false);

  // Mount flag so the portal isn't attempted during SSR (the parent
  // already runs ssr:false but we keep this defensive).
  useEffect(() => {
    setMounted(true);
  }, []);

  const showPopover = useCallback(() => {
    const el = wrapRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    // Anchor: just above the link, horizontally centred — but clamp so
    // the 320px-wide popover stays fully inside the viewport.
    const half = CITE_POPOVER_WIDTH / 2;
    const minX = CITE_POPOVER_VPAD + half;
    const maxX = window.innerWidth - CITE_POPOVER_VPAD - half;
    const wantedX = r.left + r.width / 2;
    const left = Math.max(minX, Math.min(maxX, wantedX));
    const top = r.top - 8; // 8px gap above the link
    setCoords({ left, top });
    setHovered(true);
  }, []);

  const hidePopover = useCallback(() => {
    setHovered(false);
  }, []);

  if (!source) {
    // Orphan marker (no matching source). Render as plain text so users
    // don't click into a broken anchor.
    return <span className="cite-link cite-link--orphan">{children}</span>;
  }

  return (
    <>
      <span
        ref={wrapRef}
        className="cite-link-wrap"
        onMouseEnter={showPopover}
        onMouseLeave={hidePopover}
        onFocus={showPopover}
        onBlur={hidePopover}
      >
        <a
          href={href}
          className="cite-link"
          onClick={(e) => {
            e.preventDefault();
            onJump();
          }}
        >
          {children}
        </a>
      </span>
      {mounted && hovered && coords &&
        createPortal(
          <span
            className="cite-popover"
            role="tooltip"
            style={{ left: coords.left, top: coords.top }}
          >
            <span className="cite-popover-title">
              {source.caseName ?? source.citation ?? "Untitled source"}
            </span>
            {(source.court || source.year) && (
              <span className="cite-popover-meta">
                {source.court}
                {source.court && source.year ? " · " : ""}
                {source.year ?? ""}
              </span>
            )}
            {source.excerpt && (
              <span className="cite-popover-excerpt">
                “{source.excerpt.length > 240 ? source.excerpt.slice(0, 240) + "…" : source.excerpt}”
              </span>
            )}
          </span>,
          document.body
        )}
    </>
  );
}

// ============================================
// Assistant body — memoised so already-completed messages don't re-parse
// markdown when a NEW message is streaming. Re-renders only when its own
// content / sources / id / onJump callback change.
// ============================================

interface AssistantBodyProps {
  msgId: string;
  content: string;
  sources: VaquillSource[] | undefined;
  onJumpToSource: (msgId: string, sourceIndex: number) => void;
}

const AssistantBody = memo(function AssistantBody({
  msgId,
  content,
  sources,
  onJumpToSource,
}: AssistantBodyProps) {
  const sourceMap = new Map<number, VaquillSource>();
  (sources ?? []).forEach((s) => sourceMap.set(s.sourceIndex, s));

  const text =
    sources && sources.length > 0
      ? linkifyCitations(content, msgId, new Set(sourceMap.keys()))
      : content;

  const anchorPrefix = `#src-${msgId}-`;

  return (
    <div className="message-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          a: ({ href, children, ...rest }) => {
            if (typeof href === "string" && href.startsWith(anchorPrefix)) {
              const n = Number(href.slice(anchorPrefix.length));
              const src = Number.isFinite(n) ? sourceMap.get(n) : undefined;
              return (
                <CitationLink
                  href={href}
                  source={src}
                  onJump={() => onJumpToSource(msgId, n)}
                >
                  {children}
                </CitationLink>
              );
            }
            // External markdown links — open in new tab for safety.
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" {...rest}>
                {children}
              </a>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
});

// ============================================
// ChatWidget
// ============================================

export default function ChatWidget({
  agentName = UI_CONFIG.agentName,
  exampleQuestions = [],
  embedded = false,
}: ChatWidgetProps) {
  // Hydrate from localStorage on mount. We start with [] for SSR safety
  // (the widget already runs ssr:false but useState's initialiser fires on
  // first client render — reading localStorage there is fine). We keep
  // the empty initial value so the empty-state flash doesn't happen
  // before hydration on slow devices.
  const [messages, setMessages] = useState<Message[]>(() => loadStoredMessages());
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);
  // Streaming progress — shown in the empty-content assistant bubble so
  // users know to wait during the 30-60s answer-generation window.
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [streamingStatus, setStreamingStatus] = useState<string>("Searching legal cases…");
  const [streamingElapsed, setStreamingElapsed] = useState<number>(0);
  const streamingStartedAtRef = useRef<number>(0);

  // Tick a 1s timer while a message is streaming so the elapsed badge
  // updates without re-rendering every message.
  useEffect(() => {
    if (!streamingId) return;
    const id = window.setInterval(() => {
      setStreamingElapsed(
        Math.floor((Date.now() - streamingStartedAtRef.current) / 1000)
      );
    }, 1000);
    return () => window.clearInterval(id);
  }, [streamingId]);

  // Persist messages whenever they change. Skipped while streaming would
  // be nice (less write churn) but real-world chats are short enough that
  // per-update writes are imperceptible — and we get instant resume on
  // refresh-mid-answer.
  useEffect(() => {
    saveStoredMessages(messages);
  }, [messages]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setExpandedSources(new Set());
    setStreamingId(null);
    clearStoredMessages();
  }, []);

  // The floating embed.js header has a "New chat" button. It posts a
  // message to the iframe; we listen here and clear state. When the
  // widget is embedded on a customer site (cross-origin parent), the
  // message naturally arrives with a different origin than the iframe —
  // so we authenticate on the message *shape* instead. The action (wipe
  // local chat state) carries no sensitive data.
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "vaquill:new-chat") handleNewChat();
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [handleNewChat]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // True while the user is parked near the bottom (so we follow new tokens).
  // Flips false the moment they scroll up to read — we then leave them alone.
  const stickToBottomRef = useRef(true);

  // Track whether the user is at the bottom of the scroll container.
  // Threshold of 64px tolerates fractional pixels + the "near enough" feel
  // every chat app uses (Slack, ChatGPT). When they scroll up to read,
  // we stop auto-scrolling entirely.
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      const distance = el.scrollHeight - (el.scrollTop + el.clientHeight);
      stickToBottomRef.current = distance < 64;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Auto-follow new content only when user is near the bottom.
  // We use `behavior: "auto"` (instant) during streaming so each token
  // doesn't queue a smooth-scroll animation that fights the cursor.
  useEffect(() => {
    if (!stickToBottomRef.current) return;
    messagesEndRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [messages]);

  // Auto-resize textarea. Floor by 33px (one line at 14px×1.5 + 12px
  // padding) so the textarea never collapses to 0 if scrollHeight is
  // 0 on first paint before fonts settle.
  useEffect(() => {
    if (!textareaRef.current) return;
    const el = textareaRef.current;
    el.style.height = "auto";
    const natural = el.scrollHeight || 33;
    const capped = Math.max(33, Math.min(natural, UI_CONFIG.textareaMaxHeightPx));
    el.style.height = `${capped}px`;
  }, [input]);

  // Build chatHistory from current messages for the API.
  //
  // Filters applied (each empirically tied to an upstream 422 we hit):
  //   1. Empty-content messages — rejected outright.
  //   2. Error placeholders (isError === true) — these are our own
  //      "Sorry, there was an error…" strings, not real assistant
  //      output. Repeated error placeholders in history have been
  //      observed to poison the next turn into 422.
  //   3. Legacy error placeholders without the flag — match by prefix
  //      so existing localStorage chats with poisoned history recover
  //      on next send without requiring the user to start a new chat.
  //   4. Cap at the last 10 turns (5 Q&A pairs). Unbounded history
  //      growth wastes tokens and can hit upstream limits.
  const buildChatHistory = useCallback(() => {
    const cleaned = messages.filter((m) => {
      if (m.content.trim().length === 0) return false;
      if (m.isError) return false;
      if (
        m.role === "assistant" &&
        m.content.startsWith("Sorry, there was an error:")
      ) {
        return false;
      }
      return true;
    });
    const capped = cleaned.slice(-10);
    return capped.map((m) => ({ role: m.role, content: m.content }));
  }, [messages]);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    // New message — re-stick to bottom for the assistant's reply.
    stickToBottomRef.current = true;

    // Snapshot history BEFORE adding this message (API expects prior turns)
    const chatHistory = buildChatHistory();

    const assistantId = `asst-${Date.now()}`;

    // Buffer SSE tokens and flush at most once per animation frame so we
    // re-render the markdown tree ~60×/sec instead of once per character.
    // `accumulated` keeps the full answer for the follow-up call (which
    // needs it after the flush has cleared `pending`).
    let pending = "";
    let accumulated = "";
    let flushScheduled = false;
    const flush = () => {
      flushScheduled = false;
      if (!pending) return;
      const chunk = pending;
      pending = "";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: m.content + chunk } : m
        )
      );
    };
    const scheduleFlush = () => {
      if (flushScheduled) return;
      flushScheduled = true;
      requestAnimationFrame(flush);
    };

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed, chatHistory }),
      });

      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ error: "Request failed" }));
        throw new Error(err.error ?? `HTTP ${res.status}`);
      }

      // Insert empty assistant bubble; the loading dots + status text
      // stay in place until the first chunk lands.
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          timestamp: Date.now(),
          sources: [],
        },
      ]);
      setIsLoading(false);
      streamingStartedAtRef.current = Date.now();
      setStreamingElapsed(0);
      setStreamingStatus("Searching legal cases…");
      setStreamingId(assistantId);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalSources: VaquillSource[] = [];
      let finalQuestionInterpreted: string | undefined;

      // Standard SSE parser: accumulate, split on `\n`, ignore non-data lines.
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (!trimmedLine.startsWith("data:")) continue;
          const dataStr = trimmedLine.slice(5).trim();
          if (!dataStr) continue;

          try {
            const event = JSON.parse(dataStr);
            if (event.type === "chunk" && typeof event.text === "string") {
              pending += event.text;
              accumulated += event.text;
              scheduleFlush();
            } else if (event.type === "status" && typeof event.message === "string") {
              setStreamingStatus(event.message);
            } else if (event.type === "sources" && Array.isArray(event.sources)) {
              // Sources arrive BEFORE chunks. Attach them right now so
              // the source skeleton is visible while the answer streams
              // — this is the "show your work" trust signal users
              // expect from Perplexity / NotebookLM.
              finalSources = event.sources;
              const incoming = event.sources as VaquillSource[];
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, sources: incoming } : m
                )
              );
              // Source panel stays collapsed by default; users open it
              // via the chip in the action row or by clicking a [N]
              // citation marker (which auto-expands).
            } else if (event.type === "done") {
              finalQuestionInterpreted = event.questionInterpreted;
            } else if (event.type === "error") {
              throw new Error(event.error ?? "Stream error");
            }
          } catch {
            // Malformed SSE line — skip
          }
        }
      }

      // One final synchronous flush so any tail chunk lands before we
      // finalise the message. Sources were already attached when their
      // SSE event arrived; here we just record questionInterpreted and
      // ensure sources are correct (in case the stream missed the
      // pre-stream `sources` event for any reason).
      flush();
      setStreamingId(null);

      // Kick off LLM-generated follow-ups in the background. We don't
      // await — the answer is already on screen, follow-ups can land a
      // beat later. On failure the API returns the fallback list so the
      // UI is never empty.
      const answerForFollowUps = accumulated;
      void (async () => {
        try {
          if (!answerForFollowUps.trim()) return;
          const r = await fetch("/api/follow-ups", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: trimmed, answer: answerForFollowUps }),
          });
          if (!r.ok) return;
          const data = (await r.json()) as { followUps?: string[] };
          if (!Array.isArray(data.followUps) || data.followUps.length === 0) return;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, followUps: data.followUps } : m
            )
          );
        } catch {
          // Silent — fallback list will render.
        }
      })();

      setMessages((prev) => {
        // If the stream ended without delivering any content (upstream
        // closed early — e.g. the non-legal-query path that fails server-
        // side `done` validation), drop the empty placeholder and append
        // a friendly error in its place so chatHistory never contains an
        // empty assistant message (which would 422 on the next turn).
        const hasContent = prev.some(
          (m) => m.id === assistantId && m.content.trim().length > 0
        );
        if (!hasContent) {
          return prev
            .filter((m) => m.id !== assistantId)
            .concat({
              id: `err-${Date.now()}`,
              role: "assistant",
              content:
                "I couldn't generate an answer for that. Try rephrasing as a legal-research question (e.g. about a statute, case, or doctrine).",
              timestamp: Date.now(),
              isError: true,
            });
        }
        return prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                sources: m.sources?.length ? m.sources : finalSources,
                questionInterpreted: finalQuestionInterpreted,
              }
            : m
        );
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      console.error("[ChatWidget] send error:", message);
      setStreamingId(null);
      // Drop the empty assistant placeholder (if it was inserted) so
      // chatHistory doesn't carry an empty-content message — upstream
      // rejects those with HTTP 422.
      setMessages((prev) =>
        prev
          .filter((m) => !(m.id === assistantId && m.content.trim().length === 0))
          .concat({
            id: `err-${Date.now()}`,
            role: "assistant",
            content: `Sorry, there was an error: ${message}. Please try again.`,
            timestamp: Date.now(),
            isError: true,
          })
      );
      setIsLoading(false);
    }
  }, [input, isLoading, buildChatHistory]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleExampleClick = (q: string) => {
    setInput(q);
    textareaRef.current?.focus();
  };

  const toggleSources = (msgId: string) => {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) next.delete(msgId);
      else next.add(msgId);
      return next;
    });
  };

  // Click-quote-to-jump — clicking a `[N]` marker:
  //   1. Expands the source panel for that message if collapsed.
  //   2. Updates the URL hash to the matching card so :target highlights.
  //   3. Scrolls the card into view inside the chat scroll container.
  const handleJumpToSource = useCallback(
    (msgId: string, sourceIndex: number) => {
      setExpandedSources((prev) => {
        if (prev.has(msgId)) return prev;
        const next = new Set(prev);
        next.add(msgId);
        return next;
      });
      const targetId = `src-${msgId}-${sourceIndex}`;
      // Defer one frame so the panel is in the DOM before we scroll
      // (when it was previously collapsed).
      requestAnimationFrame(() => {
        const el = document.getElementById(targetId);
        if (!el) return;
        // Update hash so :target rule kicks in for the highlight pulse.
        if (typeof history !== "undefined" && history.replaceState) {
          history.replaceState(null, "", `#${targetId}`);
        }
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    },
    []
  );

  const handleFollowUpClick = useCallback((q: string) => {
    setInput(q);
    textareaRef.current?.focus();
  }, []);

  const copyToClipboard = async (text: string, msgId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(msgId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Clipboard API unavailable
    }
  };

  // ============================================
  // Render
  // ============================================

  const isEmpty = messages.length === 0;

  return (
    <div className="chat-widget">
      {/* Header — hidden inside the floating embed (outer window has its own) */}
      {!embedded && (
        <header className="chat-header">
          <div className="chat-header-left">
            <div className="chat-header-text">
              <h1 className="chat-agent-name">{agentName}</h1>
            </div>
          </div>
          {messages.length > 0 && (
            <button
              type="button"
              className="header-action-btn"
              onClick={handleNewChat}
              title="Start a new chat"
              aria-label="Start a new chat"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.8}
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M12 5v14M5 12h14" />
              </svg>
              <span>New chat</span>
            </button>
          )}
        </header>
      )}

      {/* Messages */}
      <div
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
        ref={messagesContainerRef}
      >
        {isEmpty && (
          <div className="chat-empty">
            <p className="chat-empty-title">Ask any legal question</p>
            <p className="legal-disclaimer legal-disclaimer--banner">
              This is legal information, not legal advice. Always verify
              cited sources and consult a licensed attorney for advice on
              your specific situation.
            </p>
            {exampleQuestions.length > 0 && (
              <div className="example-questions">
                {exampleQuestions.map((q) => (
                  <button
                    key={q}
                    className="example-question-btn"
                    onClick={() => handleExampleClick(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`message message--${msg.role}`}>
            <div className={`message-bubble message-bubble--${msg.role}`}>
              {msg.role === "assistant" ? (
                msg.id === streamingId && msg.content.length === 0 ? (
                  <div className="streaming-status" aria-live="polite">
                    <span className="loading-dot" />
                    <span className="loading-dot" />
                    <span className="loading-dot" />
                    <span className="streaming-status-text">{streamingStatus}</span>
                    <span className="streaming-status-hint">
                      {streamingElapsed > 0
                        ? `${streamingElapsed}s elapsed · usually 30–60s`
                        : "usually takes 30–60s"}
                    </span>
                  </div>
                ) : (
                  <AssistantBody
                    msgId={msg.id}
                    content={msg.content}
                    sources={msg.sources}
                    onJumpToSource={handleJumpToSource}
                  />
                )
              ) : (
                <p className="message-text">{msg.content}</p>
              )}
            </div>

            {/* Assistant message actions */}
            {msg.role === "assistant" && msg.content && (() => {
              const verification = verifyCitations(msg.content, msg.sources);
              return (
                <div className="message-actions">
                  {/* Copy */}
                  <button
                    className="action-btn"
                    onClick={() => copyToClipboard(msg.content, msg.id)}
                    title="Copy response"
                    aria-label="Copy response"
                  >
                    {copiedId === msg.id ? (
                      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 00-1.414 0L8 12.586 4.707 9.293a1 1 0 00-1.414 1.414l4 4a1 1 0 001.414 0l8-8a1 1 0 000-1.414z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path d="M8 2a1 1 0 000 2h2a1 1 0 100-2H8z" />
                        <path d="M3 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v6h-4.586l1.293-1.293a1 1 0 00-1.414-1.414l-3 3a1 1 0 000 1.414l3 3a1 1 0 001.414-1.414L10.414 13H15v3a2 2 0 01-2 2H5a2 2 0 01-2-2V5z" />
                      </svg>
                    )}
                  </button>

                  {/* Citation-verified badge — green check when every
                      [N] in the answer resolves to a real source. Amber
                      when one or more citations are orphans. Hidden
                      until the stream finishes (verification needs the
                      complete answer + complete source list). */}
                  {!isLoading && verification.total > 0 && (
                    verification.allGrounded ? (
                      <span
                        className="cite-verified cite-verified--ok"
                        title={`All ${verification.total} citations resolve to a source in the database.`}
                      >
                        <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        <span>Verified · {verification.total}</span>
                      </span>
                    ) : (
                      <span
                        className="cite-verified cite-verified--warn"
                        title={`${verification.matched} of ${verification.total} citations matched a source. The rest could not be verified.`}
                      >
                        <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                          <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                        </svg>
                        <span>{verification.matched}/{verification.total} verified</span>
                      </span>
                    )
                  )}

                  {/* Sources toggle */}
                  {msg.sources && msg.sources.length > 0 && (
                    <button
                      className="action-btn sources-toggle-btn"
                      onClick={() => toggleSources(msg.id)}
                      aria-expanded={expandedSources.has(msg.id)}
                      title="Toggle sources"
                    >
                      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
                      </svg>
                      <span>{msg.sources.length}</span>
                    </button>
                  )}
                </div>
              );
            })()}

            {/* Sources panel */}
            {msg.role === "assistant" &&
              msg.sources &&
              msg.sources.length > 0 &&
              expandedSources.has(msg.id) && (
                <div className="sources-panel" role="region" aria-label="Legal sources">
                  <p className="sources-heading">
                    Sources ({msg.sources.length})
                  </p>
                  <div className="sources-list">
                    {msg.sources.map((src, idx) => (
                      <SourceCard
                        key={`${msg.id}-src-${idx}`}
                        source={src}
                        msgId={msg.id}
                      />
                    ))}
                  </div>
                </div>
              )}

            {/* Suggested follow-ups — only under the most recent
                assistant message, only when the stream is finished. */}
            {msg.role === "assistant" &&
              !isLoading &&
              msg.content &&
              msg.id === messages[messages.length - 1]?.id && (
                <div className="follow-ups" role="group" aria-label="Suggested follow-ups">
                  {(msg.followUps && msg.followUps.length > 0
                    ? msg.followUps
                    : FALLBACK_FOLLOW_UPS
                  ).map((q) => (
                    <button
                      key={q}
                      type="button"
                      className="follow-up-chip"
                      onClick={() => handleFollowUpClick(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="message message--assistant">
            <div className="message-bubble message-bubble--assistant message-bubble--loading">
              <span className="loading-dot" />
              <span className="loading-dot" />
              <span className="loading-dot" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a legal question…"
            rows={1}
            aria-label="Message input"
          />
          <div className="chat-input-actions">
            {/* Send button */}
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              aria-label="Send message"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12zm0 0h7.5" />
              </svg>
            </button>
          </div>
        </div>
        <p className="legal-disclaimer legal-disclaimer--footer">
          Information only, not legal advice. Verify all citations.
        </p>
      </div>
    </div>
  );
}
