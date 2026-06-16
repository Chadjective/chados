# ChadOS v3 — Scope & Implementation Plan

## Overview

v3 adds **richer photo input** and a **pluggable local-model layer** on top of the
all-local (Ollama + ChromaDB) AI stack that already powers chat and semantic search.

Three workstreams:
1. **Photo Sources** — import photos from local folders and drag-drop, not just Google Takeout.
2. **Local Model Registry** — discover installed Ollama models and let the user pick which one
   powers chat/RAG (e.g. swap `llama3.1:8b` → Hermes), persisted across launches.
3. **Vision Enrichment** — run a local *vision* model (llava / llama3.2-vision) over photos to
   auto-generate captions + tags, and embed photos so they're searchable by content and reachable
   from chat — exactly like the text archive is today.

These three share one new piece of plumbing: a **background enrichment-jobs framework** (a model
applied to many rows is always a long, resumable, cancellable batch). Build it once; reuse it for
captioning, tagging, and photo embedding.

> **Explicitly out of scope for v3** (declined): batch text-enrichment of emails (classify /
> summarize / extract). The framework below is general enough to add it later, but no email
> enrichment endpoints or UI ship in v3.

---

## Prerequisite: unify the vector store (cleanup, do first)

Photo semantic search and the new vision pipeline all write to ChromaDB, so the existing
inconsistency must be resolved before building on it:

| File | CHROMA_DIR | Collection | Embed endpoint |
|------|-----------|-----------|----------------|
| [`routers/ai_chat.py:28`](../backend/routers/ai_chat.py) | `DB_DIR / "chroma"` | `archive` | `/api/embeddings` (singular) |
| [`embedder.py:36`](../backend/embedder.py) | `~/personal-archive-data/chroma` | `archive_embeddings` | `/api/embed` |
| [`routers/semantic.py:28`](../backend/routers/semantic.py) | `~/personal-archive-data/chroma` | `archive_embeddings` | `/api/embed` |

Chat's RAG reads a **different collection** than the embedder writes to, so chat context is likely
running on an empty/partial index today. Also `ai_chat.SCOPE_TYPES` already includes `"photo"` and
`"note"`, but `semantic.VALID_TYPES` does not — the scaffolding half-anticipates photos.

**Steps:**
1. Move the three constants (`CHROMA_DIR`, `COLLECTION_NAME`, `EMBED_MODEL`, `OLLAMA_URL`) into
   `config.py` and import everywhere. One source of truth.
2. Pick one collection name (`archive_embeddings`) and one path (under the configured data dir).
3. Standardize on one Ollama embed endpoint (`/api/embed`) and one request shape.
4. Add `"photo"` to `semantic.VALID_TYPES`.

**Deliverables:**
- [ ] Single shared ChromaDB config in `config.py`
- [ ] Chat RAG and semantic search read the same collection the embedder writes
- [ ] `photo` is a valid semantic-search type

---

## Workstream 1: Photo Sources (local folder + drag-drop)

### Goal
A user can add photos from anywhere on disk — a folder, or files dragged into the UI — and have
them imported with the same metadata pipeline used for Takeout.

### 1.1 — Pluggable import sources

Today [`photo_importer.py`](../backend/photo_importer.py) is hard-wired to scan
`Takeout*/Google Photos/` and read Google JSON sidecars. Generalize it:

1. Refactor the importer into a **source-agnostic core** + per-source adapters:
   - `core`: dimensions (Pillow/ffmpeg), thumbnail generation, EXIF date/GPS, file hash dedupe,
     DB insert. This logic already exists — extract it so it doesn't assume a JSON sidecar exists.
   - `TakeoutSource` (existing behavior, with JSON sidecar)
   - `LocalFolderSource` (new): walk a folder, EXIF-only metadata, no sidecar required.
2. Dedupe across sources via the existing `file_hash` (MD5 of size + first 64KB) and the
   `file_path UNIQUE` constraint, so re-importing or overlapping folders is safe.
3. Record provenance: add `import_source TEXT DEFAULT 'takeout'` to `photos` (`takeout` |
   `local_folder` | `upload`) so the UI can show where each photo came from and re-runs are scoped.

### 1.2 — API + jobs

```
POST /api/photos/import/folder
  Body: {path: "/Users/chad/Pictures/2019", recursive: true}
  Response: {job_id: 42}            # runs in background (see Enrichment-jobs framework)

POST /api/photos/import/upload
  multipart/form-data: files[]      # drag-drop from the browser
  Response: {imported: 12, skipped_duplicates: 3}

GET  /api/photos/import/jobs
GET  /api/photos/import/jobs/{id}   # {status, total, processed, errors}
```

- Folder import is a background job (libraries can be large; thumbnailing is slow).
- Upload is synchronous for small batches; copies files into the managed data dir before importing.
- Both reuse the dedupe + thumbnail + EXIF core from 1.1.

### 1.3 — Frontend: `PhotoImport.tsx` (new)

- Drag-drop zone + "Add folder…" button (folder picker uses the Electron bridge when packaged per
  SCOPE-v2; falls back to a path input + multi-file `<input>` in the browser).
- Live progress (reuses the jobs UI from the enrichment framework).
- Entry point from the Photos view header and from the v2 Setup Wizard ("import more").

**Deliverables:**
- [ ] Source-agnostic importer core + `LocalFolderSource`
- [ ] `import_source` column + provenance shown in the lightbox
- [ ] Folder-import (background) and upload (sync) endpoints
- [ ] `PhotoImport.tsx` with drag-drop, folder picker, and progress

---

## Workstream 2: Local Model Registry (swap chat model → Hermes, etc.)

### Goal
Stop hard-coding the model. Let the user see which Ollama models are installed and choose which one
powers chat/RAG (Hermes, Mistral, Qwen, …) and — later — which vision/embedding models are used.

### 2.1 — Backend: model registry

Currently the model is the constant `CHAT_MODEL = "llama3.1:8b"`
([`ai_chat.py:26`](../backend/routers/ai_chat.py)). Replace with a registry:

1. New `app_settings(key TEXT PRIMARY KEY, value TEXT)` KV table for persisted selections
   (`model.chat`, `model.vision`, `model.embed`). Defaults preserve today's behavior.
2. New router `routers/models.py` (`/api/models`):

```
GET  /api/models
  Response: {
    installed: [{name: "llama3.1:8b", size_bytes, family, capabilities: ["chat"]}, ...],
    selected: {chat: "llama3.1:8b", vision: "llava:13b", embed: "nomic-embed-text"},
    ollama_online: true
  }
  # installed comes from Ollama GET /api/tags; capability inferred from a curated name map
  # (vision: llava/llama3.2-vision/moondream/bakllava; embed: nomic-embed-text/mxbai-embed; else chat)

POST /api/models/select
  Body: {role: "chat" | "vision" | "embed", model: "hermes3:8b"}
  Response: {ok: true}

GET  /api/models/recommended
  Response: {chat: ["hermes3:8b", "qwen2.5:7b"], vision: ["llava:13b", "llama3.2-vision"],
             embed: ["nomic-embed-text"]}   # suggested `ollama pull` targets, not auto-pulled
```

3. `ai_chat.py` reads `model.chat` from `app_settings` (cached) instead of the constant. Same for
   embed model in the chat/embedder path. Unknown/uninstalled selection → fall back to default +
   surface a warning in `/api/ai/status`.

> Pulling models stays a manual `ollama pull` (documented in the UI). v3 does **not** download
> models on the user's behalf — it lists what's installed and recommends what to pull.

### 2.2 — Frontend: `ModelSettings.tsx` (new)

- Lists installed models grouped by capability; radio-select the active chat (and vision/embed)
  model; shows size and online status.
- "Recommended models" section with copy-paste `ollama pull …` commands.
- Surfaces the `/api/ai/status` warning when a selected model isn't installed.

**Deliverables:**
- [ ] `app_settings` table + `routers/models.py`
- [ ] Chat/embedder read the selected model from settings (default = current behavior)
- [ ] Capability detection + recommended-pull list
- [ ] `ModelSettings.tsx` with per-role pickers and status

---

## Workstream 3: Vision Enrichment (auto-tag, caption, photo search)

### Goal
Apply a local vision model to photos to produce: (a) a natural-language **caption/description**,
(b) **auto-tags** in the existing tag system, and (c) **embeddings** so photos are findable by
content via semantic search and chat.

### 3.1 — Enrichment-jobs framework (shared foundation)

A model over many rows is a long batch — build the runner once and reuse it for captioning,
tagging, photo embedding, and (1.2) folder import.

```sql
CREATE TABLE enrichment_jobs (
    id INTEGER PRIMARY KEY,
    job_type TEXT NOT NULL,        -- 'vision_caption' | 'vision_tag' | 'photo_embed' | 'photo_import'
    model TEXT,                    -- model used (NULL for import)
    scope_json TEXT,               -- {all:true} | {album_id} | {year} | {ids:[...]}
    status TEXT DEFAULT 'queued',  -- queued | running | done | cancelled | error
    total INTEGER DEFAULT 0,
    processed INTEGER DEFAULT 0,
    error TEXT,
    started_at TEXT, finished_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

- Runs in a background task (FastAPI `BackgroundTasks` / a worker thread), **one job at a time**
  (Ollama serializes inference anyway), **resumable** (skip already-enriched rows like
  [`embedder.py`](../backend/embedder.py) does) and **cancellable** (cooperative flag check).
- Generic progress endpoints (also serve Workstream 1):

```
GET  /api/enrich/jobs            # list with progress
GET  /api/enrich/jobs/{id}
POST /api/enrich/jobs/{id}/cancel
```

### 3.2 — Data model for photo enrichment

```sql
ALTER TABLE photos ADD COLUMN ai_caption TEXT;            -- generated description
ALTER TABLE photos ADD COLUMN ai_caption_model TEXT;      -- which model produced it
ALTER TABLE photos ADD COLUMN enriched_at TEXT;           -- NULL = not yet processed
-- distinguish AI-suggested tags from user tags, reusing the existing item_tags table:
ALTER TABLE item_tags ADD COLUMN source TEXT DEFAULT 'user';   -- 'user' | 'ai'
ALTER TABLE item_tags ADD COLUMN confidence REAL;              -- NULL for user tags
```

Reusing `user_tags` / `item_tags` (see SCOPE-v2 §2.1) means AI tags flow through the **existing**
tag filtering, `TagManager`, and `/api/tags` infrastructure for free — they're just marked
`source='ai'` so the UI can render them differently and offer accept/reject.

### 3.3 — Enrichment endpoints

```
POST /api/enrich/photos/caption   Body: {model?, scope, overwrite:false}  -> {job_id}
POST /api/enrich/photos/tag       Body: {model?, scope, overwrite:false}  -> {job_id}
POST /api/enrich/photos/embed     Body: {model?, scope}                   -> {job_id}
```

- **Caption / tag** call Ollama's multimodal API (`POST /api/generate` with base64 `images`)
  using the selected `model.vision`. One prompt returns a caption; a second (or structured) prompt
  returns a short tag list. Caption → `photos.ai_caption`; tags → `item_tags` (`source='ai'`,
  creating `user_tags` rows on demand, deduped by name).
- **Embed** generates a vector per photo from `title + ai_caption + description + tag names` via the
  selected `model.embed` and upserts into ChromaDB with `metadata.type = "photo"`, id `photo:{id}`.
  This is the cheapest path to photo semantic search because it **reuses the existing text-embed +
  ChromaDB stack** — no separate CLIP index. (A native CLIP image-embedding mode is a possible
  later upgrade; noted as a stretch, not v3.)
- Because embed reads `ai_caption`, the natural order is **caption → embed**; the UI should nudge
  this (or offer a "caption + tag + embed" combined run).

### 3.4 — Search & chat integration (mostly free after the prerequisite)

- `semantic.py` already filters by `metadata.type`; with `"photo"` added to `VALID_TYPES`, photos
  appear in `/api/semantic/search` results once embedded.
- `ai_chat.py` already lists `"photo"` in `SCOPE_TYPES`, so RAG chat can cite photos with no new
  code — it just needs the unified collection (prerequisite) and photo vectors present.

### 3.5 — Frontend

1. **`EnrichmentPanel.tsx`** (new) — pick scope (all / album / year / current selection) and model,
   start caption/tag/embed jobs, watch progress, cancel. Lives in Settings or the Photos header.
2. **`PhotoLightbox.tsx`** (modify) — show `ai_caption`, AI tags (visually distinct from user tags),
   with accept/reject (reject removes the `source='ai'` `item_tags` row; accept flips it to `'user'`).
3. **`PhotoTimeline.tsx`** (modify) — add a tag filter (works for AI + user tags via existing
   `item_tags`) and a "caption" badge for enriched photos.
4. **Search** — surface photo results (thumbnail + caption snippet) in the semantic search UI.

**Deliverables:**
- [ ] `enrichment_jobs` table + background runner (resumable, cancellable, single-flight)
- [ ] Photo enrichment columns + `item_tags.source/confidence`
- [ ] caption / tag / embed endpoints using the selected vision + embed models
- [ ] Photos appear in semantic search and RAG chat
- [ ] `EnrichmentPanel.tsx`; lightbox captions + AI-tag accept/reject; timeline tag filter

---

## Implementation Order

```
Phase 0 — Vector-store cleanup (prerequisite)
  0. Unify CHROMA_DIR / collection / embed endpoint in config.py; add 'photo' to VALID_TYPES

Phase 1 — Model registry (smallest, unblocks "swap to Hermes")
  1. app_settings table + routers/models.py + capability detection
  2. ai_chat/embedder read selected model from settings
  3. ModelSettings.tsx

Phase 2 — Enrichment-jobs framework + Photo import
  4. enrichment_jobs table + background runner + /api/enrich/jobs + cancel
  5. Refactor photo_importer into core + LocalFolderSource; import_source column
  6. /api/photos/import/{folder,upload}; PhotoImport.tsx (drag-drop + progress)

Phase 3 — Vision enrichment
  7. Photo enrichment columns + item_tags.source/confidence
  8. caption + tag + embed jobs (Ollama multimodal)
  9. EnrichmentPanel.tsx; lightbox captions + AI-tag accept/reject; timeline tag filter
 10. Verify photos surface in semantic search + RAG chat
```

Phase 1 ships value on its own (Hermes for chat). Phase 2's jobs framework is the foundation Phase 3
depends on, which is why import comes before vision enrichment.

---

## Non-Goals (for now)
- **Email/text enrichment** (classify, summarize, extract) — explicitly deferred.
- Cloud/hosted models — everything stays local via Ollama, consistent with the current design.
- Auto-pulling models — the app lists/recommends; the user runs `ollama pull`.
- Fine-tuning or training any model.
- Native CLIP image embeddings — v3 embeds photos via generated captions; CLIP is a later upgrade.
- Face *recognition / identity naming* — generic people/scene tags are in scope; naming individuals
  and a people directory are not.
- Real-time sync from cloud photo services (iCloud/Google Photos live).

---

## Success Criteria
- [ ] A user can drag a folder of photos in and see them in the timeline within one import run.
- [ ] A user can switch chat from llama3.1 to Hermes (or any installed model) in Settings, and chat
      uses it on the next message.
- [ ] Running vision enrichment over an album produces captions + tags visible in the lightbox.
- [ ] Searching "beach sunset" (or asking chat) surfaces relevant photos that have no such text in
      their filename — proving content-based retrieval works.
- [ ] Enrichment of a large library is resumable and cancellable, with visible progress.
```
