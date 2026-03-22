import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, MessageSquare, Download, Paperclip, Eye } from 'lucide-react';
import { fetchEmail, getAttachmentUrl } from '../utils/api';
import { formatFullDate, formatSender, formatAddressList, formatFileSize } from '../utils/format';
import type { Email, Attachment } from '../types';
import RelatedSidebar from './RelatedSidebar';

export default function EmailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [email, setEmail] = useState<Email | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showHtml, setShowHtml] = useState(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    fetchEmail(Number(id))
      .then((data) => {
        setEmail(data);
        setShowHtml(!!data.body_html);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Write HTML content into sandboxed iframe
  useEffect(() => {
    if (email?.body_html && showHtml && iframeRef.current) {
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
      overflow-wrap: break-word;
    }
    img { max-width: 100%; height: auto; }
    a { color: #1a73e8; }
    table { max-width: 100%; }
    pre { white-space: pre-wrap; word-wrap: break-word; }
  </style>
</head>
<body>${email.body_html}</body>
</html>`);
        doc.close();

        const resizeObserver = new ResizeObserver(() => {
          if (iframeRef.current && doc.body) {
            iframeRef.current.style.height = doc.body.scrollHeight + 32 + 'px';
          }
        });
        if (doc.body) resizeObserver.observe(doc.body);
        return () => resizeObserver.disconnect();
      }
    }
  }, [email, showHtml]);

  // Escape to go back
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
    return <div className="email-view-loading">Loading...</div>;
  }

  if (error || !email) {
    return (
      <div className="email-view-error">{error || 'Email not found'}</div>
    );
  }

  return (
    <div className="email-view-with-related">
      <div className="email-view">
        <div className="email-view-toolbar">
          <button className="btn-back" onClick={handleBack}>
            <ArrowLeft size={16} />
            <span>Back</span>
          </button>
          {email.thread_id && (
            <button
              className="btn-thread"
              onClick={() => navigate(`/thread/${email.id}`)}
            >
              <MessageSquare size={16} />
              <span>View Thread</span>
            </button>
          )}
        </div>

        <div className="email-view-header">
          <h2 className="email-view-subject">
            {email.subject || '(no subject)'}
          </h2>
          {email.labels.length > 0 && (
            <div className="email-view-labels">
              {email.labels.map((l) => (
                <span key={l} className="email-label-tag">
                  {l}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="email-view-meta">
          <div className="email-view-from">
            <strong>{formatSender(email.from_name, email.from_address)}</strong>
            {email.from_name && email.from_address && (
              <span className="email-view-address">
                {' '}
                &lt;{email.from_address}&gt;
              </span>
            )}
          </div>
          <div className="email-view-date">{formatFullDate(email.date)}</div>
          {email.to_addresses.length > 0 && (
            <div className="email-view-to">
              <span className="email-meta-label">To: </span>
              {formatAddressList(email.to_addresses)}
            </div>
          )}
          {email.cc_addresses.length > 0 && (
            <div className="email-view-cc">
              <span className="email-meta-label">Cc: </span>
              {formatAddressList(email.cc_addresses)}
            </div>
          )}
        </div>

        {email.body_html && (
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

        <div className="email-view-body">
          {showHtml && email.body_html ? (
            <iframe
              ref={iframeRef}
              className="email-html-frame"
              sandbox="allow-same-origin"
              title="Email content"
            />
          ) : (
            <pre className="email-text-body">
              {email.body_text || '(no content)'}
            </pre>
          )}
        </div>

        {email.attachments.length > 0 && (
          <AttachmentList attachments={email.attachments} />
        )}
      </div>
      <RelatedSidebar type="email" id={email.id} />
    </div>
  );
}

function AttachmentList({ attachments }: { attachments: Attachment[] }) {
  return (
    <div className="attachments">
      <div className="attachments-header">
        <Paperclip size={14} />
        <span>
          {attachments.length} attachment{attachments.length !== 1 ? 's' : ''}
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
