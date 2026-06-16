import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { HardDrive, Trash2, Mail, Image, FileText, Paperclip } from 'lucide-react';
import { fetchSpaceAnalysis, fetchSmartFilters } from '../utils/api';
import type { SpaceAnalysis, SmartFilter } from '../types';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${sizes[i]}`;
}

const TYPE_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  photos: Image,
  attachments: Paperclip,
  drive: FileText,
};

const TYPE_COLORS: Record<string, string> = {
  email: '#4285f4',
  photos: '#34a853',
  attachments: '#fbbc05',
  drive: '#ea4335',
};

export default function SpaceManager() {
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<SpaceAnalysis | null>(null);
  const [filters, setFilters] = useState<SmartFilter[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchSpaceAnalysis(), fetchSmartFilters()])
      .then(([space, smart]) => {
        setAnalysis(space);
        setFilters(smart.filters);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading || !analysis) {
    return (
      <div className="space-manager">
        <div className="space-header">
          <h2><HardDrive size={20} /> Space Manager</h2>
        </div>
        <div className="space-loading">Analyzing your archive...</div>
      </div>
    );
  }

  return (
    <div className="space-manager">
      <div className="space-header">
        <h2><HardDrive size={20} /> Space Manager</h2>
        <span className="space-total">Total: {formatBytes(analysis.total_bytes)}</span>
      </div>

      {/* Space breakdown bar */}
      <div className="space-breakdown">
        <div className="space-bar">
          {Object.entries(analysis.by_type).map(([type, data]) => {
            const pct = analysis.total_bytes > 0 ? (data.bytes / analysis.total_bytes) * 100 : 0;
            if (pct < 0.5) return null;
            return (
              <div
                key={type}
                className="space-bar-segment"
                style={{ width: `${pct}%`, backgroundColor: TYPE_COLORS[type] || '#999' }}
                title={`${type}: ${formatBytes(data.bytes)}`}
              />
            );
          })}
        </div>
        <div className="space-legend">
          {Object.entries(analysis.by_type).map(([type, data]) => {
            const Icon = TYPE_ICONS[type] || HardDrive;
            return (
              <div key={type} className="space-legend-item">
                <span className="space-legend-dot" style={{ backgroundColor: TYPE_COLORS[type] || '#999' }} />
                <Icon size={14} />
                <span className="space-legend-label">{type}</span>
                <span className="space-legend-value">
                  {formatBytes(data.bytes)} ({data.count.toLocaleString()})
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Smart suggestions */}
      {filters.length > 0 && (
        <div className="space-section">
          <h3>Cleanup Suggestions</h3>
          <div className="space-suggestions">
            {filters.map((f) => (
              <div key={f.name} className="space-suggestion">
                <div className="space-suggestion-info">
                  <span className="space-suggestion-name">{f.name}</span>
                  <span className="space-suggestion-stats">
                    {f.count.toLocaleString()} emails &middot; {formatBytes(f.size_bytes)}
                  </span>
                </div>
                <button
                  className="space-suggestion-btn"
                  onClick={() => navigate(`/search?q=${encodeURIComponent(f.query)}`)}
                >
                  Preview
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Potential savings */}
      {Object.keys(analysis.potential_savings).length > 0 && (
        <div className="space-section">
          <h3>Potential Savings</h3>
          <div className="space-savings">
            {Object.entries(analysis.potential_savings).map(([key, data]) => {
              if (data.count === 0) return null;
              return (
                <div key={key} className="space-saving-item">
                  <Trash2 size={14} />
                  <span>
                    Delete {data.count.toLocaleString()} {key.replace(/_/g, ' ')} to free{' '}
                    <strong>{formatBytes(data.bytes)}</strong>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Top space consumers */}
      {analysis.top_space_consumers.length > 0 && (
        <div className="space-section">
          <h3>Largest Emails</h3>
          <div className="space-top-list">
            {analysis.top_space_consumers.slice(0, 10).map((item) => (
              <div
                key={item.id}
                className="space-top-item"
                onClick={() => navigate(`/email/${item.id}`)}
              >
                <div className="space-top-info">
                  <span className="space-top-subject">{item.subject || '(no subject)'}</span>
                  <span className="space-top-from">{item.from_name || ''}</span>
                </div>
                <span className="space-top-size">{formatBytes(item.bytes)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
