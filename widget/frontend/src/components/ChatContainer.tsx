import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import type { Message, Source, WidgetInfo, ChatHistoryItem } from '../types';
import { sendChatMessage } from '../utils/api';
import { preprocessMarkdown } from '../utils/markdownPreprocessor';
import './ChatContainer.css';

interface ChatContainerProps {
  widgetInfo: WidgetInfo;
}

const MAX_HISTORY_TURNS = 10;

const ChatContainer = ({ widgetInfo }: ChatContainerProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Build chat history from current messages (exclude error messages)
  const buildChatHistory = (): ChatHistoryItem[] => {
    const validMessages = messages.filter(
      (m) => !m.id.startsWith('error-') && m.content.trim(),
    );
    // Keep last N turns (each turn = 1 user + 1 assistant)
    const sliced = validMessages.slice(-MAX_HISTORY_TURNS * 2);
    return sliced.map((m) => ({ role: m.role, content: m.content }));
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
      id: `user-${Date.now()}`,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const history = buildChatHistory();

    try {
      const data = await sendChatMessage(trimmed, history, widgetInfo.mode);
      const processedAnswer = preprocessMarkdown(data.answer);
      const assistantId = `assistant-${Date.now()}`;

      // Add message with empty content, then animate word-by-word
      const assistantMessage: Message = {
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        id: assistantId,
        sources: data.sources,
        questionInterpreted: data.questionInterpreted,
        mode: data.mode,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);

      // Word-by-word animation
      const words = processedAnswer.split(' ');
      let currentText = '';

      for (let i = 0; i < words.length; i++) {
        currentText += (i === 0 ? '' : ' ') + words[i];
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId ? { ...msg, content: currentText } : msg,
          ),
        );
        await new Promise<void>((resolve) => setTimeout(resolve, 25));
      }
    } catch (err) {
      console.error('Chat error:', err);
      const errorText =
        err instanceof Error ? err.message : 'An unexpected error occurred.';
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: errorText,
          timestamp: Date.now(),
          id: `error-${Date.now()}`,
        },
      ]);
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopy = async (messageId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(messageId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // clipboard not available
    }
  };

  const toggleSources = (messageId: string) => {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) next.delete(messageId);
      else next.add(messageId);
      return next;
    });
  };

  const handleSuggestedQuestion = (question: string) => {
    setInput(question);
    textareaRef.current?.focus();
  };

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-logo">
          <span className="chat-header-logo-text">{widgetInfo.branding.logoText}</span>
        </div>
        <h1 className="chat-header-title">{widgetInfo.title}</h1>
      </div>

      {/* Messages */}
      <div className="chat-messages" role="log" aria-live="polite" aria-label="Chat messages">
        {messages.length === 0 && (
          <div className="chat-empty-state">
            <p className="chat-empty-state-hint">Ask any legal question to get started</p>
            {widgetInfo.suggestedQuestions.length > 0 && (
              <div className="chat-suggestions">
                {widgetInfo.suggestedQuestions.map((q, i) => (
                  <button
                    key={i}
                    className="chat-suggestion-btn"
                    onClick={() => handleSuggestedQuestion(q)}
                    type="button"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`chat-message chat-message--${message.role}`}
          >
            <div className="chat-message-bubble">
              {message.role === 'assistant' ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  className="chat-markdown"
                >
                  {message.content}
                </ReactMarkdown>
              ) : (
                <p className="chat-message-text">{message.content}</p>
              )}

              {/* Sources */}
              {message.role === 'assistant' &&
                message.sources &&
                message.sources.length > 0 && (
                  <div className="chat-sources">
                    <button
                      className="chat-sources-toggle"
                      onClick={() => toggleSources(message.id)}
                      type="button"
                      aria-expanded={expandedSources.has(message.id)}
                    >
                      {expandedSources.has(message.id) ? 'Hide' : 'Show'}{' '}
                      {message.sources.length} source
                      {message.sources.length !== 1 ? 's' : ''}
                    </button>

                    {expandedSources.has(message.id) && (
                      <div className="chat-sources-list">
                        {message.sources.map((source, idx) => (
                          <SourceCard key={idx} source={source} index={idx + 1} />
                        ))}
                      </div>
                    )}
                  </div>
                )}

              {/* Copy button for assistant messages */}
              {message.role === 'assistant' && message.content && (
                <button
                  className="chat-copy-btn"
                  onClick={() => handleCopy(message.id, message.content)}
                  type="button"
                  title="Copy answer"
                  aria-label="Copy answer to clipboard"
                >
                  {copiedId === message.id ? 'Copied' : 'Copy'}
                </button>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="chat-message chat-message--assistant">
            <div className="chat-message-bubble chat-loading-bubble">
              <span className="chat-loading-dot" />
              <span className="chat-loading-dot" />
              <span className="chat-loading-dot" />
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
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a legal question..."
            rows={1}
            aria-label="Message input"
            disabled={isLoading}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            type="button"
            aria-label="Send message"
          >
            <SendIcon />
          </button>
        </div>
        <p className="chat-disclaimer">
          Vaquill provides legal information, not legal advice. Consult a qualified
          lawyer for specific matters.
        </p>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const SourceCard = ({ source, index }: { source: Source; index: number }) => (
  <div className="source-card">
    <div className="source-card-header">
      <span className="source-card-index">{index}</span>
      <span className="source-card-name">
        {source.caseName || 'Legal Source'}
      </span>
    </div>

    {source.citation && (
      <p className="source-card-citation">{source.citation}</p>
    )}
    {source.court && (
      <p className="source-card-court">{source.court}</p>
    )}
    {source.excerpt && (
      <p className="source-card-excerpt">{source.excerpt}</p>
    )}

    <div className="source-card-footer">
      {source.relevanceScore != null && (
        <span className="source-card-score">
          {Math.round(source.relevanceScore * 100)}% match
        </span>
      )}
      {source.pdfUrl && (
        <a
          href={source.pdfUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="source-card-pdf-link"
        >
          View PDF
        </a>
      )}
    </div>
  </div>
);

const SendIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

export default ChatContainer;
