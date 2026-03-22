import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Pin, Tag, X, ArrowLeft } from 'lucide-react';
import { fetchNotes, fetchNote, fetchNoteLabels } from '../utils/api';
import type { Note } from '../types';

const NOTE_COLORS: Record<string, string> = {
  DEFAULT: '#ffffff',
  RED: '#f28b82',
  ORANGE: '#fbbc04',
  YELLOW: '#fff475',
  GREEN: '#ccff90',
  TEAL: '#a7ffeb',
  BLUE: '#cbf0f8',
  DARK_BLUE: '#aecbfa',
  PURPLE: '#d7aefb',
  PINK: '#fdcfe8',
  BROWN: '#e6c9a8',
  GRAY: '#e8eaed',
};

function getNoteColor(color: string | null): string {
  if (!color) return NOTE_COLORS.DEFAULT;
  return NOTE_COLORS[color.toUpperCase()] || color;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString([], {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export default function NotesView() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [notes, setNotes] = useState<Note[]>([]);
  const [labels, setLabels] = useState<string[]>([]);
  const [selectedLabel, setSelectedLabel] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedNote, setSelectedNote] = useState<Note | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetchNoteLabels().then(setLabels).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchNotes({ label: selectedLabel || undefined, limit: 500 })
      .then((res) => setNotes(res.notes))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedLabel]);

  useEffect(() => {
    if (id) {
      setDetailLoading(true);
      fetchNote(Number(id))
        .then(setSelectedNote)
        .catch(console.error)
        .finally(() => setDetailLoading(false));
    } else {
      setSelectedNote(null);
    }
  }, [id]);

  const pinned = notes.filter((n) => n.is_pinned);
  const unpinned = notes.filter((n) => !n.is_pinned);

  if (selectedNote || detailLoading) {
    return (
      <div className="note-detail-view">
        <div className="note-detail-toolbar">
          <button className="btn-back" onClick={() => navigate('/notes')}>
            <ArrowLeft size={16} />
            Back to Notes
          </button>
        </div>
        {detailLoading ? (
          <div className="note-detail-loading">Loading note...</div>
        ) : selectedNote ? (
          <div
            className="note-detail-card"
            style={{ backgroundColor: getNoteColor(selectedNote.color) }}
          >
            {selectedNote.is_pinned && (
              <div className="note-detail-pin">
                <Pin size={16} /> Pinned
              </div>
            )}
            <h2 className="note-detail-title">{selectedNote.title || 'Untitled'}</h2>
            <div className="note-detail-content">
              {selectedNote.content || 'No content'}
            </div>
            {selectedNote.labels.length > 0 && (
              <div className="note-detail-labels">
                {selectedNote.labels.map((label) => (
                  <span key={label} className="note-label-tag">
                    <Tag size={10} /> {label}
                  </span>
                ))}
              </div>
            )}
            <div className="note-detail-dates">
              {selectedNote.created_time && (
                <span>Created: {formatDate(selectedNote.created_time)}</span>
              )}
              {selectedNote.modified_time && (
                <span>Modified: {formatDate(selectedNote.modified_time)}</span>
              )}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="notes-container">
      <div className="notes-header">
        <h2>Notes</h2>
        {labels.length > 0 && (
          <div className="notes-label-filter">
            <button
              className={`notes-filter-btn ${selectedLabel === '' ? 'active' : ''}`}
              onClick={() => setSelectedLabel('')}
            >
              All
            </button>
            {labels.map((label) => (
              <button
                key={label}
                className={`notes-filter-btn ${selectedLabel === label ? 'active' : ''}`}
                onClick={() => setSelectedLabel(label)}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="notes-body">
        {loading ? (
          <div className="notes-loading">Loading notes...</div>
        ) : notes.length === 0 ? (
          <div className="notes-empty">No notes found</div>
        ) : (
          <>
            {pinned.length > 0 && (
              <>
                <div className="notes-section-title">
                  <Pin size={14} /> Pinned
                </div>
                <div className="notes-masonry">
                  {pinned.map((note) => (
                    <div
                      key={note.id}
                      className="note-card"
                      style={{ backgroundColor: getNoteColor(note.color) }}
                      onClick={() => navigate(`/notes/${note.id}`)}
                    >
                      {note.title && (
                        <div className="note-card-title">{note.title}</div>
                      )}
                      {note.content && (
                        <div className="note-card-content">
                          {note.content.length > 200
                            ? note.content.slice(0, 200) + '...'
                            : note.content}
                        </div>
                      )}
                      {note.labels.length > 0 && (
                        <div className="note-card-labels">
                          {note.labels.map((label) => (
                            <span key={label} className="note-label-tag">
                              {label}
                            </span>
                          ))}
                        </div>
                      )}
                      {note.is_pinned && (
                        <div className="note-card-pin">
                          <Pin size={12} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}

            {unpinned.length > 0 && (
              <>
                {pinned.length > 0 && (
                  <div className="notes-section-title">Others</div>
                )}
                <div className="notes-masonry">
                  {unpinned.map((note) => (
                    <div
                      key={note.id}
                      className="note-card"
                      style={{ backgroundColor: getNoteColor(note.color) }}
                      onClick={() => navigate(`/notes/${note.id}`)}
                    >
                      {note.title && (
                        <div className="note-card-title">{note.title}</div>
                      )}
                      {note.content && (
                        <div className="note-card-content">
                          {note.content.length > 200
                            ? note.content.slice(0, 200) + '...'
                            : note.content}
                        </div>
                      )}
                      {note.labels.length > 0 && (
                        <div className="note-card-labels">
                          {note.labels.map((label) => (
                            <span key={label} className="note-label-tag">
                              {label}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
