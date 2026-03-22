from pydantic import BaseModel
from typing import Optional, List
import json


class EmailSummary(BaseModel):
    id: int
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[str] = None
    snippet: Optional[str] = None
    labels: List[str] = []
    has_attachments: bool = False
    is_read: bool = True
    is_starred: bool = False

    @classmethod
    def from_row(cls, row):
        labels = []
        if row["labels"]:
            try:
                labels = json.loads(row["labels"])
            except (json.JSONDecodeError, TypeError):
                pass
        snippet = ""
        if row.get("body_text"):
            snippet = row["body_text"][:200].replace("\n", " ").strip()
        return cls(
            id=row["id"],
            message_id=row["message_id"],
            thread_id=row["thread_id"],
            from_address=row["from_address"],
            from_name=row["from_name"],
            subject=row["subject"],
            date=row["date"],
            snippet=snippet,
            labels=labels,
            has_attachments=bool(row["has_attachments"]),
            is_read=bool(row["is_read"]),
            is_starred=bool(row["is_starred"]),
        )


class EmailDetail(BaseModel):
    id: int
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    to_addresses: list = []
    cc_addresses: list = []
    bcc_addresses: list = []
    subject: Optional[str] = None
    date: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    labels: List[str] = []
    has_attachments: bool = False
    is_read: bool = True
    is_starred: bool = False
    raw_size_bytes: int = 0
    attachments: list = []

    @classmethod
    def from_row(cls, row, attachments=None):
        def parse_json(val):
            if not val:
                return []
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return []

        return cls(
            id=row["id"],
            message_id=row["message_id"],
            thread_id=row["thread_id"],
            from_address=row["from_address"],
            from_name=row["from_name"],
            to_addresses=parse_json(row["to_addresses"]),
            cc_addresses=parse_json(row["cc_addresses"]),
            bcc_addresses=parse_json(row["bcc_addresses"]),
            subject=row["subject"],
            date=row["date"],
            body_text=row["body_text"],
            body_html=row["body_html"],
            labels=parse_json(row["labels"]),
            has_attachments=bool(row["has_attachments"]),
            is_read=bool(row["is_read"]),
            is_starred=bool(row["is_starred"]),
            raw_size_bytes=row["raw_size_bytes"] or 0,
            attachments=attachments or [],
        )


class AttachmentInfo(BaseModel):
    id: int
    email_id: int
    filename: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: int = 0


class LabelInfo(BaseModel):
    id: int
    name: str
    email_count: int = 0


class SearchResult(BaseModel):
    emails: List[EmailSummary]
    total: int
    page: int
    page_size: int


class ThreadDetail(BaseModel):
    thread_id: str
    subject: Optional[str] = None
    messages: List[EmailDetail] = []
    message_count: int = 0


# ---------------------------------------------------------------------------
# Phase 3: Contacts
# ---------------------------------------------------------------------------

class ContactEmail(BaseModel):
    type: Optional[str] = None
    address: Optional[str] = None


class ContactPhone(BaseModel):
    type: Optional[str] = None
    number: Optional[str] = None


class ContactSummary(BaseModel):
    id: int
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    emails: List[ContactEmail] = []
    phones: List[ContactPhone] = []
    organization: Optional[str] = None
    title: Optional[str] = None
    groups: List[str] = []
    has_photo: bool = False


class ContactDetail(ContactSummary):
    notes: Optional[str] = None
    photo_path: Optional[str] = None
    source_file: Optional[str] = None


class ContactGroup(BaseModel):
    name: str
    count: int


# ---------------------------------------------------------------------------
# Phase 3: Calendar
# ---------------------------------------------------------------------------

class EventAttendee(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None


class EventSummary(BaseModel):
    id: int
    calendar_name: Optional[str] = None
    summary: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_all_day: bool = False
    status: Optional[str] = None


class EventDetail(EventSummary):
    uid: Optional[str] = None
    description: Optional[str] = None
    start_unix: Optional[int] = None
    end_unix: Optional[int] = None
    recurrence: Optional[str] = None
    organizer: Optional[str] = None
    attendees: List[EventAttendee] = []
    source_file: Optional[str] = None


class CalendarInfo(BaseModel):
    name: Optional[str] = None
    event_count: int = 0


# ---------------------------------------------------------------------------
# Phase 3: Chat
# ---------------------------------------------------------------------------

class ChatParticipant(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class ChatMessagePreview(BaseModel):
    sender_name: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None


class ChatMessage(BaseModel):
    id: int
    conversation_id: int
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None
    message_type: Optional[str] = "text"


class ConversationSummary(BaseModel):
    id: int
    name: Optional[str] = None
    participants: List[ChatParticipant] = []
    type: Optional[str] = None
    last_message: Optional[ChatMessagePreview] = None


class ConversationDetail(BaseModel):
    id: int
    name: Optional[str] = None
    participants: List[ChatParticipant] = []
    type: Optional[str] = None
    source_folder: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 3: Drive
# ---------------------------------------------------------------------------

class DriveFileSummary(BaseModel):
    id: int
    filename: Optional[str] = None
    path: Optional[str] = None
    parent_path: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: int = 0
    modified_time: Optional[str] = None
    is_folder: bool = False


class DriveFileDetail(DriveFileSummary):
    extracted_text: Optional[str] = None
    source_file: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 3: Notes (Google Keep)
# ---------------------------------------------------------------------------

class NoteSummary(BaseModel):
    id: int
    title: Optional[str] = None
    snippet: Optional[str] = None
    color: Optional[str] = None
    labels: List[str] = []
    is_archived: bool = False
    is_pinned: bool = False
    is_trashed: bool = False
    created_time: Optional[str] = None
    modified_time: Optional[str] = None


class NoteDetail(BaseModel):
    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    color: Optional[str] = None
    labels: List[str] = []
    is_archived: bool = False
    is_pinned: bool = False
    is_trashed: bool = False
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    source_file: Optional[str] = None


class NoteLabel(BaseModel):
    name: str
    count: int


# ---------------------------------------------------------------------------
# Global Search
# ---------------------------------------------------------------------------

class GlobalSearchItem(BaseModel):
    id: int
    title: Optional[str] = None
    subtitle: Optional[str] = None
    date: Optional[str] = None
    snippet: Optional[str] = None
    type: str
    conversation_id: Optional[int] = None
    color: Optional[str] = None


class GlobalSearchSection(BaseModel):
    total: int
    items: List[GlobalSearchItem] = []


class GlobalSearchResult(BaseModel):
    query: str
    total_results: int
    results: dict = {}


# ---------------------------------------------------------------------------
# Phase 4: Analytics
# ---------------------------------------------------------------------------

class YearlyEmailVolume(BaseModel):
    year: int
    count: int


class MonthlyEmailVolume(BaseModel):
    year: int
    month: int
    count: int


class EmailVolumeResponse(BaseModel):
    yearly: List[YearlyEmailVolume] = []
    monthly: List[MonthlyEmailVolume] = []


class EmailHeatmapResponse(BaseModel):
    heatmap: List[List[int]] = []  # 7x24 grid: [day_of_week][hour]


class TopContact(BaseModel):
    name: Optional[str] = None
    address: str
    sent_count: int = 0
    received_count: int = 0
    total: int = 0
    last_contact: Optional[str] = None


class TopContactsResponse(BaseModel):
    contacts: List[TopContact] = []


class ContactMonth(BaseModel):
    year: int
    month: int
    sent: int = 0
    received: int = 0


class ContactTimelineResponse(BaseModel):
    address: str
    name: Optional[str] = None
    months: List[ContactMonth] = []


class ResponseTimeBucket(BaseModel):
    label: str
    count: int = 0


class ResponseTimesResponse(BaseModel):
    buckets: List[ResponseTimeBucket] = []
    average_hours: Optional[float] = None


class YearlyWritingStats(BaseModel):
    year: int
    avg_length: float = 0.0
    avg_words: float = 0.0
    email_count: int = 0


class WordFrequency(BaseModel):
    word: str
    count: int


class WritingStatsResponse(BaseModel):
    yearly: List[YearlyWritingStats] = []
    top_words: List[WordFrequency] = []


class DataTypeOverview(BaseModel):
    count: int = 0
    size_bytes: int = 0
    earliest: Optional[str] = None
    latest: Optional[str] = None


class PhotoOverview(BaseModel):
    count: int = 0
    size_bytes: int = 0
    videos: int = 0


class ChatOverview(BaseModel):
    conversations: int = 0
    messages: int = 0


class DriveOverview(BaseModel):
    count: int = 0
    size_bytes: int = 0


class ContactsOverview(BaseModel):
    count: int = 0


class CalendarOverview(BaseModel):
    count: int = 0
    earliest: Optional[str] = None
    latest: Optional[str] = None


class OverviewResponse(BaseModel):
    email: Optional[DataTypeOverview] = None
    photos: Optional[PhotoOverview] = None
    calendar: Optional[CalendarOverview] = None
    contacts: Optional[ContactsOverview] = None
    chat: Optional[ChatOverview] = None
    drive: Optional[DriveOverview] = None


class OnThisDayEmail(BaseModel):
    id: int
    subject: Optional[str] = None
    from_name: Optional[str] = None
    date: Optional[str] = None


class OnThisDayPhoto(BaseModel):
    id: int
    filename: Optional[str] = None
    thumbnail_path: Optional[str] = None


class OnThisDayEvent(BaseModel):
    id: int
    summary: Optional[str] = None


class OnThisDayYear(BaseModel):
    year: int
    emails: List[OnThisDayEmail] = []
    photos: List[OnThisDayPhoto] = []
    events: List[OnThisDayEvent] = []


class OnThisDayResponse(BaseModel):
    years: List[OnThisDayYear] = []


class MonthlyActivity(BaseModel):
    year: int
    month: int
    emails: int = 0
    photos: int = 0
    events: int = 0
    chats: int = 0


class ActivityTimelineResponse(BaseModel):
    months: List[MonthlyActivity] = []


class YearlyPhotoStats(BaseModel):
    year: int
    count: int = 0
    video_count: int = 0


class CameraStats(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    count: int = 0


class PhotoStatsResponse(BaseModel):
    yearly: List[YearlyPhotoStats] = []
    cameras: List[CameraStats] = []


# ---------------------------------------------------------------------------
# Phase 4C: AI Chat
# ---------------------------------------------------------------------------

class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AIChatRequest(BaseModel):
    message: str
    conversation_history: List[ConversationMessage] = []
    scope: Optional[List[str]] = None  # e.g. ["email", "calendar", "chat"]


class AISource(BaseModel):
    type: str
    id: str
    title: str
    date: Optional[str] = None
    relevance_score: float = 0.0


class AIChatStatusResponse(BaseModel):
    ollama_available: bool = False
    model_loaded: bool = False
    chroma_ready: bool = False
    embedded_count: int = 0


class AISuggestResponse(BaseModel):
    suggestions: List[str] = []


# ---------------------------------------------------------------------------
# Phase 4B: Semantic Search
# ---------------------------------------------------------------------------

class SemanticSearchItem(BaseModel):
    type: str
    id: int
    title: Optional[str] = None
    snippet: Optional[str] = None
    date: Optional[str] = None
    score: float = 0.0


class SemanticSearchTypeGroup(BaseModel):
    items: List[SemanticSearchItem] = []
    count: int = 0


class SemanticSearchResponse(BaseModel):
    query: str
    total: int = 0
    results: List[SemanticSearchItem] = []
    grouped: dict = {}


class SemanticTypeCounts(BaseModel):
    email: int = 0
    calendar: int = 0
    chat: int = 0
    contact: int = 0
    drive: int = 0


class SemanticStatusResponse(BaseModel):
    total_embedded: int = 0
    by_type: SemanticTypeCounts = SemanticTypeCounts()
    chroma_ready: bool = False
    ollama_available: bool = False


# ---------------------------------------------------------------------------
# Related Items
# ---------------------------------------------------------------------------

class RelatedSource(BaseModel):
    type: str
    id: int
    date: Optional[str] = None


class RelatedEmail(BaseModel):
    id: int
    subject: Optional[str] = None
    from_name: Optional[str] = None
    date: Optional[str] = None


class RelatedPhoto(BaseModel):
    id: int
    filename: Optional[str] = None
    date_taken: Optional[str] = None
    thumbnail_path: Optional[str] = None


class RelatedEvent(BaseModel):
    id: int
    summary: Optional[str] = None
    start_time: Optional[str] = None
    location: Optional[str] = None


class RelatedContact(BaseModel):
    id: int
    name: Optional[str] = None
    emails: list = []


class RelatedChat(BaseModel):
    id: int
    conversation_id: int
    sender_name: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[str] = None


class RelatedDrive(BaseModel):
    id: int
    filename: Optional[str] = None
    path: Optional[str] = None
    mime_type: Optional[str] = None


class RelatedResponse(BaseModel):
    source: RelatedSource
    related: dict = {}
