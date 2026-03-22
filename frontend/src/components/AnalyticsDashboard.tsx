import { useEffect, useState, useMemo, useCallback } from 'react';
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  Mail, Image, CalendarDays, Users, MessageSquare, HardDrive,
  TrendingUp, Clock, UserCheck, PenLine, Camera, Activity,
  ChevronLeft,
} from 'lucide-react';
import {
  fetchEmailVolume, fetchEmailHeatmap, fetchTopContacts,
  fetchContactTimeline, fetchWritingStats, fetchArchiveOverview,
  fetchOnThisDay, fetchActivityTimeline, fetchPhotoStats,
} from '../utils/api';
import type {
  EmailVolume, EmailHeatmap, TopContact, ContactTimeline,
  WritingStats, ArchiveOverview, OnThisDay, ActivityTimeline, PhotoStats,
} from '../types';

type Tab = 'overview' | 'email' | 'writing' | 'photos' | 'activity';

const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'overview', label: 'Overview', icon: <TrendingUp size={16} /> },
  { key: 'email', label: 'Email', icon: <Mail size={16} /> },
  { key: 'writing', label: 'Writing', icon: <PenLine size={16} /> },
  { key: 'photos', label: 'Photos', icon: <Camera size={16} /> },
  { key: 'activity', label: 'Activity', icon: <Activity size={16} /> },
];

const ACCENT = '#1a73e8';
const ACCENT_LIGHT = '#4285f4';
const COLORS = ['#1a73e8', '#34a853', '#fbbc04', '#ea4335', '#673ab7', '#ff6d00', '#00bcd4', '#e91e63'];

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

// ── Overview Tab ──────────────────────────────────────

function OverviewTab() {
  const [overview, setOverview] = useState<ArchiveOverview | null>(null);
  const [onThisDay, setOnThisDay] = useState<OnThisDay | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchArchiveOverview()
      .then(setOverview)
      .catch(console.error)
      .finally(() => setLoading(false));
    fetchOnThisDay()
      .then(setOnThisDay)
      .catch(console.error);
  }, []);

  if (loading) return <div className="analytics-loading">Loading overview...</div>;
  if (!overview) return <div className="analytics-empty">No data available</div>;

  const cards = [
    { label: 'Emails', value: overview.email.total, range: overview.email.date_range, icon: <Mail size={24} />, color: '#1a73e8' },
    { label: 'Photos', value: overview.photos.total, range: overview.photos.date_range, icon: <Image size={24} />, color: '#34a853' },
    { label: 'Calendar Events', value: overview.calendar.total, range: overview.calendar.date_range, icon: <CalendarDays size={24} />, color: '#fbbc04' },
    { label: 'Contacts', value: overview.contacts.total, range: '', icon: <Users size={24} />, color: '#ea4335' },
    { label: 'Chat Messages', value: overview.chat.total, range: overview.chat.date_range, icon: <MessageSquare size={24} />, color: '#673ab7' },
    { label: 'Drive Files', value: overview.drive.total, range: '', icon: <HardDrive size={24} />, color: '#ff6d00' },
  ];

  const todayStr = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric' });

  return (
    <div className="analytics-tab-content">
      <div className="analytics-cards-grid">
        {cards.map((card) => (
          <div key={card.label} className="analytics-stat-card">
            <div className="analytics-stat-icon" style={{ color: card.color }}>
              {card.icon}
            </div>
            <div className="analytics-stat-info">
              <div className="analytics-stat-value">{formatNumber(card.value)}</div>
              <div className="analytics-stat-label">{card.label}</div>
              {card.range && <div className="analytics-stat-range">{card.range}</div>}
            </div>
          </div>
        ))}
      </div>

      {onThisDay && onThisDay.years.length > 0 && (
        <div className="analytics-section">
          <h3 className="analytics-section-title">
            <Clock size={18} />
            On This Day ({todayStr})
          </h3>
          <div className="analytics-on-this-day">
            {onThisDay.years.map((y) => (
              <div key={y.year} className="otd-year-card">
                <div className="otd-year">{y.year}</div>
                <div className="otd-stats">
                  {y.emails.length > 0 && <span className="otd-stat"><Mail size={14} /> {y.emails.length} emails</span>}
                  {y.photos.length > 0 && <span className="otd-stat"><Image size={14} /> {y.photos.length} photos</span>}
                  {y.events.length > 0 && <span className="otd-stat"><CalendarDays size={14} /> {y.events.length} events</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Email Tab ─────────────────────────────────────────

function EmailTab() {
  const [volume, setVolume] = useState<EmailVolume | null>(null);
  const [heatmap, setHeatmap] = useState<EmailHeatmap | null>(null);
  const [contacts, setContacts] = useState<TopContact[]>([]);
  const [selectedContact, setSelectedContact] = useState<string | null>(null);
  const [contactTimeline, setContactTimeline] = useState<ContactTimeline | null>(null);
  const [volumeMode, setVolumeMode] = useState<'yearly' | 'monthly'>('yearly');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchEmailVolume(), fetchEmailHeatmap(), fetchTopContacts(20)])
      .then(([v, h, c]) => { setVolume(v); setHeatmap(h); setContacts(c); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleContactClick = useCallback((address: string) => {
    setSelectedContact(address);
    fetchContactTimeline(address)
      .then(setContactTimeline)
      .catch(console.error);
  }, []);

  const volumeData = useMemo(() => {
    if (!volume) return [];
    if (volumeMode === 'yearly') {
      return volume.yearly.map(d => ({ name: String(d.year), Emails: d.count }));
    }
    return volume.monthly.map(d => ({
      name: `${MONTH_NAMES[d.month - 1]} ${d.year}`,
      Emails: d.count,
    }));
  }, [volume, volumeMode]);

  const heatmapMax = useMemo(() => {
    if (!heatmap) return 1;
    return Math.max(1, ...heatmap.heatmap.flat());
  }, [heatmap]);

  const contactBarData = useMemo(() => {
    return contacts.slice(0, 20).map(c => ({
      name: c.name || c.address,
      Sent: c.sent_count,
      Received: c.received_count,
    }));
  }, [contacts]);

  const timelineData = useMemo(() => {
    if (!contactTimeline) return [];
    return contactTimeline.months.map(m => ({
      name: `${MONTH_NAMES[m.month - 1]} ${m.year}`,
      Sent: m.sent,
      Received: m.received,
    }));
  }, [contactTimeline]);

  if (loading) return <div className="analytics-loading">Loading email analytics...</div>;

  return (
    <div className="analytics-tab-content">
      {/* Volume Chart */}
      <div className="analytics-section">
        <div className="analytics-section-header">
          <h3 className="analytics-section-title">
            <TrendingUp size={18} />
            Email Volume
          </h3>
          <div className="analytics-toggle">
            <button
              className={volumeMode === 'yearly' ? 'active' : ''}
              onClick={() => setVolumeMode('yearly')}
            >
              Yearly
            </button>
            <button
              className={volumeMode === 'monthly' ? 'active' : ''}
              onClick={() => setVolumeMode('monthly')}
            >
              Monthly
            </button>
          </div>
        </div>
        <div className="analytics-chart-container">
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={volumeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12 }}
                interval={volumeMode === 'monthly' ? Math.max(0, Math.floor(volumeData.length / 12) - 1) : 0}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="Emails"
                stroke={ACCENT}
                strokeWidth={2}
                dot={volumeMode === 'yearly'}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Heatmap */}
      {heatmap && (
        <div className="analytics-section">
          <h3 className="analytics-section-title">
            <Clock size={18} />
            Email Activity by Day &amp; Hour
          </h3>
          <div className="analytics-heatmap-wrapper">
            <div className="analytics-heatmap">
              <div className="heatmap-corner" />
              {HOURS.map(h => (
                <div key={h} className="heatmap-hour-label">
                  {h === 0 ? '12a' : h < 12 ? `${h}a` : h === 12 ? '12p' : `${h - 12}p`}
                </div>
              ))}
              {DAYS.map((day, di) => (
                <>
                  <div key={`label-${day}`} className="heatmap-day-label">{day}</div>
                  {HOURS.map(hi => {
                    const val = heatmap.heatmap[di]?.[hi] ?? 0;
                    const intensity = val / heatmapMax;
                    return (
                      <div
                        key={`${di}-${hi}`}
                        className="heatmap-cell"
                        style={{
                          backgroundColor: intensity === 0
                            ? '#f0f0f0'
                            : `rgba(26, 115, 232, ${0.15 + intensity * 0.85})`,
                        }}
                        title={`${day} ${hi}:00 — ${val.toLocaleString()} emails`}
                      />
                    );
                  })}
                </>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Top Contacts */}
      <div className="analytics-section">
        <h3 className="analytics-section-title">
          <UserCheck size={18} />
          Top 20 Contacts
        </h3>
        <div className="analytics-chart-container">
          <ResponsiveContainer width="100%" height={Math.max(400, contacts.length * 28)}>
            <BarChart data={contactBarData} layout="vertical" margin={{ left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fontSize: 11 }}
                width={115}
              />
              <Tooltip />
              <Legend />
              <Bar dataKey="Received" stackId="a" fill={ACCENT} />
              <Bar dataKey="Sent" stackId="a" fill={ACCENT_LIGHT} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="analytics-contact-list">
          {contacts.map((c) => (
            <button
              key={c.address}
              className={`analytics-contact-btn ${selectedContact === c.address ? 'active' : ''}`}
              onClick={() => handleContactClick(c.address)}
            >
              <span className="contact-btn-name">{c.name || c.address}</span>
              <span className="contact-btn-count">{c.total.toLocaleString()} emails</span>
            </button>
          ))}
        </div>
      </div>

      {/* Contact Timeline */}
      {selectedContact && contactTimeline && (
        <div className="analytics-section">
          <div className="analytics-section-header">
            <h3 className="analytics-section-title">
              <UserCheck size={18} />
              Timeline: {contactTimeline.name || contactTimeline.address}
            </h3>
            <button className="analytics-back-btn" onClick={() => { setSelectedContact(null); setContactTimeline(null); }}>
              <ChevronLeft size={16} /> Back
            </button>
          </div>
          <div className="analytics-chart-container">
            <ResponsiveContainer width="100%" height={350}>
              <AreaChart data={timelineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 12 }}
                  interval={Math.max(0, Math.floor(timelineData.length / 12) - 1)}
                />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="Received" stackId="1" stroke={ACCENT} fill={ACCENT} fillOpacity={0.3} />
                <Area type="monotone" dataKey="Sent" stackId="1" stroke={ACCENT_LIGHT} fill={ACCENT_LIGHT} fillOpacity={0.3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Writing Tab ───────────────────────────────────────

function WritingTab() {
  const [stats, setStats] = useState<WritingStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWritingStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const yearlyData = useMemo(() => {
    if (!stats) return [];
    return stats.yearly.map(d => ({
      name: String(d.year),
      'Avg Words': d.avg_words,
      'Avg Length': d.avg_length,
      'Email Count': d.email_count,
    }));
  }, [stats]);

  const maxWordCount = useMemo(() => {
    if (!stats || stats.top_words.length === 0) return 1;
    return stats.top_words[0].count;
  }, [stats]);

  if (loading) return <div className="analytics-loading">Loading writing stats...</div>;
  if (!stats) return <div className="analytics-empty">No data available</div>;

  return (
    <div className="analytics-tab-content">
      <div className="analytics-section">
        <h3 className="analytics-section-title">
          <PenLine size={18} />
          Average Email Length Over Time
        </h3>
        <div className="analytics-chart-container">
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={yearlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="Avg Words" stroke={ACCENT} strokeWidth={2} dot />
              <Line yAxisId="right" type="monotone" dataKey="Email Count" stroke="#34a853" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="analytics-section">
        <h3 className="analytics-section-title">
          <PenLine size={18} />
          Top 50 Words
        </h3>
        <div className="analytics-word-cloud">
          {stats.top_words.slice(0, 50).map((w, i) => {
            const scale = 0.6 + (w.count / maxWordCount) * 1.4;
            const opacity = 0.45 + (w.count / maxWordCount) * 0.55;
            return (
              <span
                key={w.word}
                className="word-cloud-word"
                style={{
                  fontSize: `${scale}rem`,
                  opacity,
                  color: COLORS[i % COLORS.length],
                }}
                title={`${w.word}: ${w.count.toLocaleString()}`}
              >
                {w.word}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Photos Tab ────────────────────────────────────────

function PhotosTab() {
  const [stats, setStats] = useState<PhotoStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPhotoStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const yearlyData = useMemo(() => {
    if (!stats) return [];
    return stats.yearly.map(d => ({
      name: String(d.year),
      Photos: d.count,
      Videos: d.video_count,
    }));
  }, [stats]);

  const cameraData = useMemo(() => {
    if (!stats) return [];
    return stats.cameras.slice(0, 10).map(c => ({
      name: c.model ? `${c.make} ${c.model}`.trim() : c.make || 'Unknown',
      value: c.count,
    }));
  }, [stats]);

  if (loading) return <div className="analytics-loading">Loading photo stats...</div>;
  if (!stats) return <div className="analytics-empty">No data available</div>;

  return (
    <div className="analytics-tab-content">
      <div className="analytics-section">
        <h3 className="analytics-section-title">
          <Camera size={18} />
          Photos &amp; Videos Per Year
        </h3>
        <div className="analytics-chart-container">
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={yearlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Photos" fill={ACCENT} />
              <Bar dataKey="Videos" fill="#34a853" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {cameraData.length > 0 && (
        <div className="analytics-section">
          <h3 className="analytics-section-title">
            <Camera size={18} />
            Camera / Device Breakdown
          </h3>
          <div className="analytics-chart-container analytics-pie-row">
            <div className="analytics-pie-chart">
              <ResponsiveContainer width="100%" height={350}>
                <PieChart>
                  <Pie
                    data={cameraData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={120}
                    label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    labelLine
                  >
                    {cameraData.map((_, idx) => (
                      <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="analytics-pie-legend">
              {cameraData.map((c, i) => (
                <div key={c.name} className="pie-legend-item">
                  <span className="pie-legend-swatch" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                  <span className="pie-legend-name">{c.name}</span>
                  <span className="pie-legend-count">{c.value.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Activity Tab ──────────────────────────────────────

function ActivityTab() {
  const [timeline, setTimeline] = useState<ActivityTimeline | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchActivityTimeline()
      .then(setTimeline)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const data = useMemo(() => {
    if (!timeline) return [];
    return timeline.months.map(m => ({
      name: `${MONTH_NAMES[m.month - 1]} ${m.year}`,
      Emails: m.emails,
      Photos: m.photos,
      Events: m.events,
      Chats: m.chats,
    }));
  }, [timeline]);

  if (loading) return <div className="analytics-loading">Loading activity timeline...</div>;
  if (!timeline) return <div className="analytics-empty">No data available</div>;

  return (
    <div className="analytics-tab-content">
      <div className="analytics-section">
        <h3 className="analytics-section-title">
          <Activity size={18} />
          Unified Activity Timeline
        </h3>
        <div className="analytics-chart-container">
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12 }}
                interval={Math.max(0, Math.floor(data.length / 12) - 1)}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="Emails" stackId="1" stroke="#1a73e8" fill="#1a73e8" fillOpacity={0.4} />
              <Area type="monotone" dataKey="Photos" stackId="1" stroke="#34a853" fill="#34a853" fillOpacity={0.4} />
              <Area type="monotone" dataKey="Events" stackId="1" stroke="#fbbc04" fill="#fbbc04" fillOpacity={0.4} />
              <Area type="monotone" dataKey="Chats" stackId="1" stroke="#673ab7" fill="#673ab7" fillOpacity={0.4} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────

export default function AnalyticsDashboard() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  return (
    <div className="analytics-dashboard">
      <div className="analytics-header">
        <h2 className="analytics-title">Analytics</h2>
        <p className="analytics-subtitle">Explore your Google Archive data</p>
      </div>

      <div className="analytics-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`analytics-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      <div className="analytics-body">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'email' && <EmailTab />}
        {activeTab === 'writing' && <WritingTab />}
        {activeTab === 'photos' && <PhotosTab />}
        {activeTab === 'activity' && <ActivityTab />}
      </div>
    </div>
  );
}
