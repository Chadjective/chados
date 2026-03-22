export interface Email {
  id: number;
  message_id: string | null;
  thread_id: string | null;
  from_name: string | null;
  from_address: string | null;
  to_addresses: AddressEntry[];
  cc_addresses: AddressEntry[];
  subject: string | null;
  date: string | null;
  body_text: string | null;
  body_html: string | null;
  labels: string[];
  has_attachments: boolean;
  is_read: boolean;
  is_starred: boolean;
  snippet: string | null;
  attachments: Attachment[];
}

export interface EmailSummary {
  id: number;
  message_id: string | null;
  thread_id: string | null;
  from_address: string | null;
  from_name: string | null;
  subject: string | null;
  date: string | null;
  snippet: string | null;
  labels: string[];
  has_attachments: boolean;
  is_read: boolean;
  is_starred: boolean;
}

export interface AddressEntry {
  name: string;
  address: string;
}

export interface Label {
  id: number;
  name: string;
  email_count: number;
}

export interface Attachment {
  id: number;
  email_id: number;
  filename: string | null;
  content_type: string | null;
  size_bytes: number;
}

export interface SearchResult {
  emails: EmailSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ThreadDetail {
  thread_id: string;
  subject: string | null;
  messages: Email[];
  message_count: number;
}

export interface Photo {
  id: number;
  filename: string;
  title: string;
  description: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  size_bytes: number;
  date_taken: string | null;
  date_taken_unix: number | null;
  latitude: number | null;
  longitude: number | null;
  camera_make: string | null;
  camera_model: string | null;
  device_type: string | null;
  is_video: boolean;
  duration_seconds: number | null;
  is_favorite: boolean;
  source_album: string | null;
  has_thumbnail: boolean;
}

export interface Album {
  id: number;
  name: string;
  photo_count: number;
  cover_photo_id: number | null;
  has_cover_thumbnail: boolean;
}

export interface TimelineEntry {
  year: number;
  month: number;
  count: number;
}

export interface PhotoSearchResult {
  photos: Photo[];
  total: number;
}

// ── Contacts ──────────────────────────────────────────

export interface ContactEmail {
  type: string;
  address: string;
}

export interface ContactPhone {
  type: string;
  number: string;
}

export interface Contact {
  id: number;
  name: string;
  given_name: string | null;
  family_name: string | null;
  emails: ContactEmail[];
  phones: ContactPhone[];
  organization: string | null;
  title: string | null;
  notes: string | null;
  groups: string[];
  has_photo?: boolean;
}

// ── Calendar ──────────────────────────────────────────

export interface CalendarEvent {
  id: number;
  calendar_name: string;
  summary: string;
  description: string | null;
  location: string | null;
  start_time: string;
  end_time: string;
  is_all_day: boolean;
  recurrence: string | null;
  organizer: string | null;
  attendees: string[];
  status: string | null;
}

export interface CalendarInfo {
  name: string;
  event_count: number;
}

// ── Chat ──────────────────────────────────────────────

export interface ChatParticipant {
  name: string;
  email: string;
}

export interface ChatConversation {
  id: number;
  name: string;
  participants: ChatParticipant[];
  type: string | null;
  message_count?: number;
  last_message_time?: string | null;
  last_message_preview?: string | null;
  last_message?: {
    sender_name: string;
    content: string;
    timestamp: string;
  } | null;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  sender_name: string;
  sender_email: string | null;
  content: string;
  timestamp: string;
  message_type: string | null;
}

// ── Drive ─────────────────────────────────────────────

export interface DriveFile {
  id: number;
  filename: string;
  path: string;
  parent_path: string | null;
  mime_type: string | null;
  size_bytes: number;
  modified_time: string | null;
  is_folder: boolean;
  extracted_text: string | null;
}

// ── Notes ─────────────────────────────────────────────

export interface Note {
  id: number;
  title: string;
  content: string | null;
  color: string | null;
  labels: string[];
  is_archived: boolean;
  is_pinned: boolean;
  created_time: string | null;
  modified_time: string | null;
}

// ── Global Search ─────────────────────────────────────

export interface GlobalSearchResultSection<T> {
  items: T[];
  total: number;
}

export interface GlobalSearchResult {
  emails: GlobalSearchResultSection<EmailSummary>;
  photos: GlobalSearchResultSection<Photo>;
  contacts: GlobalSearchResultSection<Contact>;
  calendar: GlobalSearchResultSection<CalendarEvent>;
  chat: GlobalSearchResultSection<ChatConversation>;
  drive: GlobalSearchResultSection<DriveFile>;
  notes: GlobalSearchResultSection<Note>;
}

// ── Analytics ────────────────────────────────────────

export interface EmailVolume {
  yearly: { year: number; count: number }[];
  monthly: { year: number; month: number; count: number }[];
}

export interface EmailHeatmap {
  heatmap: number[][];
}

export interface TopContact {
  name: string;
  address: string;
  sent_count: number;
  received_count: number;
  total: number;
  last_contact: string;
}

export interface ContactTimeline {
  address: string;
  name: string;
  months: { year: number; month: number; sent: number; received: number }[];
}

export interface WritingStats {
  yearly: { year: number; avg_length: number; avg_words: number; email_count: number }[];
  top_words: { word: string; count: number }[];
}

export interface ArchiveOverview {
  email: { total: number; date_range: string };
  photos: { total: number; date_range: string };
  calendar: { total: number; date_range: string };
  contacts: { total: number };
  chat: { total: number; date_range: string };
  drive: { total: number };
}

export interface OnThisDayEmail { id: number; subject: string; from_name: string; date: string; }
export interface OnThisDayPhoto { id: number; filename: string; thumbnail_path: string; }
export interface OnThisDayEvent { id: number; summary: string; }
export interface OnThisDayYear { year: number; emails: OnThisDayEmail[]; photos: OnThisDayPhoto[]; events: OnThisDayEvent[]; }
export interface OnThisDay {
  years: OnThisDayYear[];
}

export interface ActivityTimeline {
  months: { year: number; month: number; emails: number; photos: number; events: number; chats: number }[];
}

export interface PhotoStats {
  yearly: { year: number; count: number; video_count: number }[];
  cameras: { make: string; model: string; count: number }[];
}

// ── AI Chat ──────────────────────────────────────────

export interface AIChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: AISource[];
  isStreaming?: boolean;
  error?: string;
}

export interface AISource {
  type: string;
  id: string;
  title: string;
  date: string | null;
  relevance_score: number;
}

export interface AIChatStatus {
  ollama_available: boolean;
  model_loaded: boolean;
  chroma_ready: boolean;
  embedded_count: number;
}

// ── Related Items ────────────────────────────────────

export interface RelatedSource {
  type: string;
  id: number;
  date: string | null;
}

export interface RelatedEmail {
  id: number;
  subject: string | null;
  from_name: string | null;
  date: string | null;
}

export interface RelatedPhoto {
  id: number;
  filename: string | null;
  date_taken: string | null;
  thumbnail_path: string | null;
}

export interface RelatedEvent {
  id: number;
  summary: string | null;
  start_time: string | null;
  location: string | null;
}

export interface RelatedContact {
  id: number;
  name: string | null;
  emails: { type?: string; address?: string }[];
}

export interface RelatedChat {
  id: number;
  conversation_id: number;
  sender_name: string | null;
  content: string | null;
  timestamp: string | null;
}

export interface RelatedDrive {
  id: number;
  filename: string | null;
  path: string | null;
  mime_type: string | null;
}

export interface RelatedItems {
  emails: RelatedEmail[];
  photos: RelatedPhoto[];
  events: RelatedEvent[];
  contacts: RelatedContact[];
  chats: RelatedChat[];
  drive: RelatedDrive[];
}

export interface RelatedResponse {
  source: RelatedSource;
  related: RelatedItems;
}
