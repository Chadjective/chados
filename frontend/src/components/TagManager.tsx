import { useState, useEffect, useCallback } from 'react';
import { Tag, Plus, X, Edit2, Check } from 'lucide-react';
import { fetchTags, createTag, updateTag, deleteTag } from '../utils/api';
import type { UserTag } from '../types';
import ConfirmDialog from './ConfirmDialog';

const PRESET_COLORS = [
  '#1a73e8', '#e53935', '#43a047', '#fb8c00',
  '#8e24aa', '#00897b', '#d81b60', '#3949ab',
  '#546e7a', '#6d4c41',
];

export default function TagManager() {
  const [tags, setTags] = useState<UserTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(PRESET_COLORS[0]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const loadTags = useCallback(async () => {
    try {
      const data = await fetchTags();
      setTags(data.tags);
    } catch (err) {
      console.error('Failed to load tags:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTags();
  }, [loadTags]);

  async function handleCreate() {
    if (!newName.trim()) return;
    try {
      await createTag(newName.trim(), newColor);
      setNewName('');
      setNewColor(PRESET_COLORS[0]);
      loadTags();
    } catch (err) {
      console.error('Failed to create tag:', err);
    }
  }

  async function handleUpdate() {
    if (editingId === null || !editName.trim()) return;
    try {
      await updateTag(editingId, { name: editName.trim(), color: editColor });
      setEditingId(null);
      loadTags();
    } catch (err) {
      console.error('Failed to update tag:', err);
    }
  }

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteTag(deleteId);
      setDeleteId(null);
      loadTags();
    } catch (err) {
      console.error('Failed to delete tag:', err);
    }
  }

  function startEdit(tag: UserTag) {
    setEditingId(tag.id);
    setEditName(tag.name);
    setEditColor(tag.color);
  }

  return (
    <div className="tag-manager">
      <div className="tag-manager-header">
        <h2><Tag size={20} /> Tags</h2>
      </div>

      {/* Create new tag */}
      <div className="tag-create">
        <input
          type="text"
          placeholder="New tag name..."
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          className="tag-input"
        />
        <div className="tag-color-picker">
          {PRESET_COLORS.map((c) => (
            <button
              key={c}
              className={`tag-color-swatch ${c === newColor ? 'active' : ''}`}
              style={{ backgroundColor: c }}
              onClick={() => setNewColor(c)}
            />
          ))}
        </div>
        <button
          className="tag-create-btn"
          onClick={handleCreate}
          disabled={!newName.trim()}
        >
          <Plus size={16} /> Create
        </button>
      </div>

      {/* Tag list */}
      {loading ? (
        <div className="tag-loading">Loading tags...</div>
      ) : tags.length === 0 ? (
        <div className="tag-empty">
          <Tag size={32} strokeWidth={1} />
          <p>No tags yet. Create one above.</p>
        </div>
      ) : (
        <div className="tag-list">
          {tags.map((tag) => (
            <div key={tag.id} className="tag-item">
              {editingId === tag.id ? (
                <div className="tag-edit-row">
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleUpdate()}
                    className="tag-input tag-input-sm"
                    autoFocus
                  />
                  <div className="tag-color-picker tag-color-picker-sm">
                    {PRESET_COLORS.map((c) => (
                      <button
                        key={c}
                        className={`tag-color-swatch tag-color-swatch-sm ${c === editColor ? 'active' : ''}`}
                        style={{ backgroundColor: c }}
                        onClick={() => setEditColor(c)}
                      />
                    ))}
                  </div>
                  <button className="tag-icon-btn" onClick={handleUpdate} title="Save">
                    <Check size={14} />
                  </button>
                  <button className="tag-icon-btn" onClick={() => setEditingId(null)} title="Cancel">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <>
                  <div className="tag-item-left">
                    <span className="tag-pill" style={{ backgroundColor: tag.color }}>
                      {tag.name}
                    </span>
                    <span className="tag-item-count">{tag.item_count} items</span>
                  </div>
                  <div className="tag-item-actions">
                    <button className="tag-icon-btn" onClick={() => startEdit(tag)} title="Edit">
                      <Edit2 size={14} />
                    </button>
                    <button
                      className="tag-icon-btn tag-icon-btn-danger"
                      onClick={() => setDeleteId(tag.id)}
                      title="Delete"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={deleteId !== null}
        title="Delete tag"
        message={`Delete the tag "${tags.find((t) => t.id === deleteId)?.name}"?`}
        detail="This will remove the tag from all items."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
