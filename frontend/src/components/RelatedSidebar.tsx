import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  Mail,
  Image,
  Calendar,
  Users,
  MessageSquare,
  HardDrive,
} from 'lucide-react';
import { fetchRelated, getPhotoThumbnailUrl } from '../utils/api';
import type {
  RelatedResponse,
  RelatedEmail,
  RelatedPhoto,
  RelatedEvent,
  RelatedContact,
  RelatedChat,
  RelatedDrive,
} from '../types';

interface RelatedSidebarProps {
  type: string;
  id: number;
}

function formatShortDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function truncate(text: string | null, maxLen: number): string {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
}

export default function RelatedSidebar({ type, id }: RelatedSidebarProps) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<RelatedResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    fetchRelated(type, id)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [type, id, open]);

  const related = data?.related;
  const hasResults =
    related &&
    (related.emails.length > 0 ||
      related.photos.length > 0 ||
      related.events.length > 0 ||
      related.contacts.length > 0 ||
      related.chats.length > 0 ||
      related.drive.length > 0);

  return (
    <>
      <button
        className="related-sidebar-toggle"
        onClick={() => setOpen((v) => !v)}
        title={open ? 'Hide related items' : 'Show related items'}
      >
        {open ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
      <div className={`related-sidebar ${open ? 'related-sidebar--open' : ''}`}>
        <div className="related-sidebar-header">
          <h3>Related Items</h3>
        </div>
        <div className="related-sidebar-body">
          {loading && <div className="related-sidebar-loading">Loading...</div>}
          {error && <div className="related-sidebar-error">{error}</div>}
          {!loading && !error && !hasResults && (
            <div className="related-sidebar-empty">No related items found</div>
          )}
          {!loading && !error && related && (
            <>
              {related.emails.length > 0 && (
                <RelatedSection
                  title="Emails"
                  icon={<Mail size={14} />}
                  count={related.emails.length}
                >
                  {related.emails.map((item: RelatedEmail) => (
                    <button
                      key={item.id}
                      className="related-item"
                      onClick={() => navigate(`/email/${item.id}`)}
                    >
                      <div className="related-item-primary">
                        {truncate(item.from_name || 'Unknown', 30)}
                      </div>
                      <div className="related-item-secondary">
                        {truncate(item.subject, 50)}
                      </div>
                      <div className="related-item-date">
                        {formatShortDate(item.date)}
                      </div>
                    </button>
                  ))}
                </RelatedSection>
              )}

              {related.photos.length > 0 && (
                <RelatedSection
                  title="Photos"
                  icon={<Image size={14} />}
                  count={related.photos.length}
                >
                  <div className="related-photos-grid">
                    {related.photos.map((item: RelatedPhoto) => (
                      <button
                        key={item.id}
                        className="related-photo-thumb"
                        onClick={() => navigate(`/photos?photo=${item.id}`)}
                        title={item.filename || undefined}
                      >
                        <img
                          src={getPhotoThumbnailUrl(item.id)}
                          alt={item.filename || 'Photo'}
                          loading="lazy"
                        />
                      </button>
                    ))}
                  </div>
                </RelatedSection>
              )}

              {related.events.length > 0 && (
                <RelatedSection
                  title="Events"
                  icon={<Calendar size={14} />}
                  count={related.events.length}
                >
                  {related.events.map((item: RelatedEvent) => (
                    <button
                      key={item.id}
                      className="related-item"
                      onClick={() => navigate('/calendar')}
                    >
                      <div className="related-item-primary">
                        {truncate(item.summary, 40)}
                      </div>
                      <div className="related-item-date">
                        {formatShortDate(item.start_time)}
                        {item.location ? ` \u00b7 ${truncate(item.location, 25)}` : ''}
                      </div>
                    </button>
                  ))}
                </RelatedSection>
              )}

              {related.contacts.length > 0 && (
                <RelatedSection
                  title="Contacts"
                  icon={<Users size={14} />}
                  count={related.contacts.length}
                >
                  {related.contacts.map((item: RelatedContact) => (
                    <button
                      key={item.id}
                      className="related-item"
                      onClick={() => navigate(`/contacts`)}
                    >
                      <div className="related-item-primary">
                        {item.name || 'Unknown'}
                      </div>
                      {item.emails.length > 0 && (
                        <div className="related-item-secondary">
                          {item.emails[0]?.address || ''}
                        </div>
                      )}
                    </button>
                  ))}
                </RelatedSection>
              )}

              {related.chats.length > 0 && (
                <RelatedSection
                  title="Chats"
                  icon={<MessageSquare size={14} />}
                  count={related.chats.length}
                >
                  {related.chats.map((item: RelatedChat) => (
                    <button
                      key={item.id}
                      className="related-item"
                      onClick={() => navigate(`/chat/${item.conversation_id}`)}
                    >
                      <div className="related-item-primary">
                        {item.sender_name || 'Unknown'}
                      </div>
                      <div className="related-item-secondary">
                        {truncate(item.content, 60)}
                      </div>
                      <div className="related-item-date">
                        {formatShortDate(item.timestamp)}
                      </div>
                    </button>
                  ))}
                </RelatedSection>
              )}

              {related.drive.length > 0 && (
                <RelatedSection
                  title="Drive"
                  icon={<HardDrive size={14} />}
                  count={related.drive.length}
                >
                  {related.drive.map((item: RelatedDrive) => (
                    <button
                      key={item.id}
                      className="related-item"
                      onClick={() => navigate('/drive')}
                    >
                      <div className="related-item-primary">
                        {item.filename || 'Untitled'}
                      </div>
                      {item.mime_type && (
                        <div className="related-item-secondary">
                          {item.mime_type}
                        </div>
                      )}
                    </button>
                  ))}
                </RelatedSection>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}

function RelatedSection({
  title,
  icon,
  count,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="related-section">
      <div className="related-section-header">
        {icon}
        <span className="related-section-title">{title}</span>
        <span className="related-section-count">{count}</span>
      </div>
      <div className="related-section-items">{children}</div>
    </div>
  );
}
