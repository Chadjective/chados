import { useState } from 'react';
import { Trash2, Star, Mail, MailOpen, Tag, X } from 'lucide-react';
import { softDelete, toggleStar, markRead } from '../utils/api';
import ConfirmDialog from './ConfirmDialog';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${sizes[i]}`;
}

interface ActionToolbarProps {
  selectedIds: number[];
  onActionComplete: () => void;
  onClearSelection: () => void;
}

export default function ActionToolbar({
  selectedIds,
  onActionComplete,
  onClearSelection,
}: ActionToolbarProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [loading, setLoading] = useState(false);

  if (selectedIds.length === 0) return null;

  async function handleDelete() {
    setLoading(true);
    try {
      await softDelete('email', selectedIds);
      onClearSelection();
      onActionComplete();
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setLoading(false);
      setShowDeleteConfirm(false);
    }
  }

  async function handleStar(starred: boolean) {
    setLoading(true);
    try {
      await toggleStar(selectedIds, starred);
      onActionComplete();
    } catch (err) {
      console.error('Star failed:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleMarkRead(read: boolean) {
    setLoading(true);
    try {
      await markRead(selectedIds, read);
      onActionComplete();
    } catch (err) {
      console.error('Mark read failed:', err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="action-toolbar">
        <div className="action-toolbar-left">
          <button className="action-toolbar-close" onClick={onClearSelection} title="Clear selection">
            <X size={16} />
          </button>
          <span className="action-toolbar-count">
            {selectedIds.length} selected
          </span>
        </div>
        <div className="action-toolbar-actions">
          <button
            className="action-btn"
            onClick={() => setShowDeleteConfirm(true)}
            disabled={loading}
            title="Delete"
          >
            <Trash2 size={16} />
            <span>Delete</span>
          </button>
          <button
            className="action-btn"
            onClick={() => handleStar(true)}
            disabled={loading}
            title="Star"
          >
            <Star size={16} />
            <span>Star</span>
          </button>
          <button
            className="action-btn"
            onClick={() => handleMarkRead(true)}
            disabled={loading}
            title="Mark as read"
          >
            <MailOpen size={16} />
            <span>Read</span>
          </button>
          <button
            className="action-btn"
            onClick={() => handleMarkRead(false)}
            disabled={loading}
            title="Mark as unread"
          >
            <Mail size={16} />
            <span>Unread</span>
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete emails"
        message={`Move ${selectedIds.length} email${selectedIds.length !== 1 ? 's' : ''} to trash?`}
        detail="You can restore them from the Trash view."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </>
  );
}
