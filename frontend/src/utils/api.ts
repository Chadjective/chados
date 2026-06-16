import type {
  Email, SearchResult, Label, ThreadDetail, Photo, PhotoSearchResult, TimelineEntry, Album,
  Contact, CalendarEvent, CalendarInfo, ChatConversation, ChatMessage,
  DriveFile, Note, GlobalSearchResult,
  EmailVolume, EmailHeatmap, TopContact, ContactTimeline, WritingStats,
  ArchiveOverview, OnThisDay, ActivityTimeline, PhotoStats,
  AIChatStatus, AISource, RelatedResponse,
  UserTag, TrashItem, SmartFilter, SpaceAnalysis,
  ImportDrive, ImportJob,
} from '../types';

const API_BASE = '/api';

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function fetchEmails(params: {
  label?: string;
  offset?: number;
  limit?: number;
}): Promise<SearchResult> {
  const sp = new URLSearchParams();
  if (params.label) sp.set('label', params.label);
  if (params.offset !== undefined) sp.set('offset', String(params.offset));
  if (params.limit !== undefined) sp.set('limit', String(params.limit));
  return fetchJSON<SearchResult>(`${API_BASE}/emails?${sp.toString()}`);
}

export async function fetchEmail(id: number): Promise<Email> {
  return fetchJSON<Email>(`${API_BASE}/emails/${id}`);
}

export async function fetchThread(id: number): Promise<ThreadDetail> {
  return fetchJSON<ThreadDetail>(`${API_BASE}/emails/${id}/thread`);
}

export async function searchEmails(
  query: string,
  offset = 0,
  limit = 50
): Promise<SearchResult> {
  const sp = new URLSearchParams();
  sp.set('q', query);
  sp.set('offset', String(offset));
  sp.set('limit', String(limit));
  return fetchJSON<SearchResult>(`${API_BASE}/emails/search?${sp.toString()}`);
}

export async function fetchLabels(): Promise<Label[]> {
  return fetchJSON<Label[]>(`${API_BASE}/labels`);
}

export function getAttachmentUrl(id: number): string {
  return `${API_BASE}/attachments/${id}`;
}

// ── Photo API ──────────────────────────────────────────

export async function fetchPhotos(params: {
  year?: number;
  month?: number;
  media_type?: string;
  favorite?: boolean;
  album?: string;
  offset?: number;
  limit?: number;
}): Promise<PhotoSearchResult> {
  const sp = new URLSearchParams();
  if (params.year !== undefined) sp.set('year', String(params.year));
  if (params.month !== undefined) sp.set('month', String(params.month));
  if (params.media_type) sp.set('media_type', params.media_type);
  if (params.favorite !== undefined) sp.set('favorite', String(params.favorite));
  if (params.album) sp.set('album', params.album);
  if (params.offset !== undefined) sp.set('offset', String(params.offset));
  if (params.limit !== undefined) sp.set('limit', String(params.limit));
  return fetchJSON<PhotoSearchResult>(`${API_BASE}/photos?${sp.toString()}`);
}

export async function fetchPhoto(id: number): Promise<Photo> {
  return fetchJSON<Photo>(`${API_BASE}/photos/${id}`);
}

export async function fetchPhotoTimeline(): Promise<TimelineEntry[]> {
  return fetchJSON<TimelineEntry[]>(`${API_BASE}/photos/timeline`);
}

export async function fetchAlbums(): Promise<Album[]> {
  return fetchJSON<Album[]>(`${API_BASE}/photos/albums`);
}

export async function fetchAlbumPhotos(
  albumId: number,
  offset = 0,
  limit = 50
): Promise<{ album: Album; photos: Photo[]; total: number }> {
  const sp = new URLSearchParams();
  sp.set('offset', String(offset));
  sp.set('limit', String(limit));
  return fetchJSON<{ album: Album; photos: Photo[]; total: number }>(
    `${API_BASE}/photos/albums/${albumId}?${sp.toString()}`
  );
}

export async function searchPhotos(
  query: string,
  offset = 0,
  limit = 50
): Promise<PhotoSearchResult> {
  const sp = new URLSearchParams();
  sp.set('q', query);
  sp.set('offset', String(offset));
  sp.set('limit', String(limit));
  return fetchJSON<PhotoSearchResult>(`${API_BASE}/photos/search?${sp.toString()}`);
}

export function getPhotoThumbnailUrl(id: number): string {
  return `${API_BASE}/photos/${id}/thumbnail`;
}

export function getPhotoFullUrl(id: number): string {
  return `${API_BASE}/photos/${id}/full`;
}

// ── Contacts API ──────────────────────────────────────

export async function fetchContacts(params: {
  offset?: number;
  limit?: number;
  group?: string;
} = {}): Promise<{ contacts: Contact[]; total: number }> {
  const sp = new URLSearchParams();
  if (params.offset !== undefined) sp.set('offset', String(params.offset));
  if (params.limit !== undefined) sp.set('limit', String(params.limit));
  if (params.group) sp.set('group', params.group);
  return fetchJSON<{ contacts: Contact[]; total: number }>(`${API_BASE}/contacts?${sp.toString()}`);
}

export async function fetchContact(id: number): Promise<Contact> {
  return fetchJSON<Contact>(`${API_BASE}/contacts/${id}`);
}

export async function searchContacts(
  query: string,
  offset = 0,
  limit = 50
): Promise<{ contacts: Contact[]; total: number }> {
  const sp = new URLSearchParams();
  sp.set('q', query);
  sp.set('offset', String(offset));
  sp.set('limit', String(limit));
  return fetchJSON<{ contacts: Contact[]; total: number }>(`${API_BASE}/contacts/search?${sp.toString()}`);
}

export async function fetchContactGroups(): Promise<string[]> {
  const res = await fetchJSON<{ groups: { name: string; count: number }[]; total: number }>(`${API_BASE}/contacts/groups`);
  return res.groups.map(g => g.name);
}

// ── Calendar API ──────────────────────────────────────

export async function fetchCalendarEvents(params: {
  calendar?: string;
  start_date?: string;
  end_date?: string;
  offset?: number;
  limit?: number;
} = {}): Promise<{ events: CalendarEvent[]; total: number }> {
  const sp = new URLSearchParams();
  if (params.calendar) sp.set('calendar', params.calendar);
  if (params.start_date) sp.set('start_date', params.start_date);
  if (params.end_date) sp.set('end_date', params.end_date);
  if (params.offset !== undefined) sp.set('offset', String(params.offset));
  if (params.limit !== undefined) sp.set('limit', String(params.limit));
  return fetchJSON<{ events: CalendarEvent[]; total: number }>(`${API_BASE}/calendar/events?${sp.toString()}`);
}

export async function fetchMonthEvents(
  year: number,
  month: number
): Promise<{ events: CalendarEvent[]; total: number }> {
  return fetchJSON<{ events: CalendarEvent[]; total: number }>(
    `${API_BASE}/calendar/month/${year}/${month}`
  );
}

export async function fetchCalendars(): Promise<CalendarInfo[]> {
  const res = await fetchJSON<{ calendars: CalendarInfo[]; total: number }>(`${API_BASE}/calendar/calendars`);
  return res.calendars;
}

// ── Chat API ──────────────────────────────────────────

export async function fetchConversations(params: {
  offset?: number;
  limit?: number;
} = {}): Promise<{ conversations: ChatConversation[]; total: number }> {
  const sp = new URLSearchParams();
  if (params.offset !== undefined) sp.set('offset', String(params.offset));
  if (params.limit !== undefined) sp.set('limit', String(params.limit));
  return fetchJSON<{ conversations: ChatConversation[]; total: number }>(`${API_BASE}/chat/conversations?${sp.toString()}`);
}

export async function fetchConversation(
  id: number,
  offset = 0,
  limit = 100
): Promise<{ conversation: ChatConversation; messages: ChatMessage[]; total: number }> {
  const sp = new URLSearchParams();
  sp.set('offset', String(offset));
  sp.set('limit', String(limit));
  return fetchJSON<{ conversation: ChatConversation; messages: ChatMessage[]; total: number }>(
    `${API_BASE}/chat/conversations/${id}?${sp.toString()}`
  );
}

export async function searchChat(
  query: string,
  offset = 0,
  limit = 50
): Promise<{ messages: ChatMessage[]; total: number }> {
  const sp = new URLSearchParams();
  sp.set('q', query);
  sp.set('offset', String(offset));
  sp.set('limit', String(limit));
  return fetchJSON<{ messages: ChatMessage[]; total: number }>(`${API_BASE}/chat/search?${sp.toString()}`);
}

// ── Drive API ─────────────────────────────────────────

export async function fetchDriveFiles(params: {
  path?: string;
  offset?: number;
  limit?: number;
} = {}): Promise<{ files: DriveFile[]; total: number }> {
  const sp = new URLSearchParams();
  if (params.path !== undefined) sp.set('parent_path', params.path);
  if (params.offset !== undefined) sp.set('offset', String(params.offset));
  if (params.limit !== undefined) sp.set('limit', String(params.limit));
  return fetchJSON<{ files: DriveFile[]; total: number }>(`${API_BASE}/drive/files?${sp.toString()}`);
}

export async function fetchDriveFile(id: number): Promise<DriveFile> {
  return fetchJSON<DriveFile>(`${API_BASE}/drive/files/${id}`);
}

export async function fetchDriveFolders(): Promise<string[]> {
  const res = await fetchJSON<{ folders: string[]; total: number }>(`${API_BASE}/drive/folders`);
  return res.folders;
}

export async function searchDrive(
  query: string,
  offset = 0,
  limit = 50
): Promise<{ files: DriveFile[]; total: number }> {
  const sp = new URLSearchParams();
  sp.set('q', query);
  sp.set('offset', String(offset));
  sp.set('limit', String(limit));
  return fetchJSON<{ files: DriveFile[]; total: number }>(`${API_BASE}/drive/search?${sp.toString()}`);
}

export function getDriveFilePreviewUrl(id: number): string {
  return `${API_BASE}/drive/files/${id}/preview`;
}

// ── Notes API ─────────────────────────────────────────

export async function fetchNotes(params: {
  label?: string;
  archived?: boolean;
  offset?: number;
  limit?: number;
} = {}): Promise<{ notes: Note[]; total: number }> {
  const sp = new URLSearchParams();
  if (params.label) sp.set('label', params.label);
  if (params.archived !== undefined) sp.set('archived', String(params.archived));
  if (params.offset !== undefined) sp.set('offset', String(params.offset));
  if (params.limit !== undefined) sp.set('limit', String(params.limit));
  return fetchJSON<{ notes: Note[]; total: number }>(`${API_BASE}/notes?${sp.toString()}`);
}

export async function fetchNote(id: number): Promise<Note> {
  return fetchJSON<Note>(`${API_BASE}/notes/${id}`);
}

export async function fetchNoteLabels(): Promise<string[]> {
  return fetchJSON<string[]>(`${API_BASE}/notes/labels`);
}

// ── Global Search API ─────────────────────────────────

export async function globalSearch(query: string): Promise<GlobalSearchResult> {
  const sp = new URLSearchParams();
  sp.set('q', query);
  return fetchJSON<GlobalSearchResult>(`${API_BASE}/search?${sp.toString()}`);
}

// ── Analytics API ─────────────────────────────────────

export async function fetchEmailVolume(): Promise<EmailVolume> {
  return fetchJSON<EmailVolume>(`${API_BASE}/analytics/email-volume`);
}

export async function fetchEmailHeatmap(): Promise<EmailHeatmap> {
  return fetchJSON<EmailHeatmap>(`${API_BASE}/analytics/email-heatmap`);
}

export async function fetchTopContacts(limit = 20): Promise<TopContact[]> {
  const data = await fetchJSON<{ contacts: TopContact[] }>(`${API_BASE}/analytics/top-contacts?limit=${limit}`);
  return data.contacts;
}

export async function fetchContactTimeline(address: string): Promise<ContactTimeline> {
  const sp = new URLSearchParams();
  sp.set('address', address);
  return fetchJSON<ContactTimeline>(`${API_BASE}/analytics/contact-timeline?${sp.toString()}`);
}

export async function fetchWritingStats(): Promise<WritingStats> {
  return fetchJSON<WritingStats>(`${API_BASE}/analytics/writing-stats`);
}

export async function fetchArchiveOverview(): Promise<ArchiveOverview> {
  // Transform API response shape to match frontend types
  const raw = await fetchJSON<Record<string, any>>(`${API_BASE}/analytics/overview`);
  function dateRange(earliest?: string, latest?: string): string {
    if (!earliest || !latest) return '';
    const fmt = (d: string) => new Date(d).getFullYear().toString();
    return `${fmt(earliest)} – ${fmt(latest)}`;
  }
  return {
    email: { total: raw.email?.count ?? 0, date_range: dateRange(raw.email?.earliest, raw.email?.latest) },
    photos: { total: raw.photos?.count ?? 0, date_range: raw.photos?.videos ? `${raw.photos.videos} videos` : '' },
    calendar: { total: raw.calendar?.count ?? 0, date_range: dateRange(raw.calendar?.earliest, raw.calendar?.latest) },
    contacts: { total: raw.contacts?.count ?? 0 },
    chat: { total: raw.chat?.messages ?? 0, date_range: `${raw.chat?.conversations ?? 0} conversations` },
    drive: { total: raw.drive?.count ?? 0 },
  };
}

export async function fetchOnThisDay(): Promise<OnThisDay> {
  const now = new Date();
  return fetchJSON<OnThisDay>(`${API_BASE}/analytics/on-this-day?month=${now.getMonth() + 1}&day=${now.getDate()}`);
}

export async function fetchActivityTimeline(): Promise<ActivityTimeline> {
  return fetchJSON<ActivityTimeline>(`${API_BASE}/analytics/activity-timeline`);
}

export async function fetchPhotoStats(): Promise<PhotoStats> {
  return fetchJSON<PhotoStats>(`${API_BASE}/analytics/photo-stats`);
}

// ── Related Items API ─────────────────────────────────

export async function fetchRelated(type: string, id: number): Promise<RelatedResponse> {
  const sp = new URLSearchParams();
  sp.set('type', type);
  sp.set('id', String(id));
  return fetchJSON<RelatedResponse>(`${API_BASE}/related?${sp.toString()}`);
}

// ── AI Chat API ──────────────────────────────────────

export async function fetchAIStatus(): Promise<AIChatStatus> {
  return fetchJSON<AIChatStatus>(`${API_BASE}/ai/status`);
}

export async function fetchAISuggestions(): Promise<string[]> {
  const res = await fetchJSON<{ suggestions: string[] }>(`${API_BASE}/ai/suggest`);
  return res.suggestions;
}

export interface AIStreamCallbacks {
  onToken: (token: string) => void;
  onDone: (sources: AISource[]) => void;
  onError: (error: string) => void;
}

export async function sendAIMessage(
  message: string,
  conversationHistory: { role: string; content: string }[],
  scope: string[] | null,
  callbacks: AIStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const resp = await fetch(`${API_BASE}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        conversation_history: conversationHistory,
        scope: scope,
      }),
      signal,
    });

    if (!resp.ok) {
      callbacks.onError(`API error: ${resp.status} ${resp.statusText}`);
      return;
    }

    const reader = resp.body?.getReader();
    if (!reader) {
      callbacks.onError('No response body');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) continue;
        const jsonStr = trimmed.slice(6);
        if (!jsonStr) continue;

        try {
          const data = JSON.parse(jsonStr);
          if (data.error) {
            callbacks.onError(data.error);
            return;
          }
          if (data.token) {
            callbacks.onToken(data.token);
          }
          if (data.done) {
            callbacks.onDone(data.sources || []);
            return;
          }
        } catch {
          // skip malformed JSON lines
        }
      }
    }

    // If we get here without a done event, still signal done
    callbacks.onDone([]);
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      return;
    }
    callbacks.onError(err instanceof Error ? err.message : 'Unknown error');
  }
}

// ── Actions API ──────────────────────────────────────

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function deleteJSON<T>(url: string): Promise<T> {
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

async function putJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

export async function softDelete(itemType: string, itemIds: number[]): Promise<{ deleted: number }> {
  return postJSON(`${API_BASE}/actions/delete`, { item_type: itemType, item_ids: itemIds });
}

export async function permanentDelete(itemType: string, itemIds: number[]): Promise<{ deleted: number; space_freed_bytes: number; files_removed: number }> {
  return postJSON(`${API_BASE}/actions/delete`, { item_type: itemType, item_ids: itemIds, permanent: true });
}

export async function restoreItems(itemType: string, itemIds: number[]): Promise<{ restored: number }> {
  return postJSON(`${API_BASE}/actions/restore`, { item_type: itemType, item_ids: itemIds });
}

export async function toggleStar(itemIds: number[], starred: boolean): Promise<{ updated: number }> {
  return postJSON(`${API_BASE}/actions/star`, { item_ids: itemIds, starred });
}

export async function markRead(itemIds: number[], read: boolean): Promise<{ updated: number }> {
  return postJSON(`${API_BASE}/actions/mark-read`, { item_ids: itemIds, read });
}

export async function modifyLabels(itemIds: number[], addLabels: string[], removeLabels: string[]): Promise<{ updated: number }> {
  return postJSON(`${API_BASE}/actions/label`, { item_ids: itemIds, add_labels: addLabels, remove_labels: removeLabels });
}

export async function tagItems(itemType: string, itemIds: number[], tagId: number): Promise<{ tagged: number }> {
  return postJSON(`${API_BASE}/actions/tag`, { item_type: itemType, item_ids: itemIds, tag_id: tagId });
}

export async function untagItems(itemType: string, itemIds: number[], tagId: number): Promise<{ untagged: number }> {
  return postJSON(`${API_BASE}/actions/untag`, { item_type: itemType, item_ids: itemIds, tag_id: tagId });
}

export async function fetchTrash(itemType: string = 'email', offset = 0, limit = 50): Promise<{ items: TrashItem[]; total: number; total_size_bytes: number }> {
  const sp = new URLSearchParams({ item_type: itemType, offset: String(offset), limit: String(limit) });
  return fetchJSON(`${API_BASE}/actions/trash?${sp.toString()}`);
}

export async function emptyTrash(itemType: string = 'all'): Promise<{ permanently_deleted: number; space_freed_bytes: number }> {
  return postJSON(`${API_BASE}/actions/empty-trash`, { item_type: itemType });
}

export async function fetchSpaceAnalysis(): Promise<SpaceAnalysis> {
  return fetchJSON(`${API_BASE}/actions/space-analysis`);
}

export async function fetchSmartFilters(): Promise<{ filters: SmartFilter[] }> {
  return fetchJSON(`${API_BASE}/smart-filters`);
}

// ── Tags API ─────────────────────────────────────────

export async function fetchTags(): Promise<{ tags: UserTag[] }> {
  return fetchJSON(`${API_BASE}/tags`);
}

export async function createTag(name: string, color: string): Promise<UserTag> {
  return postJSON(`${API_BASE}/tags`, { name, color });
}

export async function updateTag(tagId: number, updates: { name?: string; color?: string }): Promise<UserTag> {
  return putJSON(`${API_BASE}/tags/${tagId}`, updates);
}

export async function deleteTag(tagId: number): Promise<{ deleted: boolean }> {
  return deleteJSON(`${API_BASE}/tags/${tagId}`);
}

export async function searchEmailsCountOnly(query: string): Promise<{ total: number; total_size_bytes: number }> {
  const sp = new URLSearchParams({ q: query, count_only: 'true' });
  return fetchJSON(`${API_BASE}/emails/search?${sp.toString()}`);
}

// ── Photo import (v4) ────────────────────────────────

export async function fetchImportDrives(): Promise<{ drives: ImportDrive[] }> {
  return fetchJSON(`${API_BASE}/photos/import/drives`);
}

export async function startFolderImport(
  path: string, recursive: boolean, label?: string,
): Promise<{ job_id: number }> {
  return postJSON(`${API_BASE}/photos/import/folder`, { path, recursive, label });
}

export async function fetchImportJobs(): Promise<{ jobs: ImportJob[] }> {
  return fetchJSON(`${API_BASE}/photos/import/jobs`);
}

export async function fetchImportJob(jobId: number): Promise<ImportJob> {
  return fetchJSON(`${API_BASE}/photos/import/jobs/${jobId}`);
}

export async function cancelImportJob(jobId: number): Promise<{ cancelled: boolean }> {
  return postJSON(`${API_BASE}/photos/import/jobs/${jobId}/cancel`, {});
}
