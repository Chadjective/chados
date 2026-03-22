# Architecture — Personal Google Archive

## Overview

A local-only web application for browsing, searching, and analyzing your entire Google data export (Takeout). Built in 4 phases, expanding from email to photos, documents, and AI-powered analytics.

## System Diagram

```
┌─────────────────────────────────────────────────────┐
│  Browser (localhost)                                │
│  React + TypeScript + Vite                          │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ Email   │ │ Photos   │ │ Drive    │ │ AI Chat│  │
│  │ Viewer  │ │ Timeline │ │ Browser  │ │ Panel  │  │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └───┬────┘  │
└───────┼──────────┼──────────┼──────────┼────────────┘
        │          │          │          │
        ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI Backend (localhost:8000)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ /emails  │ │ /photos  │ │ /drive   │ │ /chat  │  │
│  │ /labels  │ │ /albums  │ │/contacts │ │/search │  │
│  │/attach.  │ │/timeline │ │/calendar │ │/analytics│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘  │
└───────┼──────────┼──────────┼──────────┼────────────┘
        │          │          │          │
        ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────┐
│  Data Layer                                          │
│                                                      │
│  SQLite (archive.db)     ChromaDB (Phase 4)          │
│  ├── emails              ├── email embeddings        │
│  ├── emails_fts (FTS5)   ├── document embeddings     │
│  ├── attachments         └── photo embeddings        │
│  ├── labels                                          │
│  ├── photos (Phase 2)    Ollama (Phase 4)            │
│  ├── albums (Phase 2)    ├── llama3.1:8b             │
│  ├── documents (Phase 3) └── nomic-embed-text        │
│  ├── contacts (Phase 3)                              │
│  ├── events (Phase 3)    File Storage                │
│  ├── notes (Phase 3)     ├── /attachments/           │
│  └── chats (Phase 3)     ├── /thumbnails/ (Phase 2)  │
│                           └── /documents/ (Phase 3)   │
└──────────────────────────────────────────────────────┘
```

## Key Paths

| What | Where | Why |
|------|-------|-----|
| Raw Takeout data | `/Volumes/backup Plus/TakeOut/` | Read-only source, stays on backup drive |
| Database | `/Volumes/T9/personal-archive-data/archive.db` | Fast SSD for query performance |
| Attachments | `/Volumes/T9/personal-archive-data/attachments/` | Organized in subdirs by email_id // 1000 |
| Thumbnails (Phase 2) | `/Volumes/T9/personal-archive-data/thumbnails/` | Generated from photos |
| ChromaDB (Phase 4) | `/Volumes/T9/personal-archive-data/chroma/` | Vector embeddings |
| App code | `/Users/chadjective/Projects/Gmail Inbox/` | The application itself |

## Technology Stack

### Current (Phase 1)
- **Backend:** Python 3 + FastAPI + uvicorn
- **Database:** SQLite with WAL mode, FTS5 for full-text search
- **Frontend:** React 19 + TypeScript + Vite 8
- **Virtualization:** react-virtuoso for large list scrolling
- **Date handling:** date-fns

### Phase 2 additions
- ffmpeg (video thumbnails)
- Pillow (image processing, HEIC support)

### Phase 3 additions
- python-docx, openpyxl, pdfplumber (document text extraction)
- vobject (vCard/iCal parsing)

### Phase 4 additions
- Ollama (local LLM inference)
- ChromaDB (vector database)
- nomic-embed-text (embedding model)
- Chart.js or similar (analytics visualization)

## Database Design Principles

1. **Single SQLite file** — Simple backups, no server process needed
2. **WAL journal mode** — Allows concurrent reads while writing
3. **FTS5 external content** — Search index references main table, not a copy
4. **JSON columns** — For variable-length lists (to_addresses, labels, etc.)
5. **Unix timestamps** — Integer column for fast date sorting/filtering
6. **Extensible schema** — Each phase adds tables, never modifies existing ones

## Performance Targets

| Metric | Target | How |
|--------|--------|-----|
| App startup | < 5 seconds | Pre-built frontend, WAL mode DB |
| Email search | < 1 second | FTS5 index on 500K+ emails |
| Email list scroll | 60fps | Virtualized rendering (react-virtuoso) |
| Individual email load | < 200ms | Indexed by primary key |
| Photo thumbnail grid | Smooth scroll | Lazy loading, pre-generated thumbnails |
| Semantic search (Phase 4) | < 3 seconds | ChromaDB ANN index |

## Import Strategy

- **One-time bulk import** per data type (can take hours for large archives)
- **Streaming parser** for mbox — never loads full file into memory
- **Deferred indexing** — FTS5 populated after bulk insert for speed/safety
- **Resumable** — Duplicate detection via Message-ID (emails), file hash (photos)
- **Progress reporting** — Percentage, count, rate, ETA displayed during import

## Security Model

- **Local only** — Listens on localhost by default (0.0.0.0 for LAN access)
- **No authentication** — Single user, trusted local network
- **No external requests** — HTML emails sandboxed (no image loading, no scripts)
- **No data leaves machine** — All AI inference via local Ollama
- **Read-only archive** — No write operations to original Takeout data
