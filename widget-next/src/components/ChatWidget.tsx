"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import type { VaquillSource, VaquillMode } from "@/lib/vaquill";
import { useTTS } from "@/hooks/useTTS";
import { UI_CONFIG, VAQUILL_CONFIG } from "@/config/constants";

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
  mode?: VaquillMode;
}

interface ChatWidgetProps {
  /** Override the display name shown in the header */
  agentName?: string;
  /** Chat mode: standard (default) or deep */
  defaultMode?: VaquillMode;
  /** Initial placeholder questions shown before first message */
  exampleQuestions?: string[];
  /** Whether TTS playback button is enabled */
  ttsEnabled?: boolean;
  /** Whether microphone (STT) button is enabled */
  sttEnabled?: boolean;
}

// ============================================
// Source card
// ============================================

function SourceCard({ source }: { source: VaquillSource }) {
  return (
    <div className="source-card">
      <div className="source-card-header">
        <span className="source-case-name">{source.caseName}</span>
        {source.relevanceScore > 0 && (
          <span className="source-relevance">
            {Math.round(source.relevanceScore * 100)}%
          </span>
        )}
      </div>
      <div className="source-meta">
        <span className="source-citation">{source.citation}</span>
        <span className="source-separator">·</span>
        <span className="source-court">{source.court}</span>
      </div>
      {source.excerpt && (
        <p className="source-excerpt">&ldquo;{source.excerpt}&rdquo;</p>
      )}
      {source.pdfUrl && (
        <a
          href={source.pdfUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="source-pdf-link"
        >
          View judgment PDF
        </a>
      )}
    </div>
  );
}

// ============================================
// ChatWidget
// ============================================

export default function ChatWidget({
  agentName = UI_CONFIG.agentName,
  defaultMode = VAQUILL_CONFIG.defaultMode,
  exampleQuestions = [],
  ttsEnabled = false,
  sttEnabled = false,
}: ChatWidgetProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState<VaquillMode>(defaultMode);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const { status: ttsStatus, play: playTTS, stop: stopTTS, currentMessageId: ttsMsgId } = useTTS();

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const capped = Math.min(
        textareaRef.current.scrollHeight,
        UI_CONFIG.textareaMaxHeightPx
      );
      textareaRef.current.style.height = `${capped}px`;
    }
  }, [input]);

  // Build chatHistory from current messages for the API
  const buildChatHistory = useCallback(
    () =>
      messages.map((m) => ({
        role: m.role,
        content: m.content,
      })),
    [messages]
  );

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

    // Snapshot history BEFORE adding this message (API expects prior turns)
    const chatHistory = buildChatHistory();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          mode,
          chatHistory,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Request failed" }));
        throw new Error(err.error ?? `HTTP ${res.status}`);
      }

      const data = await res.json();

      // Create assistant message with empty content first
      const assistantId = `asst-${Date.now()}`;
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        sources: data.sources ?? [],
        questionInterpreted: data.questionInterpreted,
        mode: data.mode,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setIsLoading(false);

      // Word-by-word animation
      const words = (data.answer as string).split(" ");
      let accumulated = "";

      for (let i = 0; i < words.length; i++) {
        accumulated += (i === 0 ? "" : " ") + words[i];
        const snapshot = accumulated;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: snapshot } : m
          )
        );
        await new Promise((resolve) =>
          setTimeout(resolve, UI_CONFIG.wordAnimationDelayMs)
        );
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      console.error("[ChatWidget] send error:", message);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: `Sorry, there was an error: ${message}. Please try again.`,
          timestamp: Date.now(),
        },
      ]);
      setIsLoading(false);
    }
  }, [input, isLoading, mode, buildChatHistory]);

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

  const copyToClipboard = async (text: string, msgId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(msgId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Clipboard API unavailable
    }
  };

  // STT: start recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        await transcribeAudio(blob);
      };

      recorder.start();
      setIsRecording(true);
    } catch {
      alert("Could not access microphone. Please check browser permissions.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const transcribeAudio = async (blob: Blob) => {
    setIsTranscribing(true);
    try {
      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      const res = await fetch("/api/chat/transcribe", { method: "POST", body: form });
      if (!res.ok) throw new Error("Transcription request failed");
      const data = await res.json();
      setInput(data.transcript ?? "");
    } catch (err) {
      console.error("[STT]", err);
      alert("Failed to transcribe audio. Please try again.");
    } finally {
      setIsTranscribing(false);
    }
  };

  // ============================================
  // Render
  // ============================================

  const isEmpty = messages.length === 0;

  return (
    <div className="chat-widget">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="chat-avatar" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364-.707.707M6.343 17.657l-.707.707m12.728 0-.707-.707M6.343 6.343l-.707-.707M12 7a5 5 0 1 1 0 10A5 5 0 0 1 12 7z" />
            </svg>
          </div>
          <div>
            <h1 className="chat-agent-name">{agentName}</h1>
            <span className="chat-status-dot" aria-label="Online" />
          </div>
        </div>
        <div className="chat-header-right">
          {/* Mode toggle */}
          <div className="mode-toggle" role="group" aria-label="Query mode">
            <button
              className={`mode-btn${mode === "standard" ? " mode-btn--active" : ""}`}
              onClick={() => setMode("standard")}
              title="Standard mode — fast, 18 RAG techniques"
            >
              Standard
            </button>
            <button
              className={`mode-btn${mode === "deep" ? " mode-btn--active" : ""}`}
              onClick={() => setMode("deep")}
              title="Deep mode — 35 techniques, hallucination detection"
            >
              Deep
            </button>
          </div>
        </div>
      </header>

      {/* Messages */}
      <div className="chat-messages" role="log" aria-live="polite" aria-label="Chat messages">
        {isEmpty && (
          <div className="chat-empty">
            <p className="chat-empty-title">Ask any legal question</p>
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
                <div className="message-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="message-text">{msg.content}</p>
              )}
            </div>

            {/* Assistant message actions */}
            {msg.role === "assistant" && msg.content && (
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

                {/* TTS */}
                {ttsEnabled && (
                  <button
                    className="action-btn"
                    onClick={() =>
                      ttsMsgId === msg.id
                        ? stopTTS()
                        : playTTS(msg.content, msg.id)
                    }
                    title={ttsMsgId === msg.id ? "Stop playback" : "Read aloud"}
                    aria-label={ttsMsgId === msg.id ? "Stop playback" : "Read aloud"}
                  >
                    {ttsMsgId === msg.id && ttsStatus === "playing" ? (
                      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 002 0V8a1 1 0 00-1-1zm4 0a1 1 0 00-1 1v4a1 1 0 002 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.707.707L4.586 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.586l3.707-3.707a1 1 0 011.09-.217zM14.657 2.929a1 1 0 011.414 0A9.972 9.972 0 0119 10a9.972 9.972 0 01-2.929 7.071 1 1 0 01-1.414-1.414A7.971 7.971 0 0017 10c0-2.21-.894-4.208-2.343-5.657a1 1 0 010-1.414zm-2.829 2.828a1 1 0 011.415 0A5.983 5.983 0 0115 10a5.984 5.984 0 01-1.757 4.243 1 1 0 01-1.415-1.415A3.984 3.984 0 0013 10a3.983 3.983 0 00-1.172-2.828 1 1 0 010-1.415z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
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
            )}

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
                      <SourceCard key={`${msg.id}-src-${idx}`} source={src} />
                    ))}
                  </div>
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
            disabled={isLoading}
            aria-label="Message input"
          />
          <div className="chat-input-actions">
            {/* STT mic button */}
            {sttEnabled && (
              <button
                className={`input-action-btn${isRecording ? " input-action-btn--recording" : ""}`}
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isTranscribing || isLoading}
                title={isRecording ? "Stop recording" : "Start voice input"}
                aria-label={isRecording ? "Stop recording" : "Start voice input"}
              >
                {isTranscribing ? (
                  <svg className="animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                    <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                    <path d="M12 2a10 10 0 0 1 10 10" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3z" />
                  </svg>
                )}
              </button>
            )}

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
        <p className="chat-disclaimer">
          Vaquill may make mistakes. Always verify with primary sources.
        </p>
      </div>
    </div>
  );
}
