import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Mail, Image, User, CalendarDays, MessageSquare, HardDrive, StickyNote,
  ChevronRight,
} from 'lucide-react';
import { globalSearch } from '../utils/api';
import type { GlobalSearchResult } from '../types';

export default function GlobalSearch() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const [results, setResults] = useState<GlobalSearchResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query.trim()) {
      setResults(null);
      return;
    }
    setLoading(true);
    globalSearch(query.trim())
      .then(setResults)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [query]);

  if (!query.trim()) {
    return (
      <div className="global-search-container">
        <div className="global-search-empty">Enter a search term to search across all data</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="global-search-container">
        <div className="global-search-loading">Searching everywhere...</div>
      </div>
    );
  }

  if (!results) return null;

  const totalResults =
    results.emails.total +
    results.photos.total +
    results.contacts.total +
    results.calendar.total +
    results.chat.total +
    results.drive.total +
    results.notes.total;

  return (
    <div className="global-search-container">
      <div className="global-search-header">
        <h2>Search results for "{query}"</h2>
        <span className="global-search-total">{totalResults.toLocaleString()} results</span>
      </div>

      <div className="global-search-results">
        {results.emails.total > 0 && (
          <div className="global-search-section">
            <div className="global-search-section-header">
              <Mail size={18} />
              <h3>Emails</h3>
              <span className="global-search-section-count">{results.emails.total}</span>
              <button
                className="global-search-view-all"
                onClick={() => navigate(`/search?q=${encodeURIComponent(query)}`)}
              >
                View all <ChevronRight size={14} />
              </button>
            </div>
            <div className="global-search-section-items">
              {results.emails.items.slice(0, 5).map((email) => (
                <div
                  key={email.id}
                  className="global-search-item"
                  onClick={() => navigate(`/email/${email.id}`)}
                >
                  <div className="global-search-item-title">
                    {email.subject || '(no subject)'}
                  </div>
                  <div className="global-search-item-meta">
                    {email.from_name || email.from_address} &middot;{' '}
                    {email.date && new Date(email.date).toLocaleDateString()}
                  </div>
                  {email.snippet && (
                    <div className="global-search-item-snippet">{email.snippet}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {results.photos.total > 0 && (
          <div className="global-search-section">
            <div className="global-search-section-header">
              <Image size={18} />
              <h3>Photos</h3>
              <span className="global-search-section-count">{results.photos.total}</span>
              <button
                className="global-search-view-all"
                onClick={() => navigate(`/photos/search?q=${encodeURIComponent(query)}`)}
              >
                View all <ChevronRight size={14} />
              </button>
            </div>
            <div className="global-search-section-items">
              {results.photos.items.slice(0, 5).map((photo) => (
                <div key={photo.id} className="global-search-item">
                  <div className="global-search-item-title">{photo.title || photo.filename}</div>
                  <div className="global-search-item-meta">
                    {photo.date_taken && new Date(photo.date_taken).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {results.contacts.total > 0 && (
          <div className="global-search-section">
            <div className="global-search-section-header">
              <User size={18} />
              <h3>Contacts</h3>
              <span className="global-search-section-count">{results.contacts.total}</span>
              <button
                className="global-search-view-all"
                onClick={() => navigate('/contacts')}
              >
                View all <ChevronRight size={14} />
              </button>
            </div>
            <div className="global-search-section-items">
              {results.contacts.items.slice(0, 5).map((contact) => (
                <div
                  key={contact.id}
                  className="global-search-item"
                  onClick={() => navigate(`/contacts/${contact.id}`)}
                >
                  <div className="global-search-item-title">{contact.name}</div>
                  <div className="global-search-item-meta">
                    {contact.emails.length > 0 ? contact.emails[0] : ''}
                    {contact.organization ? ` - ${contact.organization}` : ''}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {results.calendar.total > 0 && (
          <div className="global-search-section">
            <div className="global-search-section-header">
              <CalendarDays size={18} />
              <h3>Calendar Events</h3>
              <span className="global-search-section-count">{results.calendar.total}</span>
              <button
                className="global-search-view-all"
                onClick={() => navigate('/calendar')}
              >
                View all <ChevronRight size={14} />
              </button>
            </div>
            <div className="global-search-section-items">
              {results.calendar.items.slice(0, 5).map((evt) => (
                <div key={evt.id} className="global-search-item">
                  <div className="global-search-item-title">{evt.summary}</div>
                  <div className="global-search-item-meta">
                    {new Date(evt.start_time).toLocaleDateString()} &middot;{' '}
                    {evt.calendar_name}
                    {evt.location ? ` - ${evt.location}` : ''}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {results.chat.total > 0 && (
          <div className="global-search-section">
            <div className="global-search-section-header">
              <MessageSquare size={18} />
              <h3>Chat</h3>
              <span className="global-search-section-count">{results.chat.total}</span>
              <button
                className="global-search-view-all"
                onClick={() => navigate('/chat')}
              >
                View all <ChevronRight size={14} />
              </button>
            </div>
            <div className="global-search-section-items">
              {results.chat.items.slice(0, 5).map((convo) => (
                <div
                  key={convo.id}
                  className="global-search-item"
                  onClick={() => navigate(`/chat/${convo.id}`)}
                >
                  <div className="global-search-item-title">{convo.name}</div>
                  <div className="global-search-item-meta">
                    {convo.message_count} messages &middot;{' '}
                    {convo.participants.slice(0, 3).join(', ')}
                  </div>
                  {convo.last_message_preview && (
                    <div className="global-search-item-snippet">
                      {convo.last_message_preview}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {results.drive.total > 0 && (
          <div className="global-search-section">
            <div className="global-search-section-header">
              <HardDrive size={18} />
              <h3>Drive Files</h3>
              <span className="global-search-section-count">{results.drive.total}</span>
              <button
                className="global-search-view-all"
                onClick={() => navigate('/drive')}
              >
                View all <ChevronRight size={14} />
              </button>
            </div>
            <div className="global-search-section-items">
              {results.drive.items.slice(0, 5).map((file) => (
                <div key={file.id} className="global-search-item">
                  <div className="global-search-item-title">{file.filename}</div>
                  <div className="global-search-item-meta">
                    {file.path}
                    {file.modified_time
                      ? ` - ${new Date(file.modified_time).toLocaleDateString()}`
                      : ''}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {results.notes.total > 0 && (
          <div className="global-search-section">
            <div className="global-search-section-header">
              <StickyNote size={18} />
              <h3>Notes</h3>
              <span className="global-search-section-count">{results.notes.total}</span>
              <button
                className="global-search-view-all"
                onClick={() => navigate('/notes')}
              >
                View all <ChevronRight size={14} />
              </button>
            </div>
            <div className="global-search-section-items">
              {results.notes.items.slice(0, 5).map((note) => (
                <div
                  key={note.id}
                  className="global-search-item"
                  onClick={() => navigate(`/notes/${note.id}`)}
                >
                  <div className="global-search-item-title">
                    {note.title || 'Untitled'}
                  </div>
                  {note.content && (
                    <div className="global-search-item-snippet">
                      {note.content.length > 100
                        ? note.content.slice(0, 100) + '...'
                        : note.content}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {totalResults === 0 && (
          <div className="global-search-empty">
            No results found for "{query}"
          </div>
        )}
      </div>
    </div>
  );
}
