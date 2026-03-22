import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send,
  Bot,
  User,
  Mail,
  Image,
  CalendarDays,
  MessageSquare,
  HardDrive,
  Loader2,
  Sparkles,
  X,
  ExternalLink,
} from 'lucide-react';
import { fetchAIStatus, fetchAISuggestions, sendAIMessage } from '../utils/api';
import type { AIChatMessage, AIChatStatus, AISource } from '../types';

const SCOPE_OPTIONS = [
  { key: 'email', label: 'Email', icon: Mail },
  { key: 'photo', label: 'Photos', icon: Image },
  { key: 'calendar', label: 'Calendar', icon: CalendarDays },
  { key: 'chat', label: 'Chat', icon: MessageSquare },
  { key: 'drive', label: 'Drive', icon: HardDrive },
] as const;

const TYPE_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  photo: Image,
  calendar: CalendarDays,
  chat: MessageSquare,
  drive: HardDrive,
  contact: User,
};

function getSourcePath(source: AISource): string | null {
  const id = source.id;
  switch (source.type) {
    case 'email':
      return `/email/${id}`;
    case 'photo':
      return `/photos`;
    case 'calendar':
      return `/calendar`;
    case 'chat':
      return `/chat`;
    case 'drive':
      return `/drive`;
    case 'contact':
      return `/contacts`;
    default:
      return null;
  }
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export default function AIChat() {
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<AIChatStatus | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [enabledScopes, setEnabledScopes] = useState<Set<string>>(
    new Set(SCOPE_OPTIONS.map((s) => s.key))
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch status and suggestions on mount
  useEffect(() => {
    fetchAIStatus()
      .then(setStatus)
      .catch(() => setStatus(null));

    fetchAISuggestions()
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, []);

  const handleSend = useCallback(
    async (messageText?: string) => {
      const text = (messageText || input).trim();
      if (!text || isLoading) return;

      setInput('');

      const userMsg: AIChatMessage = {
        id: generateId(),
        role: 'user',
        content: text,
      };

      const assistantMsg: AIChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: '',
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsLoading(true);

      // Build conversation history from previous messages (exclude current)
      const history = messages
        .filter((m) => !m.isStreaming && !m.error)
        .map((m) => ({ role: m.role, content: m.content }));

      const scope = enabledScopes.size === SCOPE_OPTIONS.length ? null : Array.from(enabledScopes);

      const controller = new AbortController();
      abortRef.current = controller;

      await sendAIMessage(
        text,
        history,
        scope,
        {
          onToken: (token) => {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === 'assistant' && last.isStreaming) {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + token,
                };
              }
              return updated;
            });
          },
          onDone: (sources) => {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  isStreaming: false,
                  sources: sources.length > 0 ? sources : undefined,
                };
              }
              return updated;
            });
            setIsLoading(false);
          },
          onError: (error) => {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  isStreaming: false,
                  content: '',
                  error,
                };
              }
              return updated;
            });
            setIsLoading(false);
          },
        },
        controller.signal,
      );

      abortRef.current = null;
    },
    [input, isLoading, messages, enabledScopes],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleScope = (key: string) => {
    setEnabledScopes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        // Don't allow deselecting all
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const clearChat = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setMessages([]);
    setIsLoading(false);
  };

  const isOnline = status?.ollama_available ?? false;

  return (
    <div className="ai-chat-container">
      {/* Header */}
      <div className="ai-chat-header">
        <div className="ai-chat-header-left">
          <Sparkles size={20} />
          <h2>AI Chat</h2>
          <span className={`ai-status-dot ${isOnline ? 'online' : 'offline'}`} />
          <span className="ai-status-text">
            {status === null
              ? 'Checking...'
              : isOnline
                ? `Ollama connected${status.embedded_count > 0 ? ` \u00b7 ${status.embedded_count.toLocaleString()} docs` : ''}`
                : 'Ollama offline'}
          </span>
        </div>
        {messages.length > 0 && (
          <button className="ai-clear-btn" onClick={clearChat} title="Clear conversation">
            <X size={16} />
            Clear
          </button>
        )}
      </div>

      {/* Scope selector */}
      <div className="ai-scope-bar">
        <span className="ai-scope-label">Search in:</span>
        {SCOPE_OPTIONS.map((opt) => {
          const Icon = opt.icon;
          const active = enabledScopes.has(opt.key);
          return (
            <button
              key={opt.key}
              className={`ai-scope-chip ${active ? 'active' : ''}`}
              onClick={() => toggleScope(opt.key)}
            >
              <Icon size={14} />
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Message area */}
      <div className="ai-chat-messages">
        {messages.length === 0 ? (
          <div className="ai-chat-empty">
            <Bot size={48} className="ai-empty-icon" />
            <h3>Ask me anything about your archive</h3>
            <p>
              I can search through your emails, photos, calendar events, chat messages, and drive
              files to help you find information.
            </p>

            {suggestions.length > 0 && (
              <div className="ai-suggestions">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    className="ai-suggestion-chip"
                    onClick={() => handleSend(s)}
                  >
                    <Sparkles size={14} />
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`ai-message ${msg.role === 'user' ? 'ai-message-user' : 'ai-message-assistant'}`}
              >
                <div className="ai-message-avatar">
                  {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                </div>
                <div className="ai-message-content">
                  {msg.error ? (
                    <div className="ai-message-error">{msg.error}</div>
                  ) : (
                    <>
                      <div className="ai-message-text">
                        {msg.content}
                        {msg.isStreaming && <span className="ai-cursor" />}
                      </div>
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="ai-sources">
                          <div className="ai-sources-label">Sources</div>
                          <div className="ai-sources-list">
                            {msg.sources.map((source, idx) => {
                              const Icon = TYPE_ICONS[source.type] || Mail;
                              const path = getSourcePath(source);
                              return (
                                <a
                                  key={idx}
                                  className="ai-source-card"
                                  href={path || '#'}
                                  onClick={(e) => {
                                    if (!path) e.preventDefault();
                                  }}
                                >
                                  <Icon size={14} className="ai-source-icon" />
                                  <div className="ai-source-info">
                                    <span className="ai-source-title">{source.title}</span>
                                    {source.date && (
                                      <span className="ai-source-date">{source.date}</span>
                                    )}
                                  </div>
                                  {path && <ExternalLink size={12} className="ai-source-link" />}
                                </a>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
            {isLoading && messages[messages.length - 1]?.content === '' && !messages[messages.length - 1]?.error && (
              <div className="ai-thinking">
                <Loader2 size={16} className="ai-spinner" />
                Thinking...
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="ai-chat-input-area">
        <div className="ai-chat-input-wrapper">
          <textarea
            ref={inputRef}
            className="ai-chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isOnline
                ? 'Ask about your archive...'
                : 'Ollama is offline. Start Ollama to chat.'
            }
            disabled={!isOnline}
            rows={1}
          />
          <button
            className="ai-send-btn"
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading || !isOnline}
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
