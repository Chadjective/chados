# Personal Google Archive — Master Project Roadmap

## How to Use This Document

This is the tracking document for the entire build. Work through it top to bottom. Each checkbox represents a concrete milestone you can verify before moving on.

**The rule:** Don't paste the next phase's prompt into Claude Code until every checkbox in the current phase is checked. Each phase builds on what came before.

---

## Before You Start

- [x] Google Takeout export is fully downloaded and unzipped on your external hard drive
- [x] You know the path to the Takeout folder: `/Volumes/backup Plus/TakeOut/`
- [x] Your fast 2TB drive is connected: `/Volumes/T9/personal-archive-data/`
- [ ] Mac Mini has Homebrew installed (`brew --version` in Terminal to check)
- [x] Python 3.11+ is installed (`python3 --version`)
- [x] Node.js 18+ is installed (locally at `~/.local/node/bin/node`)
- [x] Claude Code is installed and working
- [x] You've reviewed your Takeout folder to see what's inside

---

## PHASE 1: Email Archive

**Goal:** Browse and search your entire Gmail history offline, in a Gmail-like interface.
**Status: IN PROGRESS**

### 1.1 — Project Setup
- [x] Paste Phase 1 prompt into Claude Code
- [x] Claude Code asks for your Takeout Mail path — provided
- [x] Claude Code asks for your fast drive data path — provided
- [x] Project folder structure is created
- [x] Python backend dependencies install without errors
- [x] Frontend (React) dependencies install without errors

### 1.2 — Email Import
- [x] Import script exists and runs (`import.sh`)
- [x] Import starts processing your .mbox file (53GB)
- [x] Progress is displayed (emails processed, percentage, time estimate)
- [ ] Import completes without critical errors
- [ ] SQLite database file exists on your fast drive
- [ ] Quick sanity check: count total emails imported

### 1.3 — Backend API
- [x] FastAPI server starts without errors
- [x] Email list endpoint works (returns paginated emails)
- [x] Single email endpoint works (returns full email with body)
- [x] Search endpoint works (full-text search via FTS5)
- [x] Labels endpoint works (returns list of Gmail labels with counts)
- [x] Attachment serving works (download and inline preview)
- [ ] **Checkpoint:** Test endpoints at http://localhost:8000/docs

### 1.4 — Frontend Interface
- [x] React app starts without errors (TypeScript compiles clean, production build works)
- [x] Left sidebar shows Gmail labels (Inbox, Sent, Starred, etc.)
- [x] Clicking a label loads emails for that label
- [x] Email list displays sender, subject, date, attachment icon
- [x] Virtualized scrolling (react-virtuoso) for smooth performance
- [x] Clicking an email opens it and shows the full message body
- [x] HTML emails render in sandboxed iframe (scripts blocked, external resources blocked)
- [x] Plain text emails display cleanly
- [x] Email threading works — related messages grouped together
- [x] Search bar with Gmail-style operators (from:, to:, subject:, label:, has:attachment, is:starred, before:, after:)
- [x] Attachments listed and downloadable from email view
- [x] Keyboard shortcuts (j/k navigation, Enter to open, Escape to close, / to search)
- [x] Text is selectable and copy-pasteable
- [ ] **End-to-end testing with real data**

### 1.5 — Launch & Polish
- [x] Launch script starts both backend and frontend with one command
- [x] Browser opens automatically to the app
- [x] README exists with setup and usage instructions
- [ ] App loads in under 5 seconds after startup
- [ ] Search returns results in under 1 second

### Phase 1 — Done Checklist
- [ ] I can browse my entire email history by label
- [ ] I can search and find specific emails quickly
- [ ] I can read email threads with all messages grouped
- [ ] I can view and download attachments
- [ ] The experience feels reasonably similar to Gmail
- [ ] Everything runs locally — no internet needed after setup

---

## PHASE 2: Photo Archive

**Goal:** Browse your Google Photos library offline with a timeline, albums, and search.
**Status: NOT STARTED** — Prerequisite: Phase 1 complete

### 2.1 — Preparation
- [ ] Confirm ffmpeg is installed (`brew install ffmpeg` if not — needed for video thumbnails)
- [ ] Paste Phase 2 prompt into Claude Code
- [ ] Claude Code reads the existing Phase 1 codebase
- [ ] Claude Code asks for your Google Photos Takeout path — provide it

### 2.2 — Photo Import
- [ ] Photo importer script exists and runs
- [ ] Import detects photos, videos, and albums from Takeout folders
- [ ] JSON metadata files matched to photos correctly
- [ ] Progress displayed
- [ ] Thumbnails generated and saved to fast drive
- [ ] HEIC files handled
- [ ] Video thumbnails generated
- [ ] Albums detected from folder names
- [ ] Duplicates deduplicated
- [ ] Import completes

### 2.3 — Backend API
- [ ] Photo list endpoint with pagination
- [ ] Timeline endpoint (year/month counts)
- [ ] Album list endpoint
- [ ] Thumbnail serving (fast)
- [ ] Full-resolution image serving
- [ ] Photo search (description, filename, people)
- [ ] Filtering by year, month, album, media type

### 2.4 — Frontend Interface
- [ ] Navigation has both Email and Photos sections
- [ ] Photos timeline view (chronological grid by month)
- [ ] Lazy-loading thumbnails
- [ ] Lightbox with keyboard navigation
- [ ] Metadata panel (date, location, camera, description)
- [ ] Video playback
- [ ] Album browsing
- [ ] Timeline jump navigation
- [ ] Photo search

---

## PHASE 3: Documents & Everything Else

**Goal:** Browse Drive files, contacts, calendar, notes, chat, and all remaining Takeout data. Plus global search.
**Status: NOT STARTED** — Prerequisite: Phases 1 and 2 complete

### Key sections:
- 3.2: Drive / Documents import & browsing
- 3.3: Contacts import & lookup
- 3.4: Calendar import & month view
- 3.5: Notes (Keep), Chat (Hangouts), and catch-all for remaining data
- 3.6-3.10: Backend APIs and Frontend for each
- 3.11: Global search across ALL data types, unified navigation

---

## PHASE 4: AI Intelligence & Analytics

**Goal:** Analytics dashboard, semantic search, and conversational AI about your archive.
**Status: NOT STARTED** — Prerequisite: Phases 1-3 complete

### Key sections:
- 4.1: Analytics Dashboard (email volume charts, contact analysis, writing metrics, "On This Day")
- 4.2: Semantic Search (ChromaDB embeddings, meaning-based search)
- 4.3: AI Chat Interface (RAG pipeline with Ollama, streaming responses, source citations)
- 4.4: Voice Profile (writing style analysis, exportable profile)

### Prerequisites for Phase 4:
- Ollama installed and running
- Model downloaded (llama3.1:8b, ~5GB)
- ChromaDB for vector storage

---

## Architectural Decisions (Cross-Phase)

These decisions were made in Phase 1 with later phases in mind:

1. **Database:** SQLite on fast drive (`/Volumes/T9/personal-archive-data/archive.db`) — single file, extensible schema. New tables added per phase.
2. **Attachments/Media:** Stored as files on fast drive with DB references, not embedded in DB.
3. **Search:** FTS5 for keyword search now; ChromaDB for semantic search in Phase 4.
4. **Backend:** FastAPI with modular routers — new routers added per phase.
5. **Frontend:** React + TypeScript + Vite — new sections/components added per phase.
6. **Navigation:** Sidebar-based, extensible to add Photos, Drive, Contacts, etc.
7. **Data isolation:** Raw Takeout data stays on external drive (read-only). Working data (DB, thumbnails, index) lives on fast drive.

---

## Future Enhancements (Post Phase 4)

- Map view for photos and location history
- OCR for scanned PDFs (using local AI)
- Fine-tuning a model on your writing voice
- Multi-user access (family archives)
- Automated backup schedule (periodic new Takeout exports merged in)
- Mobile-friendly responsive design
- Browser extension to search archive from anywhere
