import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Paperclip,
  Download,
  Eye,
} from 'lucide-react';
import { fetchThread, getAttachmentUrl } from '../utils/api';
import {
  formatFullDate,
  formatSender,
  formatAddressList,
  formatFileSize,
} from '../utils/format';
import type { ThreadDetail, Email, Attachment } from '../types';

export default function ThreadView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    fetchThread(Number(id))
      .then(setThread)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleBack = useCallback(() => navigate(-1), [navigate]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (
        e.key === 'Escape' &&
        (e.target as HTMLElement).tagName !== 'INPUT'
      ) {
        handleBack();
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [handleBack]);

  if (loading) {
    return <div className="email-view-loading">Loading thread...</div>;
  }

  if (error || !thread) {
    return (
      <div className="email-view-error">
        {error || 'Thread not found'}
      </div>
    );
  }

  return (
    <div className="thread-view">
      <div className="email-view-toolbar">
        <button className="btn-back" onClick={handleBack}>
          <ArrowLeft size={16} />
          <span>Back</span>
        </button>
      </div>

      <div className="email-view-header">
        <h2 className="email-view-subject">
          {thread.subject || '(no subject)'}
        </h2>
        <span className="thread-count">
          {thread.message_count} message{thread.message_count !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="thread-messages">
        {thread.messages.map((msg, i) => (
          <ThreadMessage
            key={msg.id}
            msg={msg}
            defaultExpanded={i === thread.messages.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

function ThreadMessage({
  msg,
  defaultExpanded,
}: {
  msg: Email;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [showHtml, setShowHtml] = useState(!!msg.body_html);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (expanded && msg.body_html && showHtml && iframeRef.current) {
      const doc = iframeRef.current.contentDocument;
      if (doc) {
        doc.open();
        doc.write(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.6;
      color: #202124;
      margin: 16px;
      word-wrap: break-word;
    }
    img { max-width: 100%; height: auto; }
    a { color: #1a73e8; }
  </style>
</head>
<body>${msg.body_html}</body>
</html>`);
        doc.close();
        const resizeObserver = new ResizeObserver(() => {
          if (iframeRef.current && doc.body) {
            iframeRef.current.style.height =
              doc.body.scrollHeight + 32 + 'px';
          }
        });
        if (doc.body) resizeObserver.observe(doc.body);
        return () => resizeObserver.disconnect();
      }
    }
  }, [expanded, msg.body_html, showHtml]);

  const sender = formatSender(msg.from_name, msg.from_address);
  const snippetText = msg.snippet || msg.body_text?.slice(0, 100).replace(/\n/g, ' ') || '';

  return (
    <div className={`thread-message ${expanded ? 'expanded' : 'collapsed'}`}>
      <div
        className="thread-message-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="thread-message-chevron">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </span>
        <div className="thread-message-sender">
          <strong>{sender}</strong>
          {!expanded && snippetText && (
            <span className="thread-message-snippet">
              {' '}&mdash; {snippetText}
            </span>
          )}
        </div>
        <div className="thread-message-date">
          {formatFullDate(msg.date)}
        </div>
      </div>

      {expanded && (
        <div className="thread-message-body">
          <div className="thread-message-details">
            {msg.to_addresses.length > 0 && (
              <div>
                <span className="email-meta-label">To: </span>
                {formatAddressList(msg.to_addresses)}
              </div>
            )}
            {msg.cc_addresses.length > 0 && (
              <div>
                <span className="email-meta-label">Cc: </span>
                {formatAddressList(msg.cc_addresses)}
              </div>
            )}
          </div>

          {msg.body_html && (
            <div className="email-view-toggle">
              <button
                className={showHtml ? 'active' : ''}
                onClick={() => setShowHtml(true)}
              >
                HTML
              </button>
              <button
                className={!showHtml ? 'active' : ''}
                onClick={() => setShowHtml(false)}
              >
                Plain Text
              </button>
            </div>
          )}

          {showHtml && msg.body_html ? (
            <iframe
              ref={iframeRef}
              className="email-html-frame"
              sandbox="allow-same-origin"
              title="Email content"
            />
          ) : (
            <pre className="email-text-body">
              {msg.body_text || '(no content)'}
            </pre>
          )}

          {msg.attachments.length > 0 && (
            <ThreadAttachments attachments={msg.attachments} />
          )}
        </div>
      )}
    </div>
  );
}

function ThreadAttachments({ attachments }: { attachments: Attachment[] }) {
  return (
    <div className="attachments" style={{ margin: '12px 0' }}>
      <div className="attachments-header">
        <Paperclip size={14} />
        <span>
          {attachments.length} attachment
          {attachments.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="attachments-list">
        {attachments.map((att) => (
          <div key={att.id} className="attachment-item">
            <div className="attachment-icon">
              <Paperclip size={18} />
            </div>
            <div className="attachment-info">
              <span className="attachment-name">
                {att.filename || 'unnamed'}
              </span>
              <span className="attachment-size">
                {formatFileSize(att.size_bytes)}
              </span>
            </div>
            <div className="attachment-actions">
              {isPreviewable(att.content_type) && (
                <a
                  href={getAttachmentUrl(att.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="attachment-btn"
                  title="Preview"
                >
                  <Eye size={16} />
                </a>
              )}
              <a
                href={getAttachmentUrl(att.id)}
                download
                className="attachment-btn"
                title="Download"
              >
                <Download size={16} />
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function isPreviewable(contentType: string | null): boolean {
  if (!contentType) return false;
  return (
    contentType.startsWith('image/') ||
    contentType === 'application/pdf' ||
    contentType.startsWith('text/')
  );
}
