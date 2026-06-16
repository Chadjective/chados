import { useNavigate } from 'react-router-dom';
import { Star, Paperclip } from 'lucide-react';
import type { EmailSummary } from '../types';
import { formatEmailDate, formatSender } from '../utils/format';

interface EmailRowProps {
  email: EmailSummary;
  isSelected: boolean;
  isChecked?: boolean;
  onCheckToggle?: (shiftKey: boolean) => void;
}

export default function EmailRow({ email, isSelected, isChecked = false, onCheckToggle }: EmailRowProps) {
  const navigate = useNavigate();
  const sender = formatSender(email.from_name, email.from_address);
  const date = formatEmailDate(email.date);
  const isUnread = !email.is_read;

  return (
    <div
      className={`email-row${isSelected ? ' selected' : ''}${isUnread ? ' unread' : ''}${isChecked ? ' checked' : ''}`}
      onClick={() => navigate(`/email/${email.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter') navigate(`/email/${email.id}`);
      }}
    >
      <div className="email-row-checkbox">
        <input
          type="checkbox"
          checked={isChecked}
          onClick={(e) => {
            e.stopPropagation();
            onCheckToggle?.(e.shiftKey);
          }}
          readOnly
        />
      </div>
      <div
        className={`email-row-star${email.is_starred ? ' starred' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <Star size={16} fill={email.is_starred ? '#f4b400' : 'none'} />
      </div>
      <div className="email-row-sender" title={email.from_address || ''}>
        {sender}
      </div>
      <div className="email-row-content">
        <span className="email-row-subject">
          {email.subject || '(no subject)'}
        </span>
        {email.snippet && (
          <span className="email-row-snippet"> &mdash; {email.snippet}</span>
        )}
      </div>
      <div className="email-row-meta">
        {email.has_attachments && (
          <span className="email-row-attachment">
            <Paperclip size={14} />
          </span>
        )}
        <span className="email-row-date">{date}</span>
      </div>
    </div>
  );
}
