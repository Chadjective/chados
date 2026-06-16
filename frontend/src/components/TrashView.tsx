import { useState, useEffect, useCallback } from 'react';
import { Trash2, RotateCcw, AlertTriangle } from 'lucide-react';
import { fetchTrash, restoreItems, permanentDelete, emptyTrash } from '../utils/api';
import { formatEmailDate } from '../utils/format';
import ConfirmDialog from './ConfirmDialog';
import type { TrashItem } from '../types';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${sizes[i]}`;
}

export default function TrashView() {
  const [items, setItems] = useState<TrashItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalSize, setTotalSize] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showEmptyConfirm, setShowEmptyConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const loadTrash = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTrash('email', 0, 200);
      setItems(data.items);
      setTotal(data.total);
      setTotalSize(data.total_size_bytes);
    } catch (err) {
      console.error('Failed to load trash:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTrash();
  }, [loadTrash]);

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleRestore() {
    const ids = Array.from(selectedIds);
    try {
      await restoreItems('email', ids);
      setSelectedIds(new Set());
      loadTrash();
    } catch (err) {
      console.error('Restore failed:', err);
    }
  }

  async function handlePermanentDelete() {
    const ids = Array.from(selectedIds);
    try {
      await permanentDelete('email', ids);
      setSelectedIds(new Set());
      setShowDeleteConfirm(false);
      loadTrash();
    } catch (err) {
      console.error('Permanent delete failed:', err);
    }
  }

  async function handleEmptyTrash() {
    try {
      await emptyTrash('all');
      setShowEmptyConfirm(false);
      setSelectedIds(new Set());
      loadTrash();
    } catch (err) {
      console.error('Empty trash failed:', err);
    }
  }

  if (loading) {
    return (
      <div className="trash-view">
        <div className="trash-header">
          <h2><Trash2 size={20} /> Trash</h2>
        </div>
        <div className="trash-loading">Loading...</div>
      </div>
    );
  }

  return (
    <div className="trash-view">
      <div className="trash-header">
        <div className="trash-header-left">
          <h2><Trash2 size={20} /> Trash</h2>
          <span className="trash-summary">
            {total} item{total !== 1 ? 's' : ''} &middot; {formatBytes(totalSize)}
          </span>
        </div>
        <div className="trash-header-actions">
          {selectedIds.size > 0 && (
            <>
              <button className="trash-btn" onClick={handleRestore}>
                <RotateCcw size={14} /> Restore ({selectedIds.size})
              </button>
              <button
                className="trash-btn trash-btn-danger"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 size={14} /> Delete forever ({selectedIds.size})
              </button>
            </>
          )}
          {total > 0 && (
            <button
              className="trash-btn trash-btn-danger"
              onClick={() => setShowEmptyConfirm(true)}
            >
              <AlertTriangle size={14} /> Empty trash
            </button>
          )}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="trash-empty">
          <Trash2 size={48} strokeWidth={1} />
          <p>Trash is empty</p>
        </div>
      ) : (
        <div className="trash-list">
          {items.map((item) => (
            <div
              key={item.id}
              className={`trash-row ${selectedIds.has(item.id) ? 'selected' : ''}`}
            >
              <input
                type="checkbox"
                checked={selectedIds.has(item.id)}
                onChange={() => toggleSelect(item.id)}
              />
              <div className="trash-row-content">
                <span className="trash-row-from">{item.from_name || item.from_address || 'Unknown'}</span>
                <span className="trash-row-subject">{item.subject || '(no subject)'}</span>
                <span className="trash-row-snippet">{item.snippet}</span>
              </div>
              <div className="trash-row-meta">
                <span className="trash-row-size">
                  {item.raw_size_bytes ? formatBytes(item.raw_size_bytes) : ''}
                </span>
                <span className="trash-row-date">
                  {item.date ? formatEmailDate(item.date) : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={showEmptyConfirm}
        title="Empty trash"
        message={`Permanently delete ${total} item${total !== 1 ? 's' : ''}, freeing ${formatBytes(totalSize)}?`}
        detail="This cannot be undone. Files will be removed from disk."
        confirmLabel="Empty trash"
        destructive
        onConfirm={handleEmptyTrash}
        onCancel={() => setShowEmptyConfirm(false)}
      />

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Permanently delete"
        message={`Permanently delete ${selectedIds.size} item${selectedIds.size !== 1 ? 's' : ''}?`}
        detail="This cannot be undone."
        confirmLabel="Delete forever"
        destructive
        onConfirm={handlePermanentDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  );
}
