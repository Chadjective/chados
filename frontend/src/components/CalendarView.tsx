import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ChevronLeft, ChevronRight, CalendarDays, List, Grid3X3,
  MapPin, Clock, X,
} from 'lucide-react';
import { fetchMonthEvents, fetchCalendars } from '../utils/api';
import type { CalendarEvent, CalendarInfo } from '../types';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString([], {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  });
}

export default function CalendarView() {
  const navigate = useNavigate();
  const { year: yearParam, month: monthParam } = useParams<{ year: string; month: string }>();

  const now = new Date();
  // Default to Apr 2018 (busiest month with data) if no params
  const year = yearParam ? parseInt(yearParam, 10) : 2018;
  const month = monthParam ? parseInt(monthParam, 10) : 4;

  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [calendars, setCalendars] = useState<CalendarInfo[]>([]);
  const [enabledCalendars, setEnabledCalendars] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  useEffect(() => {
    fetchCalendars()
      .then((cals) => {
        setCalendars(cals);
        setEnabledCalendars(new Set(cals.map((c) => c.name)));
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchMonthEvents(year, month)
      .then((res) => setEvents(res.events))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [year, month]);

  const filteredEvents = useMemo(
    () => events.filter((e) => enabledCalendars.has(e.calendar_name)),
    [events, enabledCalendars]
  );

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    for (const evt of filteredEvents) {
      const dateKey = evt.start_time.slice(0, 10);
      if (!map[dateKey]) map[dateKey] = [];
      map[dateKey].push(evt);
    }
    return map;
  }, [filteredEvents]);

  const calendarGrid = useMemo(() => {
    const firstDay = new Date(year, month - 1, 1);
    const lastDay = new Date(year, month, 0);
    const startDow = firstDay.getDay();
    const daysInMonth = lastDay.getDate();
    const weeks: (number | null)[][] = [];
    let week: (number | null)[] = new Array(startDow).fill(null);
    for (let d = 1; d <= daysInMonth; d++) {
      week.push(d);
      if (week.length === 7) {
        weeks.push(week);
        week = [];
      }
    }
    if (week.length > 0) {
      while (week.length < 7) week.push(null);
      weeks.push(week);
    }
    return weeks;
  }, [year, month]);

  const goMonth = useCallback(
    (delta: number) => {
      let m = month + delta;
      let y = year;
      if (m < 1) { m = 12; y--; }
      if (m > 12) { m = 1; y++; }
      navigate(`/calendar/${y}/${m}`);
      setSelectedDate(null);
    },
    [year, month, navigate]
  );

  function toggleCalendar(name: string) {
    setEnabledCalendars((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  function dateKey(day: number): string {
    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  const selectedEvents = selectedDate ? eventsByDate[selectedDate] || [] : [];

  return (
    <div className="calendar-container">
      <div className="calendar-header">
        <div className="calendar-nav">
          <button className="calendar-nav-btn" onClick={() => goMonth(-1)}>
            <ChevronLeft size={18} />
          </button>
          <h2 className="calendar-title">
            {MONTH_NAMES[month - 1]} {year}
          </h2>
          <button className="calendar-nav-btn" onClick={() => goMonth(1)}>
            <ChevronRight size={18} />
          </button>
          <button
            className="calendar-today-btn"
            onClick={() => navigate(`/calendar/${now.getFullYear()}/${now.getMonth() + 1}`)}
          >
            Today
          </button>
        </div>
        <div className="calendar-view-toggle">
          <button
            className={`calendar-toggle-btn ${viewMode === 'grid' ? 'active' : ''}`}
            onClick={() => setViewMode('grid')}
          >
            <Grid3X3 size={16} /> Month
          </button>
          <button
            className={`calendar-toggle-btn ${viewMode === 'list' ? 'active' : ''}`}
            onClick={() => setViewMode('list')}
          >
            <List size={16} /> List
          </button>
        </div>
      </div>

      <div className="calendar-body">
        {calendars.length > 0 && (
          <div className="calendar-filters">
            <div className="calendar-filters-title">Calendars</div>
            {calendars.map((cal) => (
              <label key={cal.name} className="calendar-filter-item">
                <input
                  type="checkbox"
                  checked={enabledCalendars.has(cal.name)}
                  onChange={() => toggleCalendar(cal.name)}
                />
                <span>{cal.name}</span>
                <span className="calendar-filter-count">{cal.event_count}</span>
              </label>
            ))}
          </div>
        )}

        <div className="calendar-main">
          {loading ? (
            <div className="calendar-loading">Loading events...</div>
          ) : viewMode === 'grid' ? (
            <div className="calendar-grid-view">
              <div className="calendar-grid">
                <div className="calendar-grid-header">
                  {DAY_NAMES.map((d) => (
                    <div key={d} className="calendar-day-name">{d}</div>
                  ))}
                </div>
                {calendarGrid.map((week, wi) => (
                  <div key={wi} className="calendar-week">
                    {week.map((day, di) => {
                      if (day === null) {
                        return <div key={di} className="calendar-cell empty" />;
                      }
                      const dk = dateKey(day);
                      const dayEvents = eventsByDate[dk] || [];
                      const isToday =
                        day === now.getDate() &&
                        month === now.getMonth() + 1 &&
                        year === now.getFullYear();
                      const isSelected = selectedDate === dk;
                      return (
                        <div
                          key={di}
                          className={`calendar-cell ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''} ${dayEvents.length > 0 ? 'has-events' : ''}`}
                          onClick={() => setSelectedDate(dk)}
                        >
                          <span className="calendar-cell-day">{day}</span>
                          {dayEvents.length > 0 && (
                            <div className="calendar-cell-dots">
                              {dayEvents.slice(0, 3).map((evt) => (
                                <div
                                  key={evt.id}
                                  className="calendar-cell-event"
                                  title={evt.summary}
                                >
                                  {evt.summary}
                                </div>
                              ))}
                              {dayEvents.length > 3 && (
                                <div className="calendar-cell-more">
                                  +{dayEvents.length - 3} more
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>

              {selectedDate && (
                <div className="calendar-day-panel">
                  <div className="calendar-day-panel-header">
                    <h3>{formatDate(selectedDate + 'T00:00:00')}</h3>
                    <button className="calendar-day-panel-close" onClick={() => setSelectedDate(null)}>
                      <X size={16} />
                    </button>
                  </div>
                  {selectedEvents.length === 0 ? (
                    <div className="calendar-day-panel-empty">No events</div>
                  ) : (
                    <div className="calendar-day-panel-events">
                      {selectedEvents.map((evt) => (
                        <div key={evt.id} className="calendar-event-card">
                          <div className="calendar-event-summary">{evt.summary}</div>
                          <div className="calendar-event-time">
                            <Clock size={12} />
                            {evt.is_all_day
                              ? 'All day'
                              : `${formatTime(evt.start_time)} - ${formatTime(evt.end_time)}`}
                          </div>
                          {evt.location && (
                            <div className="calendar-event-location">
                              <MapPin size={12} /> {evt.location}
                            </div>
                          )}
                          {evt.description && (
                            <div className="calendar-event-desc">{evt.description}</div>
                          )}
                          {evt.attendees.length > 0 && (
                            <div className="calendar-event-attendees">
                              {evt.attendees.length} attendee{evt.attendees.length !== 1 ? 's' : ''}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="calendar-list-view">
              {filteredEvents.length === 0 ? (
                <div className="calendar-loading">No events this month</div>
              ) : (
                [...filteredEvents]
                  .sort((a, b) => a.start_time.localeCompare(b.start_time))
                  .map((evt) => (
                    <div key={evt.id} className="calendar-list-item">
                      <div className="calendar-list-date">
                        {new Date(evt.start_time).toLocaleDateString([], {
                          weekday: 'short', month: 'short', day: 'numeric',
                        })}
                      </div>
                      <div className="calendar-list-info">
                        <div className="calendar-list-summary">{evt.summary}</div>
                        <div className="calendar-list-time">
                          <Clock size={12} />
                          {evt.is_all_day
                            ? 'All day'
                            : `${formatTime(evt.start_time)} - ${formatTime(evt.end_time)}`}
                        </div>
                        {evt.location && (
                          <div className="calendar-list-location">
                            <MapPin size={12} /> {evt.location}
                          </div>
                        )}
                      </div>
                      <div className="calendar-list-calendar">{evt.calendar_name}</div>
                    </div>
                  ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
