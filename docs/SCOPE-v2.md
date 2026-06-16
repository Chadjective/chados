# ChadOS v2 — Scope & Implementation Plan

## Overview

Two workstreams running in parallel:
1. **Easy Install** — Make ChadOS installable by anyone with a Mac
2. **Write Actions** — Add delete, label, star, bulk operations, and advanced search

---

## Workstream 1: Easy Install

### Goal
A non-technical user can go from "I have a Google Takeout zip" to "browsing my archive" without touching a terminal.

### 1.1 — Electron Desktop App Shell

**What:** Wrap ChadOS in an Electron app that bundles everything (Python backend, Node frontend, SQLite) into a single `.app` that lives in /Applications.

**Steps:**
1. Create `desktop/` folder with Electron main process
2. Bundle Python as a standalone binary using PyInstaller or embed Python.framework
3. Bundle the built Vite frontend (static files, no dev server needed)
4. Electron main process:
   - Starts the Python/FastAPI backend as a child process on a random available port
   - Serves the frontend via Electron's BrowserWindow
   - Shows a system tray icon with "Open ChadOS" / "Quit"
   - On first launch, shows the Setup Wizard (see 1.2)
5. Package as `.dmg` using electron-builder
6. Code-sign for macOS (so users don't get "unidentified developer" warnings)
7. Auto-updater using electron-updater (optional, for future releases)

**Key decisions:**
- Bundle Python runtime (~50MB) vs require user to have Python installed
  - **Recommendation:** Bundle it. Requiring Python defeats the purpose.
- Backend port: use random available port, pass to frontend via Electron IPC
- Data directory: default to `~/ChadOS/` (more user-friendly than `~/personal-archive-data/`)

**Deliverables:**
- [ ] Electron shell with BrowserWindow loading the frontend
- [ ] Python backend starts/stops with the app lifecycle
- [ ] `.dmg` installer with drag-to-Applications
- [ ] App icon and branding

### 1.2 — Setup Wizard (First Launch Experience)

**What:** A guided, step-by-step UI that walks users through setup on first launch. No terminal required.

**Steps:**
1. Create a `SetupWizard.tsx` component (or separate Electron window)
2. Wizard flow:

```
┌─────────────────────────────────────────────┐
│  Welcome to ChadOS                          │
│                                             │
│  Your digital life, locally owned.          │
│                                             │
│  [Get Started →]                            │
└─────────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────────┐
│  Step 1: Get Your Data from Google          │
│                                             │
│  1. Go to takeout.google.com                │
│  2. Click "Deselect all"                    │
│  3. Select: Mail, Google Photos, Calendar,  │
│     Contacts, Google Chat, Drive            │
│  4. Click "Next step"                       │
│  5. Choose ".zip" format, 2GB file size     │
│  6. Click "Create export"                   │
│  7. Wait for Google's email (can take hours)│
│  8. Download all the zip files              │
│                                             │
│  [I already have my Takeout files →]        │
│  [Open takeout.google.com ↗]                │
└─────────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────────┐
│  Step 2: Select Your Takeout Files          │
│                                             │
│  Drag your Takeout folder here, or:         │
│  [Browse for folder...]                     │
│                                             │
│  📁 /Users/dad/Downloads/Takeout            │
│                                             │
│  Found:                                     │
│  ✅ Mail (1 .mbox file, 12 GB)             │
│  ✅ Google Photos (4,231 files)             │
│  ✅ Calendar (8 .ics files)                 │
│  ✅ Contacts (3 .vcf files)                 │
│  ✅ Google Chat (12 conversations)          │
│  ⬜ Drive (skipped — 45 GB, import later?)  │
│                                             │
│  [Import Selected →]                        │
└─────────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────────┐
│  Step 3: Importing...                       │
│                                             │
│  📧 Emails    ████████████░░░░  75%  12min  │
│  📸 Photos    ░░░░░░░░░░░░░░░░  waiting... │
│  📅 Calendar  ░░░░░░░░░░░░░░░░  waiting... │
│  👥 Contacts  ░░░░░░░░░░░░░░░░  waiting... │
│  💬 Chat      ░░░░░░░░░░░░░░░░  waiting... │
│                                             │
│  You can close this and come back later.    │
│  Import will continue in the background.    │
└─────────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────────┐
│  ✅ Import Complete!                        │
│                                             │
│  📧 142,856 emails (2011-2024)              │
│  📸 8,432 photos, 127 videos                │
│  📅 3,291 calendar events                   │
│  👥 456 contacts                            │
│  💬 23 chat conversations                   │
│                                             │
│  Optional: Enable AI features?              │
│  Adds semantic search and AI chat.          │
│  Requires 6GB download (one-time).          │
│  [Enable AI] [Skip for now]                 │
│                                             │
│  [Open ChadOS →]                            │
└─────────────────────────────────────────────┘
```

3. Persist setup state so wizard only shows on first launch
4. Allow re-running wizard from Settings to import more data

**Deliverables:**
- [ ] Wizard component with all 4 steps
- [ ] Takeout folder scanner (detect what data types exist)
- [ ] Real-time import progress UI
- [ ] Skip/resume capability
- [ ] AI opt-in step

### 1.3 — Build & Distribution

**Steps:**
1. Create `electron-builder` config for macOS (.dmg)
2. Create GitHub Releases workflow
3. Two release artifacts:
   - `ChadOS-v1.0.0-mac-arm64.dmg` (Apple Silicon)
   - `ChadOS-v1.0.0-mac-x64.dmg` (Intel Mac)
4. Landing page (optional): simple site explaining what ChadOS does with download button
5. README with screenshots

**Deliverables:**
- [ ] Automated build pipeline
- [ ] .dmg files for both architectures
- [ ] GitHub Release with changelog

---

## Workstream 2: Write Actions

### Goal
Users can organize, clean up, and manage their archive — not just read it.

### 2.1 — Data Model Changes

**Database additions:**
```sql
-- Soft delete support
ALTER TABLE emails ADD COLUMN deleted_at TEXT DEFAULT NULL;
ALTER TABLE photos ADD COLUMN deleted_at TEXT DEFAULT NULL;
ALTER TABLE calendar_events ADD COLUMN deleted_at TEXT DEFAULT NULL;
ALTER TABLE chat_messages ADD COLUMN deleted_at TEXT DEFAULT NULL;
ALTER TABLE drive_files ADD COLUMN deleted_at TEXT DEFAULT NULL;
ALTER TABLE contacts ADD COLUMN deleted_at TEXT DEFAULT NULL;

-- User-created labels/tags (separate from Gmail labels)
CREATE TABLE user_tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#1a73e8',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tag assignments (polymorphic — works for any item type)
CREATE TABLE item_tags (
    id INTEGER PRIMARY KEY,
    tag_id INTEGER NOT NULL REFERENCES user_tags(id),
    item_type TEXT NOT NULL,  -- 'email', 'photo', 'contact', etc.
    item_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tag_id, item_type, item_id)
);

-- User modifications log (audit trail)
CREATE TABLE user_actions (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,       -- 'delete', 'restore', 'star', 'unstar', 'label', 'unlabel', 'tag', 'untag'
    item_type TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    detail TEXT,               -- JSON with action-specific data
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_emails_deleted ON emails(deleted_at);
CREATE INDEX idx_photos_deleted ON photos(deleted_at);
CREATE INDEX idx_item_tags_lookup ON item_tags(item_type, item_id);
CREATE INDEX idx_item_tags_tag ON item_tags(tag_id);
```

**Steps:**
1. Add migration to database.py that runs ALTER TABLE on existing databases
2. Update ALL existing queries to add `WHERE deleted_at IS NULL` (default behavior)
3. Add `include_deleted` flag to API endpoints for trash view

**Deliverables:**
- [ ] Migration script
- [ ] All read queries filter soft-deleted items
- [ ] Audit log captures all write actions

### 2.2 — Write Action API Endpoints

**New router: `/backend/routers/actions.py`**

```
POST /api/actions/delete
  Body: {item_type: "email", item_ids: [1, 2, 3], permanent: false}
  Response: {deleted: 3, space_bytes: 1234567}

POST /api/actions/restore
  Body: {item_type: "email", item_ids: [1, 2, 3]}
  Response: {restored: 3}

POST /api/actions/permanent-delete
  Body: {item_type: "email", item_ids: [1, 2, 3]}
  Response: {deleted: 3, space_freed_bytes: 1234567, files_removed: 2}
  Note: Also deletes attachment files and photo files from disk

POST /api/actions/star
  Body: {item_ids: [1, 2, 3], starred: true}
  Response: {updated: 3}

POST /api/actions/mark-read
  Body: {item_ids: [1, 2, 3], read: true}
  Response: {updated: 3}

POST /api/actions/label
  Body: {item_ids: [1, 2, 3], add_labels: ["Important"], remove_labels: ["Inbox"]}
  Response: {updated: 3}

POST /api/actions/tag
  Body: {item_type: "email", item_ids: [1, 2, 3], tag_id: 5}
  Response: {tagged: 3}

POST /api/actions/untag
  Body: {item_type: "email", item_ids: [1, 2, 3], tag_id: 5}
  Response: {untagged: 3}

GET /api/actions/trash
  Params: ?item_type=email&offset=0&limit=50
  Response: {items: [...], total: 150, total_size_bytes: 45678900}

POST /api/actions/empty-trash
  Body: {item_type: "email"}  -- or "all" for everything
  Response: {permanently_deleted: 150, space_freed_bytes: 45678900}

GET /api/actions/space-analysis
  Response: {
    total_bytes: 12345678900,
    by_type: {email: {count, bytes}, photos: {count, bytes}, ...},
    top_space_consumers: [
      {type: "email", id: 123, subject: "...", bytes: 50000000, attachments: 3},
      ...
    ],
    potential_savings: {
      spam: {count: 2847, bytes: 890000000},
      newsletters: {count: 12456, bytes: 2300000000},
      large_attachments: {count: 89, bytes: 4500000000},
      duplicates: {count: 234, bytes: 780000000}
    }
  }

GET /api/tags
  Response: {tags: [{id, name, color, item_count}]}

POST /api/tags
  Body: {name: "Important Projects", color: "#e53935"}
  Response: {id: 1, name: "Important Projects", color: "#e53935"}

DELETE /api/tags/{id}
  Response: {deleted: true}
```

**Steps:**
1. Create actions.py router with all endpoints
2. Space analysis: query `raw_size_bytes` for emails, `size_bytes` for photos/attachments
3. Newsletter detection: GROUP BY from_address, flag senders with >20 emails and common newsletter patterns (unsubscribe, noreply, marketing)
4. Spam detection: use Gmail's existing Spam label
5. Permanent delete: remove DB rows AND delete files from disk (attachments, photos)
6. All actions log to user_actions table

**Deliverables:**
- [ ] Full actions router
- [ ] Space analysis with smart suggestions
- [ ] Newsletter/spam detection
- [ ] Tag CRUD

### 2.3 — Advanced Search & Bulk Selection

**Enhanced search for identifying bulk targets:**

```
GET /api/emails/search?q=...&count_only=true
  Returns just the count and total size — for "preview before delete"

New search operators:
  larger:5mb          — emails larger than 5MB
  smaller:1kb         — emails smaller than 1KB
  older_than:2y       — emails older than 2 years
  newer_than:6m       — emails newer than 6 months
  from:noreply        — partial match on from address
  unsubscribe:true    — emails containing "unsubscribe" link
  count:>20           — senders who've sent more than 20 emails
```

**Smart filters (pre-built searches):**
```
GET /api/smart-filters
  Response: {
    filters: [
      {name: "Newsletters", query: "unsubscribe:true", count: 12456, size: "2.3 GB"},
      {name: "Spam", query: "label:Spam", count: 2847, size: "890 MB"},
      {name: "Promotions", query: "label:\"Category Promotions\"", count: 8934, size: "1.1 GB"},
      {name: "Large emails (>5MB)", query: "larger:5mb", count: 89, size: "4.5 GB"},
      {name: "Old & unread", query: "is:unread older_than:3y", count: 45678, size: "8.2 GB"},
      {name: "Social notifications", query: "label:\"Category Social\"", count: 23456, size: "3.4 GB"},
      {name: "No-reply senders", query: "from:noreply OR from:no-reply", count: 34567, size: "5.1 GB"}
    ]
  }
```

**Steps:**
1. Add new search operators to the existing search parser in emails.py
2. Create smart-filters endpoint that pre-computes common cleanup targets
3. Add `count_only` mode to search for fast "how many match?" checks

**Deliverables:**
- [ ] Extended search operators
- [ ] Smart filters with counts and sizes
- [ ] Count-only search mode

### 2.4 — Frontend: Selection & Actions UI

**Components to create/modify:**

1. **Selection system** (modify EmailList.tsx, EmailRow.tsx):
   - Checkbox on each row (functional now, was visual-only)
   - "Select all" checkbox in header
   - "Select all X matching" for search results (beyond current page)
   - Selection count badge: "47 selected"
   - Shift+click for range selection

2. **Action toolbar** (new component: ActionToolbar.tsx):
   - Appears above email list when items are selected
   - Buttons: Delete, Star/Unstar, Mark Read/Unread, Label, Tag
   - Each button shows confirmation with count: "Delete 47 emails?"
   - Delete button shows space: "Delete 47 emails (freeing 234 MB)"

3. **Trash view** (new component: TrashView.tsx):
   - Accessible from sidebar
   - Shows deleted items grouped by type
   - "Restore" and "Permanently Delete" buttons
   - "Empty Trash" with size summary: "Permanently delete 2,847 items, freeing 4.2 GB?"
   - Warning: "This cannot be undone. Files will be removed from disk."

4. **Space Manager** (new component: SpaceManager.tsx):
   - Accessible from Analytics or sidebar
   - Visual breakdown: pie/bar chart of space by type
   - Smart suggestions: "Delete 2,847 spam emails to free 890 MB"
   - Each suggestion has a "Preview" (shows the emails) and "Delete All" button
   - Top space consumers list with individual delete buttons

5. **Tag Manager** (new component: TagManager.tsx):
   - Create/edit/delete custom tags
   - Color picker for tag colors
   - Tag pills displayed on email rows and detail views
   - Tag filter in sidebar

6. **Label management** (modify Sidebar.tsx, EmailView.tsx):
   - Right-click or dropdown to apply/remove labels
   - "Move to" dropdown
   - Drag-and-drop emails to sidebar labels (stretch goal)

7. **Confirmation dialogs** (new component: ConfirmDialog.tsx):
   - Reusable modal for all destructive actions
   - Shows count, size impact, and clear warning text
   - "Don't show again" checkbox for repeat actions

**Steps:**
1. Build selection state management (useSelection hook)
2. Build ActionToolbar component
3. Wire checkboxes into EmailRow
4. Build ConfirmDialog
5. Build TrashView
6. Build SpaceManager
7. Build TagManager
8. Update Sidebar with Trash and Tags sections
9. Add keyboard shortcuts: x = toggle select, # = delete, e = archive

**Deliverables:**
- [ ] Multi-select with shift-click and select-all
- [ ] Action toolbar with all operations
- [ ] Trash view with restore and permanent delete
- [ ] Space manager with smart suggestions
- [ ] Tag system (create, assign, filter)
- [ ] Confirmation dialogs for destructive actions
- [ ] Keyboard shortcuts for actions

---

## Implementation Order

### Phase A: Write Actions (1-2 sessions)
Build the write actions first since they work in the current terminal-launched app.

```
Session 1:
  1. Database migrations (2.1)
  2. Actions API router (2.2)
  3. Advanced search operators (2.3)
  4. Frontend selection + action toolbar (2.4 items 1-4)

Session 2:
  5. Space manager (2.4 item 4)
  6. Tag system (2.4 items 5-6)
  7. Keyboard shortcuts
  8. Polish and test
```

### Phase B: Easy Install (2-3 sessions)
Then package everything into a desktop app.

```
Session 3:
  1. Electron shell (1.1)
  2. Bundle Python backend with PyInstaller
  3. Bundle built frontend (vite build)
  4. Test launch cycle

Session 4:
  5. Setup wizard UI (1.2)
  6. Takeout folder scanner
  7. Import progress UI
  8. First-launch flow

Session 5:
  9. Build .dmg for arm64 + x64 (1.3)
  10. GitHub Release
  11. Test on clean Mac (your dad's machine)
  12. README with screenshots
```

---

## Non-Goals (for now)
- Windows/Linux support (macOS only for v2)
- Sync changes back to mbox/source files
- Real-time Gmail sync
- Composing/sending emails
- Multi-user access control
- Mobile app

---

## Success Criteria
- [ ] Dad can install ChadOS from a .dmg without help
- [ ] Dad can import his Takeout without using the terminal
- [ ] A user can identify and bulk-delete spam/newsletters, freeing gigabytes
- [ ] Trash system prevents accidental data loss
- [ ] All actions are undoable (until trash is emptied)
