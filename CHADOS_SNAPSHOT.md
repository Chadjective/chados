# ChadOS — State Snapshot

**Captured:** 2026-06-16
**Purpose:** Preserve the full state of ChadOS before forking into **Throughline** (a personal digital-archive consolidation & visualization platform).
**Repo:** `~/Projects/Gmail Inbox/` · branch `main` · `app = FastAPI(title="ChadOS", version="2.0.0")`

> This document is a read-only preservation artifact. No existing code or data was modified to produce it.

---

## 0. TL;DR — what exists

ChadOS is a **local-first personal Google Takeout archive** browser. A FastAPI backend indexes a Google Takeout export (Gmail, Photos, Calendar, Contacts, Chat, Drive, Keep) into a single ~9.4 GB SQLite database with FTS5 full-text search and an optional ChromaDB semantic layer (Ollama embeddings). A React 19 + Vite frontend renders a Gmail-style UI plus photo timeline, calendar, analytics dashboard, semantic/AI chat, and bulk actions.

**Headline data:**

| Metric | Value |
|---|---|
| Emails | **365,901** (2005-04-07 → 2024-05-25) |
| Photos/videos | **273,432** (3,503 videos; 960 with GPS) |
| Email↔label links | 959,277 |
| Attachments | 122,509 |
| Calendar events | 15,822 (2008 → 2024) |
| Contacts | 1,191 |
| Chat messages | 6,053 across 56 conversations |
| Drive files | 510 |
| Database file | **9.4 GB** (`~/personal-archive-data/archive.db`) |
| Vector store | 900 MB (ChromaDB) |
| Thumbnails | 4.4 GB |

---

## 1. Data locations (all OUTSIDE the git repo)

Configured in `backend/config.py`. User data is gitignored and lives on the internal SSD (APFS — the config notes ExFAT corrupts SQLite):

| What | Path | Size |
|---|---|---|
| **SQLite DB** | `~/personal-archive-data/archive.db` | **9.4 GB** |
| DB WAL/SHM | `archive.db-wal` (0 B), `archive.db-shm` (32 KB) | — |
| **Backup (this snapshot)** | `~/personal-archive-data/archive-backup-2026-06-16.db` | 9.4 GB ✅ |
| Vector store | `~/personal-archive-data/chroma/` | 900 MB |
| Thumbnails | `~/personal-archive-data/thumbnails/` | 4.4 GB |
| Attachments | `/Volumes/T9/personal-archive-data/attachments/` (external) | — |
| Default mbox source | `/Volumes/Backup Plus/TakeOut/.../All mail Including Spam and Trash-002.mbox` | — |
| Default Photos source | `/Volumes/backup Plus/TakeOut/Zip Files` | — |

Env overrides: `ARCHIVE_DB_DIR`, `ARCHIVE_ATTACHMENTS_DIR`, `ARCHIVE_ENABLE_AI`.

---

## 2. Git status

- **Tracked by git:** yes. Branch `main`, up to date with `origin/main`.
- **Recent commits:**
  - `f6ef19d` Rebrand to ChadOS
  - `aa47a63` Initial release: Personal Google Archive
- **Uncommitted changes** (the v3/v4 "actions + photo-import + spaces/tags + trash" work, not yet committed):
  - *Modified:* `backend/database.py`, `backend/main.py`, `backend/photo_importer.py`, routers `analytics/calendar/chat/contacts/drive/emails/photos/search`, frontend `App.css`, `App.tsx`, `EmailList.tsx`, `EmailRow.tsx`, `Sidebar.tsx`, `useKeyboardShortcuts.ts`, `types/index.ts`, `utils/api.ts`
  - *Untracked:* `backend/jobs.py`, `backend/local_folder_importer.py`, `backend/routers/actions.py`, `backend/routers/photo_import.py`, `docs/SCOPE-v2.md`, `docs/SCOPE-v3.md`, frontend `ActionToolbar.tsx`, `ConfirmDialog.tsx`, `PhotoImport.tsx`, `SpaceManager.tsx`, `TagManager.tsx`, `TrashView.tsx`, `hooks/useSelection.ts`
  - `.db`, `*.log`, `node_modules/`, `dist/`, `chroma/`, `thumbnails/`, `attachments/` are gitignored.

---

## 3. Source file tree

(excludes `node_modules/`, `venv/`, `__pycache__/`, `.git/`)

```
Gmail Inbox/
├── README.md
├── setup.sh  start.sh  import.sh  import-all.sh  import-photos.sh
├── extract_photos.sh  extract_remaining.sh  background_tasks.sh  background_tasks.log
├── docs/
│   ├── ARCHITECTURE.md  PROJECT_ROADMAP.md  SCOPE-v2.md  SCOPE-v3.md
├── backend/
│   ├── main.py                 # FastAPI app, router registration, AI feature flag
│   ├── config.py               # paths, ports, ffmpeg resolution
│   ├── database.py             # schema init + migrations + get_connection
│   ├── models.py               # Pydantic response models
│   ├── jobs.py                 # background job runner (enrichment_jobs)
│   ├── embedder.py             # ChromaDB embedding builder (Ollama nomic-embed-text)
│   ├── requirements.txt  requirements-ai.txt
│   ├── importers:
│   │   ├── importer.py             # Gmail mbox (streaming)
│   │   ├── photo_importer.py       # Google Photos Takeout
│   │   ├── local_folder_importer.py# arbitrary folder / external drive (v4)
│   │   ├── drive_importer.py        # Google Drive catalog + text extract
│   │   ├── calendar_importer.py     # iCalendar .ics
│   │   ├── contacts_importer.py     # vCard .vcf
│   │   ├── chat_importer.py         # Google Chat / Hangouts JSON
│   │   └── notes_importer.py        # Google Keep (JSON or HTML)
│   └── routers/
│       ├── __init__.py
│       ├── emails.py  labels.py  attachments.py
│       ├── photos.py  photo_import.py
│       ├── contacts.py  calendar.py  chat.py  drive.py  notes.py
│       ├── search.py  analytics.py  related.py  actions.py
│       └── ai_chat.py  semantic.py        # optional (AI)
└── frontend/
    ├── package.json  vite.config.ts  tsconfig*.json  eslint.config.js  index.html
    ├── public/ (icons.svg, favicon.svg)
    └── src/
        ├── main.tsx  App.tsx  App.css  index.css
        ├── types/index.ts
        ├── utils/ (api.ts, format.ts)
        ├── hooks/ (useKeyboardShortcuts.ts, useSelection.ts)
        └── components/
            ├── EmailList.tsx  EmailRow.tsx  EmailView.tsx  ThreadView.tsx
            ├── Sidebar.tsx  SearchBar.tsx  GlobalSearch.tsx
            ├── PhotoTimeline.tsx  AlbumGrid.tsx  PhotoLightbox.tsx  PhotoImport.tsx
            ├── CalendarView.tsx  ContactList.tsx  ChatView.tsx  DriveView.tsx  NotesView.tsx
            ├── AttachmentViewer.tsx  RelatedSidebar.tsx  AnalyticsDashboard.tsx
            ├── AIChat.tsx
            ├── ActionToolbar.tsx  ConfirmDialog.tsx  SpaceManager.tsx  TagManager.tsx  TrashView.tsx
```

**Frontend stack:** React 19.2 · Vite 8 · TypeScript 5.9 · react-router-dom 7 · react-virtuoso (list virtualization) · recharts (analytics) · lucide-react (icons) · date-fns.

---

## 4. SQLite database schema

23 objects total: 12 core tables, 5 FTS5 shadow tables, 1 virtual FTS table, 3 triggers, `sqlite_sequence`. (See §5 for the FTS/trigger machinery.)

### Core tables

**`emails`** — id, message_id (UNIQUE), thread_id, from_address, from_name, to/cc/bcc_addresses (JSON), subject, date, date_unix, body_text, body_html, labels (JSON), has_attachments, is_read, is_starred, raw_size_bytes, date_month_day, **deleted_at** (soft delete).
Indexes: date_unix DESC, thread_id, from_address, message_id, has_attachments, is_starred, date, date_month_day, (deleted_at, date_unix DESC).

**`attachments`** — id, email_id→emails, filename, content_type, size_bytes, file_path. Index: email_id.

**`labels`** — id, name (UNIQUE), email_count.
**`email_labels`** — (email_id, label_id) composite PK; indexes both ways.

**`photos`** — id, file_path (UNIQUE), filename, title, description, mime_type, width, height, size_bytes, date_taken, date_taken_unix, date_created, creation_unix, latitude, longitude, altitude, camera_make, camera_model, device_type, is_video, duration_seconds, thumbnail_path, google_photos_url, is_favorite, source_album, file_hash, date_month_day, **deleted_at**, **import_source** (default `'takeout'`), **location_source**.
Indexes: date_taken_unix DESC, source_album, is_video, file_hash, mime_type, month_day, (deleted_at, date_taken_unix DESC).

**`albums`** — id, name (UNIQUE), photo_count, cover_photo_id→photos.
**`photo_albums`** — (photo_id, album_id) composite PK; indexes both ways.

**`contacts`** — id, name, given/family_name, emails (JSON), phones (JSON), organization, title, notes, photo_path, groups (JSON), source_file, deleted_at; UNIQUE(name, emails). Index: name.

**`calendar_events`** — id, calendar_name, uid, summary, description, location, start/end_time, start/end_unix, is_all_day, recurrence, organizer, attendees (JSON), status, source_file, date_month_day, deleted_at; UNIQUE(uid, calendar_name). Indexes: start_unix DESC, calendar_name, uid, month_day.

**`chat_conversations`** — id, name, participants (JSON), type ('DM'|'Space'|'Group'), source_folder (UNIQUE). Index: type.
**`chat_messages`** — id, conversation_id→chat_conversations, sender_name, sender_email, content, timestamp, timestamp_unix, message_type, deleted_at. Indexes: conversation_id, timestamp_unix DESC.

**`drive_files`** — id, filename, path (UNIQUE), parent_path, mime_type, size_bytes, modified_time, modified_unix, is_folder, extracted_text, source_file, deleted_at. Indexes: parent_path, mime_type, modified_unix DESC.

**`notes`** — id, title, content, color, labels (JSON), is_archived, is_pinned, is_trashed, created_time, modified_time, source_file (UNIQUE). Index: created_time. *(0 rows — Keep not imported.)*

### User-layer tables (v3 "actions")

**`user_tags`** — id, name (UNIQUE), color (default `#1a73e8`), created_at.
**`item_tags`** — id, tag_id→user_tags, item_type, item_id, created_at; UNIQUE(tag_id, item_type, item_id). Indexes: (item_type, item_id), tag_id.
**`user_actions`** — id, action, item_type, item_id, detail, created_at. *(audit log)*

### Job table (v4)

**`enrichment_jobs`** — id, job_type ('photo_import'|'geo_backfill'|'vision_caption'|…), label, scope_json, status (queued|running|done|cancelled|error), total, processed, imported, skipped, errors, error, started_at, finished_at, created_at.

> **Soft-delete pattern:** emails, photos, contacts, calendar_events, chat_messages, drive_files all carry `deleted_at` → trash/restore is non-destructive. `date_month_day` columns power the "On This Day" feature.

> **Data caveat:** `photos.date_taken` has dirty extremes (MIN `1970-01-01`, MAX `4501-01-01`) from bad EXIF/sidecar timestamps — worth normalizing in Throughline.

---

## 5. Full-text & semantic search machinery

**FTS5 (built-in, on emails):**
- `emails_fts` — virtual FTS5 table over from_name, from_address, to_addresses, subject, body_text; `tokenize='porter unicode61'`, content-linked to `emails` (external content, content_rowid=id).
- Shadow tables: `emails_fts_data`, `emails_fts_idx`, `emails_fts_docsize`, `emails_fts_config`.
- Triggers `emails_ai` / `emails_ad` / `emails_au` keep the index in sync on insert/delete/update.

**Semantic layer (optional, ChromaDB + Ollama):**
- `backend/embedder.py` reads rows from SQLite, embeds via Ollama `nomic-embed-text`, stores vectors in ChromaDB at `~/personal-archive-data/chroma/` (900 MB). Supports emails (default capped 50K), calendar, chat, contact, drive. Flags: `--type`, `--limit`, `--reset`.
- Served by `routers/semantic.py` and `routers/ai_chat.py`, gated by `ARCHIVE_ENABLE_AI` (auto/false). Loaded only if import succeeds.

---

## 6. API endpoints

All under `/api`. Optional AI routers load only when `ARCHIVE_ENABLE_AI != "false"` and imports succeed.

### emails — `/api/emails`
- `GET /stats` · `GET /search` · `GET /{email_id}/thread` · `GET /{email_id}` · `GET ""` (list)

### labels — `/api/labels`
- `GET ""`

### attachments — `/api/attachments`
- `GET /{id}/info` · `GET /{id}` (download) · `GET /{id}/preview`

### photos — `/api/photos`
- `GET /stats` · `GET /timeline` · `GET /search` · `GET /albums` · `GET /albums/{album_id}` · `GET /{photo_id}` · `GET /{photo_id}/thumbnail` · `GET /{photo_id}/full` · `GET ""`

### photo import — `/api/photos/import`  *(registered before /api/photos so it resolves cleanly)*
- `GET /drives` · `POST /folder` · `GET /jobs` · `GET /jobs/{job_id}` · `POST /jobs/{job_id}/cancel`

### contacts — `/api/contacts`
- `GET /search` · `GET /groups` · `GET /{contact_id}` · `GET ""`

### calendar — `/api/calendar`
- `GET /calendars` · `GET /month/{year}/{month}` · `GET /events/{event_id}` · `GET /events`

### chat — `/api/chat`
- `GET /search` · `GET /conversations/{id}` · `GET /conversations`

### drive — `/api/drive`
- `GET /search` · `GET /folders` · `GET /files/{id}/preview` · `GET /files/{id}` · `GET /files`

### notes — `/api/notes`
- `GET /labels` · `GET /{note_id}` · `GET ""`

### search — `/api/search`
- `GET ""` (global cross-type search)

### analytics — `/api/analytics`
- `GET /email-volume` · `/email-heatmap` · `/top-contacts` · `/contact-timeline` · `/response-times` · `/writing-stats` · `/overview` · `/on-this-day` · `/activity-timeline` · `/photo-stats`

### related — `/api`
- `GET /related` (cross-entity related-items)

### actions — `/api`  *(v3 bulk actions + tags + spaces/trash)*
- `POST /actions/delete` · `/actions/restore` · `/actions/star` · `/actions/mark-read` · `/actions/label` · `/actions/tag` · `/actions/untag`
- `GET /actions/trash` · `POST /actions/empty-trash` · `GET /actions/space-analysis`
- `GET /tags` · `POST /tags` · `PUT /tags/{tag_id}` · `DELETE /tags/{tag_id}`
- `GET /smart-filters`

### AI (optional)
- **ai_chat** `/api/ai` — `POST /chat` · `GET /status` · `POST /suggest`
- **semantic** `/api/semantic` — `GET /search` · `GET /status`

---

## 7. Importer modules

All are standalone CLI scripts that write directly into `archive.db`; importers are **idempotent** (skip rows already present) so re-runs are safe.

| Module | Source format | Handles |
|---|---|---|
| `importer.py` | Gmail `.mbox` | Streams mbox line-by-line (no full pre-index); parses headers, bodies (text+html), labels, attachments; populates FTS via triggers. |
| `photo_importer.py` | Google Photos Takeout | Scans `Takeout*/Google Photos/` folders, reads JSON sidecars, generates thumbnails, dedups by file hash; `import_source='takeout'`. |
| `local_folder_importer.py` | Arbitrary folder / external drive (v4) | EXIF-only (no Google sidecar), in-place indexing (`file_path` points at original — nothing copied), hash dedup; `import_source='local_folder'`. Reuses photo_importer's hashing/EXIF/thumbnail/probe core. |
| `drive_importer.py` | Google Drive Takeout | Catalogs files, extracts text into `drive_files.extracted_text`. |
| `calendar_importer.py` | iCalendar `.ics` | Parses events with timezone-offset fallback table; UNIQUE(uid, calendar_name). |
| `contacts_importer.py` | vCard `.vcf` | Decodes quoted-printable; emails/phones/groups as JSON. |
| `chat_importer.py` | Google Chat / Hangouts JSON | Parses `Groups/` + `Users/`; custom date-format regex; conversations + messages. |
| `notes_importer.py` | Google Keep | Supports JSON (newer) and HTML (older) exports; exits gracefully if absent. *(currently 0 rows)* |
| `embedder.py` | (reads SQLite) | Builds ChromaDB embeddings via Ollama for semantic search. |

---

## 8. Background job system (`backend/jobs.py`, v4)

- Single worker thread drains a **FIFO queue persisted in `enrichment_jobs`**. One job at a time (disk/Ollama-bound work serializes anyway).
- **Resumable** — importers skip existing rows, so re-queuing is safe.
- **Cancellable** — cooperative in-memory flag the job polls (`POST /api/photos/import/jobs/{id}/cancel`).
- **Observable** — coarse status transitions (queued→running→done/cancelled/error) persisted to DB; fast-moving progress counters (total/processed/imported/skipped/errors) kept **in memory** and overlaid by `get_job()` to avoid write-lock contention with the importer's own DB connection.
- Designed as the shared foundation: photo_import today; geo-backfill / vision-caption enrichment later (add a branch in `_run_job`). Python 3.9 backend (deferred annotation eval for `X | None`).

---

## 9. Frontend component inventory (29 components)

**Email/core:** `EmailList`, `EmailRow`, `EmailView`, `ThreadView`, `Sidebar`, `SearchBar`, `GlobalSearch`, `AttachmentViewer`, `RelatedSidebar`
**Photos:** `PhotoTimeline`, `AlbumGrid`, `PhotoLightbox`, `PhotoImport`
**Other data types:** `CalendarView`, `ContactList`, `ChatView`, `DriveView`, `NotesView`
**Analytics/AI:** `AnalyticsDashboard` (recharts), `AIChat`
**v3 actions layer:** `ActionToolbar`, `ConfirmDialog`, `SpaceManager`, `TagManager`, `TrashView`
**App shell:** `App.tsx`, `main.tsx`
**Hooks:** `useKeyboardShortcuts`, `useSelection`
**Utils/types:** `utils/api.ts`, `utils/format.ts`, `types/index.ts`

---

## 10. Backup confirmation

A copy-on-write (APFS `cp -c`) clone of the live database was created before any Throughline work:

```
~/personal-archive-data/archive-backup-2026-06-16.db   (9.4 GB, exit 0 ✅)
```

The clone shares blocks with the original until either diverges, so it is effectively free on disk while preserving an exact byte-for-byte snapshot of the 365K-email / 273K-photo index. The vector store (`chroma/`) and thumbnails were **not** backed up (regenerable from the DB + source files).

> Note: `archive.db-wal` was 0 B at snapshot time (clean checkpoint), so the cloned `.db` is consistent on its own.
