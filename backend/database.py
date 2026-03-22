import sqlite3
from pathlib import Path
from config import DB_PATH, ensure_dirs

def get_connection(readonly: bool = False) -> sqlite3.Connection:
    ensure_dirs()
    if readonly:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
    return conn

def init_db(skip_fts: bool = False):
    """Initialize the database schema.

    Args:
        skip_fts: If True, skip creating FTS table and triggers (for bulk import).
                  Call build_fts() after import to create the FTS index.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE,
            thread_id TEXT,
            from_address TEXT,
            from_name TEXT,
            to_addresses TEXT,  -- JSON array
            cc_addresses TEXT,  -- JSON array
            bcc_addresses TEXT, -- JSON array
            subject TEXT,
            date TEXT,          -- ISO timestamp
            date_unix INTEGER,  -- Unix timestamp for fast sorting
            body_text TEXT,
            body_html TEXT,
            labels TEXT,        -- JSON array
            has_attachments INTEGER DEFAULT 0,
            is_read INTEGER DEFAULT 1,
            is_starred INTEGER DEFAULT 0,
            raw_size_bytes INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_emails_date_unix ON emails(date_unix DESC);
        CREATE INDEX IF NOT EXISTS idx_emails_thread_id ON emails(thread_id);
        CREATE INDEX IF NOT EXISTS idx_emails_from_address ON emails(from_address);
        CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
        CREATE INDEX IF NOT EXISTS idx_emails_has_attachments ON emails(has_attachments);
        CREATE INDEX IF NOT EXISTS idx_emails_is_starred ON emails(is_starred);

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER NOT NULL,
            filename TEXT,
            content_type TEXT,
            size_bytes INTEGER DEFAULT 0,
            file_path TEXT,
            FOREIGN KEY (email_id) REFERENCES emails(id)
        );

        CREATE INDEX IF NOT EXISTS idx_attachments_email_id ON attachments(email_id);

        CREATE TABLE IF NOT EXISTS labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            email_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS email_labels (
            email_id INTEGER NOT NULL,
            label_id INTEGER NOT NULL,
            PRIMARY KEY (email_id, label_id),
            FOREIGN KEY (email_id) REFERENCES emails(id),
            FOREIGN KEY (label_id) REFERENCES labels(id)
        );

        CREATE INDEX IF NOT EXISTS idx_email_labels_label_id ON email_labels(label_id);
        CREATE INDEX IF NOT EXISTS idx_email_labels_email_id ON email_labels(email_id);

        -- Phase 2: Photos
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,           -- original path on disk
            filename TEXT,
            title TEXT,
            description TEXT,
            mime_type TEXT,
            width INTEGER,
            height INTEGER,
            size_bytes INTEGER DEFAULT 0,
            date_taken TEXT,                 -- ISO timestamp
            date_taken_unix INTEGER,         -- for fast sorting
            date_created TEXT,
            creation_unix INTEGER,
            latitude REAL,
            longitude REAL,
            altitude REAL,
            camera_make TEXT,
            camera_model TEXT,
            device_type TEXT,                -- e.g. ANDROID_PHONE, IOS
            is_video INTEGER DEFAULT 0,
            duration_seconds REAL,
            thumbnail_path TEXT,             -- path to generated thumbnail
            google_photos_url TEXT,
            is_favorite INTEGER DEFAULT 0,
            source_album TEXT,               -- album folder name from Takeout
            file_hash TEXT                   -- for deduplication
        );

        CREATE INDEX IF NOT EXISTS idx_photos_date_taken_unix ON photos(date_taken_unix DESC);
        CREATE INDEX IF NOT EXISTS idx_photos_source_album ON photos(source_album);
        CREATE INDEX IF NOT EXISTS idx_photos_is_video ON photos(is_video);
        CREATE INDEX IF NOT EXISTS idx_photos_file_hash ON photos(file_hash);
        CREATE INDEX IF NOT EXISTS idx_photos_mime_type ON photos(mime_type);

        CREATE TABLE IF NOT EXISTS albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            photo_count INTEGER DEFAULT 0,
            cover_photo_id INTEGER,
            FOREIGN KEY (cover_photo_id) REFERENCES photos(id)
        );

        CREATE TABLE IF NOT EXISTS photo_albums (
            photo_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            PRIMARY KEY (photo_id, album_id),
            FOREIGN KEY (photo_id) REFERENCES photos(id),
            FOREIGN KEY (album_id) REFERENCES albums(id)
        );

        CREATE INDEX IF NOT EXISTS idx_photo_albums_album_id ON photo_albums(album_id);
        CREATE INDEX IF NOT EXISTS idx_photo_albums_photo_id ON photo_albums(photo_id);

        -- Phase 3: Contacts
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            given_name TEXT,
            family_name TEXT,
            emails TEXT,          -- JSON array of {type, address}
            phones TEXT,          -- JSON array of {type, number}
            organization TEXT,
            title TEXT,
            notes TEXT,
            photo_path TEXT,
            groups TEXT,          -- JSON array of group names
            source_file TEXT,
            UNIQUE(name, emails)
        );

        CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name);

        -- Phase 3: Calendar Events
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calendar_name TEXT,
            uid TEXT,
            summary TEXT,
            description TEXT,
            location TEXT,
            start_time TEXT,      -- ISO timestamp
            end_time TEXT,        -- ISO timestamp
            start_unix INTEGER,
            end_unix INTEGER,
            is_all_day INTEGER DEFAULT 0,
            recurrence TEXT,
            organizer TEXT,
            attendees TEXT,       -- JSON array of {name, email, status}
            status TEXT,
            source_file TEXT,
            UNIQUE(uid, calendar_name)
        );

        CREATE INDEX IF NOT EXISTS idx_calendar_events_start_unix ON calendar_events(start_unix DESC);
        CREATE INDEX IF NOT EXISTS idx_calendar_events_calendar_name ON calendar_events(calendar_name);
        CREATE INDEX IF NOT EXISTS idx_calendar_events_uid ON calendar_events(uid);

        -- Phase 3: Chat Conversations
        CREATE TABLE IF NOT EXISTS chat_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            participants TEXT,    -- JSON array of {name, email}
            type TEXT,            -- 'DM', 'Space', 'Group'
            source_folder TEXT UNIQUE
        );

        CREATE INDEX IF NOT EXISTS idx_chat_conversations_type ON chat_conversations(type);

        -- Phase 3: Chat Messages
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_name TEXT,
            sender_email TEXT,
            content TEXT,
            timestamp TEXT,       -- ISO timestamp
            timestamp_unix INTEGER,
            message_type TEXT DEFAULT 'text',
            FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp_unix ON chat_messages(timestamp_unix DESC);

        -- Phase 3: Drive Files
        CREATE TABLE IF NOT EXISTS drive_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            path TEXT UNIQUE,
            parent_path TEXT,
            mime_type TEXT,
            size_bytes INTEGER DEFAULT 0,
            modified_time TEXT,
            modified_unix INTEGER,
            is_folder INTEGER DEFAULT 0,
            extracted_text TEXT,
            source_file TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_drive_files_parent_path ON drive_files(parent_path);
        CREATE INDEX IF NOT EXISTS idx_drive_files_mime_type ON drive_files(mime_type);
        CREATE INDEX IF NOT EXISTS idx_drive_files_modified_unix ON drive_files(modified_unix DESC);

        -- Phase 3: Notes (Google Keep)
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            color TEXT,
            labels TEXT,          -- JSON array
            is_archived INTEGER DEFAULT 0,
            is_pinned INTEGER DEFAULT 0,
            is_trashed INTEGER DEFAULT 0,
            created_time TEXT,
            modified_time TEXT,
            source_file TEXT UNIQUE
        );

        CREATE INDEX IF NOT EXISTS idx_notes_created_time ON notes(created_time);
    """)

    if not skip_fts:
        _create_fts(cursor)

    conn.commit()
    conn.close()


def _create_fts(cursor):
    """Create FTS5 virtual table and sync triggers."""
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
            from_name,
            from_address,
            to_addresses,
            subject,
            body_text,
            content='emails',
            content_rowid='id',
            tokenize='porter unicode61'
        )
    """)

    cursor.executescript("""
        CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
            INSERT INTO emails_fts(rowid, from_name, from_address, to_addresses, subject, body_text)
            VALUES (new.id, new.from_name, new.from_address, new.to_addresses, new.subject, new.body_text);
        END;

        CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
            INSERT INTO emails_fts(emails_fts, rowid, from_name, from_address, to_addresses, subject, body_text)
            VALUES('delete', old.id, old.from_name, old.from_address, old.to_addresses, old.subject, old.body_text);
        END;

        CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
            INSERT INTO emails_fts(emails_fts, rowid, from_name, from_address, to_addresses, subject, body_text)
            VALUES('delete', old.id, old.from_name, old.from_address, old.to_addresses, old.subject, old.body_text);
            INSERT INTO emails_fts(rowid, from_name, from_address, to_addresses, subject, body_text)
            VALUES (new.id, new.from_name, new.from_address, new.to_addresses, new.subject, new.body_text);
        END;
    """)


def build_fts():
    """Build the FTS index from existing email data. Call after bulk import."""
    import time
    conn = get_connection()
    cursor = conn.cursor()

    # Drop existing FTS table and triggers if they exist (clean rebuild)
    cursor.executescript("""
        DROP TRIGGER IF EXISTS emails_ai;
        DROP TRIGGER IF EXISTS emails_ad;
        DROP TRIGGER IF EXISTS emails_au;
        DROP TABLE IF EXISTS emails_fts;
    """)
    conn.commit()

    # Create fresh FTS table
    cursor.execute("""
        CREATE VIRTUAL TABLE emails_fts USING fts5(
            from_name,
            from_address,
            to_addresses,
            subject,
            body_text,
            content='emails',
            content_rowid='id',
            tokenize='porter unicode61'
        )
    """)
    conn.commit()

    # Get total count for progress
    cursor.execute("SELECT COUNT(*) FROM emails")
    total = cursor.fetchone()[0]
    print(f"Building FTS index for {total:,} emails...")

    # Populate FTS in batches
    batch_size = 5000
    start = time.time()
    offset = 0

    while offset < total:
        cursor.execute("""
            INSERT INTO emails_fts(rowid, from_name, from_address, to_addresses, subject, body_text)
            SELECT id, from_name, from_address, to_addresses, subject, body_text
            FROM emails
            ORDER BY id
            LIMIT ? OFFSET ?
        """, (batch_size, offset))
        conn.commit()
        offset += batch_size
        elapsed = time.time() - start
        pct = min(offset / total * 100, 100)
        rate = offset / elapsed if elapsed > 0 else 0
        print(f"\r  FTS indexing: [{pct:5.1f}%] {min(offset, total):,}/{total:,} ({rate:,.0f}/sec)", end="", flush=True)

    print(f"\n  FTS index built in {time.time() - start:.1f}s")

    # Now create sync triggers for future inserts
    _create_fts_triggers(cursor)
    conn.commit()
    conn.close()


def _create_fts_triggers(cursor):
    """Create triggers to keep FTS in sync with emails table."""
    cursor.executescript("""
        CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
            INSERT INTO emails_fts(rowid, from_name, from_address, to_addresses, subject, body_text)
            VALUES (new.id, new.from_name, new.from_address, new.to_addresses, new.subject, new.body_text);
        END;

        CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
            INSERT INTO emails_fts(emails_fts, rowid, from_name, from_address, to_addresses, subject, body_text)
            VALUES('delete', old.id, old.from_name, old.from_address, old.to_addresses, old.subject, old.body_text);
        END;

        CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
            INSERT INTO emails_fts(emails_fts, rowid, from_name, from_address, to_addresses, subject, body_text)
            VALUES('delete', old.id, old.from_name, old.from_address, old.to_addresses, old.subject, old.body_text);
            INSERT INTO emails_fts(rowid, from_name, from_address, to_addresses, subject, body_text)
            VALUES (new.id, new.from_name, new.from_address, new.to_addresses, new.subject, new.body_text);
        END;
    """)


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
