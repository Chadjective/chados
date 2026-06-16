import { useEffect, useState, useCallback, type ReactNode } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import {
  Inbox,
  Send,
  Star,
  AlertOctagon,
  FileEdit,
  AlertTriangle,
  Trash2,
  Mail,
  Tag,
  Image,
  FolderOpen,
  Film,
  Heart,
  Upload,
  Users,
  CalendarDays,
  MessageSquare,
  HardDrive,
  StickyNote,
  BarChart3,
  MessageCircle,
  Sun,
  Moon,
  Sparkles,
} from 'lucide-react';
import { fetchLabels } from '../utils/api';
import type { Label } from '../types';

const SYSTEM_LABEL_ORDER = [
  'Inbox',
  'Sent Mail',
  'Sent',
  'Starred',
  'Important',
  'Drafts',
  'Spam',
  'Trash',
  'All Mail',
];

const SYSTEM_LABEL_ICONS: Record<string, ReactNode> = {
  Inbox: <Inbox size={18} />,
  'Sent Mail': <Send size={18} />,
  Sent: <Send size={18} />,
  Starred: <Star size={18} />,
  Important: <AlertOctagon size={18} />,
  Drafts: <FileEdit size={18} />,
  Spam: <AlertTriangle size={18} />,
  Trash: <Trash2 size={18} />,
  'All Mail': <Mail size={18} />,
};

const PHOTO_ITEMS = [
  { path: '/photos', label: 'Timeline', icon: <Image size={18} /> },
  { path: '/photos/albums', label: 'Albums', icon: <FolderOpen size={18} /> },
  { path: '/photos/videos', label: 'Videos', icon: <Film size={18} /> },
  { path: '/photos/favorites', label: 'Favorites', icon: <Heart size={18} /> },
  { path: '/photos/import', label: 'Import', icon: <Upload size={18} /> },
];

const OTHER_SECTIONS = [
  { path: '/contacts', label: 'Contacts', icon: <Users size={18} /> },
  { path: '/calendar', label: 'Calendar', icon: <CalendarDays size={18} /> },
  { path: '/chat', label: 'Chat', icon: <MessageSquare size={18} /> },
  { path: '/drive', label: 'Drive', icon: <HardDrive size={18} /> },
  { path: '/notes', label: 'Notes', icon: <StickyNote size={18} /> },
  { path: '/analytics', label: 'Analytics', icon: <BarChart3 size={18} /> },
  { path: '/ai-chat', label: 'AI Chat', icon: <MessageCircle size={18} /> },
  { path: '/space', label: 'Space Manager', icon: <HardDrive size={18} /> },
  { path: '/tags', label: 'Tags', icon: <Tag size={18} /> },
];

type Theme = 'light' | 'dark' | 'claude';
const THEMES: Theme[] = ['light', 'dark', 'claude'];

function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('theme') as Theme | null;
    if (saved && THEMES.includes(saved)) return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const cycle = useCallback(() => {
    setTheme((t) => THEMES[(THEMES.indexOf(t) + 1) % THEMES.length]);
  }, []);

  return { theme, cycle };
}

export default function Sidebar() {
  const [labels, setLabels] = useState<Label[]>([]);
  const navigate = useNavigate();
  const params = useParams<{ name: string }>();
  const location = useLocation();
  const activeLabel = params.name || '';
  const { theme, cycle: cycleTheme } = useTheme();

  useEffect(() => {
    fetchLabels().then(setLabels).catch(console.error);
  }, []);

  const systemLabelNames = new Set(SYSTEM_LABEL_ORDER);
  const systemLabels = SYSTEM_LABEL_ORDER.map((name) =>
    labels.find((l) => l.name === name)
  ).filter((l): l is Label => l !== undefined);

  const customLabels = labels
    .filter((l) => !systemLabelNames.has(l.name))
    .sort((a, b) => a.name.localeCompare(b.name));

  function handleClick(labelName: string) {
    if (labelName === '') {
      navigate('/');
    } else {
      navigate(`/label/${encodeURIComponent(labelName)}`);
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1>Gmail Archive</h1>
      </div>

      <button
        className={`sidebar-item ${activeLabel === '' ? 'active' : ''}`}
        onClick={() => handleClick('')}
      >
        <span className="sidebar-icon">
          <Mail size={18} />
        </span>
        <span className="sidebar-label">All Mail</span>
      </button>

      <div className="sidebar-section">
        {systemLabels.map((label) => (
          <button
            key={label.id}
            className={`sidebar-item ${activeLabel === label.name ? 'active' : ''}`}
            onClick={() => handleClick(label.name)}
          >
            <span className="sidebar-icon">
              {SYSTEM_LABEL_ICONS[label.name] || <Tag size={18} />}
            </span>
            <span className="sidebar-label">{label.name}</span>
            <span className="sidebar-count">
              {label.email_count.toLocaleString()}
            </span>
          </button>
        ))}
      </div>

      {customLabels.length > 0 && (
        <>
          <div className="sidebar-divider" />
          <div className="sidebar-section-title">Labels</div>
          <div className="sidebar-section sidebar-custom-labels">
            {customLabels.map((label) => (
              <button
                key={label.id}
                className={`sidebar-item ${activeLabel === label.name ? 'active' : ''}`}
                onClick={() => handleClick(label.name)}
              >
                <span className="sidebar-icon">
                  <Tag size={18} />
                </span>
                <span className="sidebar-label">{label.name}</span>
                <span className="sidebar-count">
                  {label.email_count.toLocaleString()}
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      <div className="sidebar-divider" />
      <button
        className={`sidebar-item ${location.pathname === '/trash' ? 'active' : ''}`}
        onClick={() => navigate('/trash')}
      >
        <span className="sidebar-icon"><Trash2 size={18} /></span>
        <span className="sidebar-label">ChadOS Trash</span>
      </button>

      <div className="sidebar-divider" />
      <div className="sidebar-section-title">Photos</div>
      <div className="sidebar-section">
        {PHOTO_ITEMS.map((item) => (
          <button
            key={item.path}
            className={`sidebar-item ${location.pathname === item.path ? 'active' : ''}`}
            onClick={() => navigate(item.path)}
          >
            <span className="sidebar-icon">{item.icon}</span>
            <span className="sidebar-label">{item.label}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-divider" />
      <div className="sidebar-section-title">More</div>
      <div className="sidebar-section">
        {OTHER_SECTIONS.map((item) => (
          <button
            key={item.path}
            className={`sidebar-item ${location.pathname.startsWith(item.path) ? 'active' : ''}`}
            onClick={() => navigate(item.path)}
          >
            <span className="sidebar-icon">{item.icon}</span>
            <span className="sidebar-label">{item.label}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-spacer" />
      <div className="sidebar-footer">
        <button className="sidebar-item theme-toggle" onClick={cycleTheme}>
          <span className="sidebar-icon">
            {theme === 'light' ? <Moon size={18} /> : theme === 'dark' ? <Sparkles size={18} /> : <Sun size={18} />}
          </span>
          <span className="sidebar-label">
            {theme === 'light' ? 'Dark Mode' : theme === 'dark' ? 'Claude Mode' : 'Light Mode'}
          </span>
        </button>
      </div>
    </aside>
  );
}
