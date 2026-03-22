import { useEffect, useState, useRef, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Search, X, MessageSquare, ArrowLeft } from 'lucide-react';
import { fetchConversations, fetchConversation, searchChat } from '../utils/api';
import type { ChatConversation, ChatMessage, ChatParticipant } from '../types';

function formatTimestamp(ts: string | null): string {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const diffDays = Math.floor(
    (now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24)
  );
  if (diffDays === 0) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  if (diffDays < 7) return d.toLocaleDateString([], { weekday: 'short' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function formatFullTime(ts: string): string {
  return new Date(ts).toLocaleString([], {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  });
}

// Detect the archive owner by finding the most frequent sender in loaded messages
function detectOwner(
  messages: ChatMessage[],
  participants: ChatParticipant[]
): ChatParticipant | null {
  if (participants.length === 0) return null;
  if (participants.length === 1) return participants[0];

  // Count messages per sender
  const counts: Record<string, number> = {};
  for (const msg of messages) {
    const key = msg.sender_name || msg.sender_email || '';
    counts[key] = (counts[key] || 0) + 1;
  }

  // Find the participant who sent the most messages (likely the archive owner)
  let best: ChatParticipant | null = participants[0]; // default to first (owner in Google exports)
  let bestCount = 0;
  for (const p of participants) {
    const c = (counts[p.name] || 0) + (counts[p.email] || 0);
    if (c > bestCount) {
      bestCount = c;
      best = p;
    }
  }

  return best;
}

export default function ChatView() {
  const navigate = useNavigate();
  const { conversationId } = useParams<{ conversationId: string }>();
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ChatMessage[] | null>(null);

  const [activeConvo, setActiveConvo] = useState<ChatConversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    fetchConversations({ limit: 200 })
      .then((res) => setConversations(res.conversations))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (conversationId) {
      setMessagesLoading(true);
      fetchConversation(Number(conversationId), 0, 500)
        .then((res) => {
          setActiveConvo(res.conversation);
          setMessages(res.messages);
        })
        .catch(console.error)
        .finally(() => setMessagesLoading(false));
    } else {
      setActiveConvo(null);
      setMessages([]);
    }
  }, [conversationId]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'auto' });
    }
  }, [messages]);

  function handleSearch() {
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }
    searchChat(query.trim(), 0, 100)
      .then((res) => setSearchResults(res.messages))
      .catch(console.error);
  }

  function clearSearch() {
    setQuery('');
    setSearchResults(null);
  }

  // Detect which participant is "me" (the archive owner)
  const owner = useMemo(
    () => activeConvo ? detectOwner(messages, activeConvo.participants) : null,
    [activeConvo, messages]
  );

  function isMine(msg: ChatMessage): boolean {
    if (!owner) return false;
    return (
      (!!owner.name && msg.sender_name === owner.name) ||
      (!!owner.email && msg.sender_email === owner.email)
    );
  }

  return (
    <div className="chat-container">
      <div className="chat-sidebar">
        <div className="chat-sidebar-header">
          <h2>Chat</h2>
        </div>
        <div className="chat-search-bar">
          <Search size={14} />
          <input
            type="text"
            placeholder="Search messages..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="chat-search-input"
          />
          {query && (
            <button className="search-clear" onClick={clearSearch}>
              <X size={14} />
            </button>
          )}
        </div>

        <div className="chat-conversation-list">
          {searchResults !== null ? (
            searchResults.length === 0 ? (
              <div className="chat-empty">No results</div>
            ) : (
              searchResults.map((msg) => (
                <button
                  key={msg.id}
                  className="chat-convo-item"
                  onClick={() => {
                    clearSearch();
                    navigate(`/chat/${msg.conversation_id}`);
                  }}
                >
                  <div className="chat-convo-name">{msg.sender_name}</div>
                  <div className="chat-convo-preview">{msg.content}</div>
                  <div className="chat-convo-time">{formatTimestamp(msg.timestamp)}</div>
                </button>
              ))
            )
          ) : loading ? (
            <div className="chat-empty">Loading conversations...</div>
          ) : conversations.length === 0 ? (
            <div className="chat-empty">No conversations</div>
          ) : (
            conversations.map((convo) => {
              const displayName = convo.participants.length > 0
                ? convo.participants.map(p => p.name).filter(Boolean).join(', ')
                : convo.name;
              const preview = convo.last_message
                ? convo.last_message.content
                : convo.last_message_preview || `${convo.message_count || 0} messages`;
              const time = convo.last_message
                ? convo.last_message.timestamp
                : convo.last_message_time || null;
              return (
                <button
                  key={convo.id}
                  className={`chat-convo-item ${conversationId && Number(conversationId) === convo.id ? 'active' : ''}`}
                  onClick={() => navigate(`/chat/${convo.id}`)}
                >
                  <div className="chat-convo-icon">
                    <MessageSquare size={16} />
                  </div>
                  <div className="chat-convo-info">
                    <div className="chat-convo-name">{displayName || convo.name}</div>
                    <div className="chat-convo-preview">
                      {preview?.slice(0, 80)}
                    </div>
                  </div>
                  <div className="chat-convo-meta">
                    <div className="chat-convo-time">
                      {time ? formatTimestamp(time) : ''}
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="chat-main">
        {!conversationId ? (
          <div className="chat-placeholder">
            <MessageSquare size={48} />
            <p>Select a conversation to view messages</p>
          </div>
        ) : messagesLoading ? (
          <div className="chat-placeholder">Loading messages...</div>
        ) : (
          <>
            <div className="chat-main-header">
              <button className="chat-back-btn" onClick={() => navigate('/chat')}>
                <ArrowLeft size={16} />
              </button>
              <div className="chat-main-title">
                <h3>{activeConvo?.name}</h3>
                {activeConvo && (
                  <span className="chat-main-participants">
                    {activeConvo.participants.map(p => p.name || p.email).join(', ')}
                  </span>
                )}
              </div>
            </div>
            <div className="chat-messages">
              {messages.map((msg) => {
                const mine = isMine(msg);
                return (
                  <div
                    key={msg.id}
                    className={`chat-bubble-row ${mine ? 'mine' : 'theirs'}`}
                  >
                    {!mine && (
                      <div className="chat-bubble-sender">{msg.sender_name}</div>
                    )}
                    <div className={`chat-bubble ${mine ? 'mine' : 'theirs'}`}>
                      <div className="chat-bubble-content">{msg.content}</div>
                      <div className="chat-bubble-time">
                        {formatFullTime(msg.timestamp)}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
