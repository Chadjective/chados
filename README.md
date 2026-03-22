# ChadOS

Your digital life, locally owned and searchable.

ChadOS is a local web application for browsing and searching your entire Google history offline — emails, photos, calendar, contacts, chat, drive files, and more — using data exported from Google Takeout.

Everything runs on your machine. No data leaves your computer.

## What's Included

- **📧 Email** — Gmail-like interface with full-text search across hundreds of thousands of emails
- **📸 Photos** — Timeline view, albums, lightbox, video playback
- **📅 Calendar** — Month grid view with event details
- **👥 Contacts** — Searchable contact list with email links
- **💬 Chat** — Google Chat conversations with message history
- **💾 Drive** — Folder browsing and file preview
- **📊 Analytics** — Email volume charts, heatmaps, top contacts, writing stats, "On This Day"
- **🔍 Semantic Search** — Meaning-based search using local AI embeddings
- **🤖 AI Chat** — Ask questions about your archive using a local LLM (Ollama)
- **🎨 Themes** — Light, Dark, and Claude modes

## Quick Start

### 1. Download your data from Google

Go to [takeout.google.com](https://takeout.google.com), select the data you want, and export it. Download the zip files to your computer.

### 2. Run setup

```bash
git clone <this-repo>
cd chados
./setup.sh
```

This installs Python dependencies, Node.js (if needed), and frontend packages. It will ask where to store the database (default: `~/personal-archive-data/`).

> **Important:** The database must be on an APFS/HFS+ drive (your Mac's internal SSD). ExFAT drives will corrupt SQLite.

### 3. Import your data

```bash
# Point at your Takeout folder — auto-discovers emails, photos, calendar, etc.
./import.sh /path/to/Takeout

# If your Takeout is split across multiple folders:
./import.sh /path/to/Takeout
./import.sh "/path/to/Takeout 2"
./import.sh "/path/to/Takeout 3"

# If your Takeout is still in zip files, point at the folder of zips:
./import.sh /path/to/folder-of-zips
```

The importer auto-detects what's in each Takeout folder (Mail, Google Photos, Calendar, Contacts, Chat, Drive, Keep) and imports everything it finds. Progress is shown for each data type.

### 4. Launch the app

```bash
./start.sh
```

Opens your browser to `http://localhost:5173`. Also accessible from other devices on your network.

## Optional: AI Features

For semantic search and AI chat, install Ollama:

```bash
# Download from ollama.com or:
curl -fsSL https://ollama.com/download/Ollama-darwin.zip -o /tmp/Ollama.zip
unzip /tmp/Ollama.zip -d /tmp && cp -R /tmp/Ollama.app /Applications/
open /Applications/Ollama.app

# Pull the models:
ollama pull llama3.1:8b          # Chat model (~5GB)
ollama pull nomic-embed-text     # Embedding model (~270MB)

# Build embeddings (one-time, takes ~1 hour):
cd backend && source venv/bin/activate
python embedder.py --type all
```

## Features

### Email
- Full-text search in <30ms across 365K+ emails (SQLite FTS5)
- Gmail search operators: `from:`, `to:`, `subject:`, `label:`, `has:attachment`, `is:starred`, `before:`, `after:`
- Thread view — related emails grouped into conversations
- HTML email rendering in sandboxed iframe
- Attachment download and inline preview
- Keyboard shortcuts (j/k, Enter, Escape, /)
- Virtual scrolling for smooth browsing

### Photos
- Timeline view grouped by month with year-jump navigation
- Albums with cover thumbnails
- Full-resolution lightbox with keyboard navigation
- Video playback
- Metadata display (date, location, camera, dimensions)
- Favorites and search

### Calendar
- Month grid view with event dots
- Event detail panel with attendees
- Calendar filter toggles
- Grid/list view toggle

### Contacts
- Alphabetical list with letter groups
- Search by name, email, phone, organization
- "View emails" links to email search

### Chat
- Conversation list sorted by recent activity
- Chat bubble message view
- Search across all conversations

### Analytics
- Email volume over time (yearly/monthly)
- Day × hour heatmap
- Top contacts with drill-down timeline
- Writing stats (average length, top words)
- Photo stats by year and camera
- "On This Day" — historical activity for today's date
- Unified activity timeline across all data types

### Related Sidebar
- When viewing any item, see contextually related items from other data types
- Time-based discovery (±3 days) and contact-based linking
- Photos from the same week as an email, calendar events on that day, etc.

## Search Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `from:` | `from:john@example.com` | Emails from a sender |
| `to:` | `to:me@example.com` | Emails to a recipient |
| `subject:` | `subject:"meeting notes"` | Subject line search |
| `label:` | `label:Inbox` | Filter by Gmail label |
| `has:attachment` | | Emails with attachments |
| `is:starred` | | Starred emails |
| `is:unread` | | Unread emails |
| `before:` | `before:2023-01-01` | Before a date |
| `after:` | `after:2022-06-15` | After a date |

Combine operators: `from:boss@work.com subject:review has:attachment after:2023-01-01`

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `j` / `↓` | Next email |
| `k` / `↑` | Previous email |
| `Enter` | Open selected email |
| `Escape` | Back to list / close lightbox |
| `/` | Focus search bar |
| `←` / `→` | Previous/next photo in lightbox |
| `i` | Toggle photo info panel |

## Architecture

```
Browser (React + TypeScript + Vite)
  ↕ /api/*
FastAPI Backend (Python + uvicorn)
  ↕
SQLite + FTS5 (~/personal-archive-data/archive.db)
  ↕ (optional)
ChromaDB (vector embeddings) + Ollama (local LLM)
```

## Troubleshooting

### "database disk image is malformed"
Your database is on an ExFAT drive. SQLite requires APFS or HFS+ for file locking. Move the database to your internal SSD: set `ARCHIVE_DB_DIR` in `.env` to a path on your internal drive.

### Import seems stuck
Large emails with many attachments take longer. If emails/sec is >0 in the progress output, it's working.

### Photos not showing
Make sure the original photo files are still accessible at their original paths. The database stores file paths, not the photos themselves.

### AI features not working
Ensure Ollama is running (`ollama serve` or open the Ollama app) and models are pulled. Check status at `http://localhost:8000/api/ai/status`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHIVE_DB_DIR` | `~/personal-archive-data` | Database and thumbnails directory |
| `ARCHIVE_ATTACHMENTS_DIR` | `$ARCHIVE_DB_DIR/attachments` | Email attachments directory |

Set these in `.env` in the project root (created by `setup.sh`).
