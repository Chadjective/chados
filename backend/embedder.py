#!/usr/bin/env python3
"""
Standalone script to build semantic embeddings for the personal archive.

Reads items from SQLite, generates embeddings via Ollama (nomic-embed-text),
and stores them in ChromaDB for vector similarity search.

Usage:
    python embedder.py                      # Embed all types (emails limited to 50K)
    python embedder.py --type email          # Embed only emails
    python embedder.py --type calendar       # Embed only calendar events
    python embedder.py --type chat           # Embed only chat messages
    python embedder.py --type contact        # Embed only contacts
    python embedder.py --type drive          # Embed only drive files
    python embedder.py --limit 10000         # Limit emails to 10K (default 50K)
    python embedder.py --reset               # Clear all embeddings and start fresh
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Add project root to path so we can import config
sys.path.insert(0, str(Path(__file__).parent))
from config import DB_PATH

CHROMA_DIR = Path.home() / "personal-archive-data" / "chroma"
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
COLLECTION_NAME = "archive_embeddings"
BATCH_SIZE = 50
DEFAULT_EMAIL_LIMIT = 50000
OLLAMA_TIMEOUT = 120.0  # seconds per batch


# ---------------------------------------------------------------------------
# ChromaDB setup
# ---------------------------------------------------------------------------

def get_chroma_collection():
    """Get or create the ChromaDB collection."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def reset_collection():
    """Delete and recreate the collection."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted collection '{COLLECTION_NAME}'")
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"Created fresh collection '{COLLECTION_NAME}'")
    return collection


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    """Open a read-only connection to the archive database."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA mmap_size=268435456")
    return conn


def table_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


# ---------------------------------------------------------------------------
# Ollama embedding
# ---------------------------------------------------------------------------

def check_ollama() -> bool:
    """Verify Ollama is running and the model is available."""
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        if resp.status_code != 200:
            return False
        models = resp.json().get("models", [])
        available = [m.get("name", "") for m in models]
        # Check for exact match or match without tag
        for name in available:
            if name == EMBED_MODEL or name.startswith(f"{EMBED_MODEL}:"):
                return True
        print(f"Model '{EMBED_MODEL}' not found. Available: {available}")
        print(f"Run: ollama pull {EMBED_MODEL}")
        return False
    except httpx.ConnectError:
        print(f"Cannot connect to Ollama at {OLLAMA_URL}")
        print("Start Ollama first: ollama serve")
        return False
    except Exception as e:
        print(f"Error checking Ollama: {e}")
        return False


def embed_texts(texts: List[str], client: httpx.Client) -> List[List[float]]:
    """Generate embeddings for a batch of texts via Ollama."""
    resp = client.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["embeddings"]


# ---------------------------------------------------------------------------
# Text formatters for each content type
# ---------------------------------------------------------------------------

def format_email(row: sqlite3.Row) -> str:
    from_name = row["from_name"] or ""
    from_addr = row["from_address"] or ""
    subject = row["subject"] or "(no subject)"
    body = (row["body_text"] or "")[:2000]
    return f"From: {from_name} <{from_addr}>\nSubject: {subject}\n\n{body}"


def format_calendar(row: sqlite3.Row) -> str:
    summary = row["summary"] or "(no title)"
    start = row["start_time"] or ""
    location = row["location"] or ""
    desc = (row["description"] or "")[:1000]
    parts = [f"Event: {summary}", f"Date: {start}"]
    if location:
        parts.append(f"Location: {location}")
    if desc:
        parts.append(desc)
    return "\n".join(parts)


def format_chat_message(row: sqlite3.Row) -> str:
    sender = row["sender_name"] or "Unknown"
    content = row["content"] or ""
    return f"{sender}: {content}"


def format_contact(row: sqlite3.Row) -> str:
    name = row["name"] or ""
    emails = row["emails"] or ""
    org = row["organization"] or ""
    title = row["title"] or ""
    parts = []
    if name:
        parts.append(f"Name: {name}")
    if emails:
        parts.append(f"Email: {emails}")
    if org:
        parts.append(f"Org: {org}")
    if title:
        parts.append(f"Title: {title}")
    return "\n".join(parts)


def format_drive(row: sqlite3.Row) -> str:
    filename = row["filename"] or ""
    path = row["path"] or ""
    text = (row["extracted_text"] or "")[:2000]
    parts = [f"File: {filename}"]
    if path:
        parts.append(f"Path: {path}")
    if text:
        parts.append(text)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Metadata extractors
# ---------------------------------------------------------------------------

def email_metadata(row: sqlite3.Row) -> Dict:
    return {
        "type": "email",
        "item_id": str(row["id"]),
        "title": (row["subject"] or "(no subject)")[:200],
        "date": row["date"] or "",
    }


def calendar_metadata(row: sqlite3.Row) -> Dict:
    return {
        "type": "calendar",
        "item_id": str(row["id"]),
        "title": (row["summary"] or "(no title)")[:200],
        "date": row["start_time"] or "",
    }


def chat_metadata(row: sqlite3.Row) -> Dict:
    return {
        "type": "chat",
        "item_id": str(row["id"]),
        "title": (row["sender_name"] or "")[:200],
        "date": row["timestamp"] or "",
    }


def contact_metadata(row: sqlite3.Row) -> Dict:
    return {
        "type": "contact",
        "item_id": str(row["id"]),
        "title": (row["name"] or "")[:200],
        "date": "",
    }


def drive_metadata(row: sqlite3.Row) -> Dict:
    return {
        "type": "drive",
        "item_id": str(row["id"]),
        "title": (row["filename"] or "")[:200],
        "date": row["modified_time"] or "",
    }


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

class Progress:
    def __init__(self, total: int, label: str):
        self.total = total
        self.label = label
        self.done = 0
        self.start_time = time.time()
        self.skipped = 0

    def advance(self, n: int = 1):
        self.done += n
        elapsed = time.time() - self.start_time
        rate = self.done / elapsed if elapsed > 0 else 0
        pct = self.done / self.total * 100 if self.total > 0 else 100
        eta_secs = (self.total - self.done) / rate if rate > 0 else 0
        eta_min = eta_secs / 60
        print(
            f"\r  {self.label}: [{pct:5.1f}%] {self.done:,}/{self.total:,} "
            f"({rate:,.1f}/sec, ETA {eta_min:.1f}m, skipped {self.skipped:,})",
            end="",
            flush=True,
        )

    def finish(self):
        elapsed = time.time() - self.start_time
        new = self.done - self.skipped
        print(
            f"\n  Done: {new:,} new embeddings, {self.skipped:,} skipped "
            f"in {elapsed:.1f}s"
        )


# ---------------------------------------------------------------------------
# Core embedding loop
# ---------------------------------------------------------------------------

def get_existing_ids(collection, item_type: str) -> set:
    """Get all IDs already embedded for a given type."""
    existing = set()
    try:
        # ChromaDB get with where filter
        result = collection.get(
            where={"type": item_type},
            include=[],
        )
        if result and result["ids"]:
            existing = set(result["ids"])
    except Exception:
        pass
    return existing


def embed_type(
    conn: sqlite3.Connection,
    collection,
    item_type: str,
    query: str,
    formatter,
    meta_fn,
    id_prefix: str,
    limit: Optional[int] = None,
):
    """Embed all items of a given type."""
    # Count total
    count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
    # Strip ORDER BY for count
    if "ORDER BY" in count_query:
        count_query = count_query[:count_query.index("ORDER BY")]
    if limit:
        total = min(conn.execute(count_query).fetchone()[0], limit)
    else:
        total = conn.execute(count_query).fetchone()[0]

    if total == 0:
        print(f"  {item_type}: no items to embed")
        return

    # Get already-embedded IDs for resumability
    existing_ids = get_existing_ids(collection, item_type)
    print(f"  {item_type}: {total:,} items to process, {len(existing_ids):,} already embedded")

    progress = Progress(total, item_type)
    http_client = httpx.Client()

    try:
        if limit:
            full_query = f"{query} LIMIT {limit}"
        else:
            full_query = query

        cursor = conn.execute(full_query)
        batch_ids = []        # type: List[str]
        batch_texts = []      # type: List[str]
        batch_metas = []      # type: List[Dict]

        while True:
            rows = cursor.fetchmany(BATCH_SIZE)
            if not rows:
                break

            for row in rows:
                doc_id = f"{id_prefix}_{row['id']}"

                # Skip if already embedded (resumability)
                if doc_id in existing_ids:
                    progress.skipped += 1
                    progress.advance()
                    continue

                text = formatter(row)
                if not text or not text.strip():
                    progress.skipped += 1
                    progress.advance()
                    continue

                batch_ids.append(doc_id)
                batch_texts.append(text)
                batch_metas.append(meta_fn(row))

                # Process batch when full
                if len(batch_ids) >= BATCH_SIZE:
                    _flush_batch(collection, http_client, batch_ids, batch_texts, batch_metas)
                    progress.advance(len(batch_ids))
                    batch_ids.clear()
                    batch_texts.clear()
                    batch_metas.clear()

            # Handle rows that were skipped (already in progress.advance)
            remaining_in_batch = len(rows) - len(batch_ids)
            # We already advanced for skipped rows inside the loop

        # Flush remaining
        if batch_ids:
            _flush_batch(collection, http_client, batch_ids, batch_texts, batch_metas)
            progress.advance(len(batch_ids))

    finally:
        http_client.close()

    progress.finish()


def _flush_batch(
    collection,
    client: httpx.Client,
    ids: List[str],
    texts: List[str],
    metas: List[Dict],
):
    """Embed and upsert a batch into ChromaDB."""
    if not ids:
        return

    try:
        embeddings = embed_texts(texts, client)
    except httpx.HTTPStatusError as e:
        print(f"\n  Ollama error: {e.response.status_code} - {e.response.text[:200]}")
        raise
    except httpx.ConnectError:
        print("\n  Lost connection to Ollama. Is it still running?")
        raise

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metas,
    )


# ---------------------------------------------------------------------------
# Type-specific embedding entrypoints
# ---------------------------------------------------------------------------

def embed_emails(conn: sqlite3.Connection, collection, limit: int):
    embed_type(
        conn=conn,
        collection=collection,
        item_type="email",
        query="SELECT * FROM emails ORDER BY date_unix DESC",
        formatter=format_email,
        meta_fn=email_metadata,
        id_prefix="email",
        limit=limit,
    )


def embed_calendar(conn: sqlite3.Connection, collection):
    embed_type(
        conn=conn,
        collection=collection,
        item_type="calendar",
        query="SELECT * FROM calendar_events ORDER BY start_unix DESC",
        formatter=format_calendar,
        meta_fn=calendar_metadata,
        id_prefix="cal",
    )


def embed_chat(conn: sqlite3.Connection, collection):
    """Embed chat messages, grouping consecutive messages from same conversation."""
    total = table_count(conn, "chat_messages")
    if total == 0:
        print("  chat: no items to embed")
        return

    existing_ids = get_existing_ids(collection, "chat")

    # Group messages by conversation for context
    rows = conn.execute("""
        SELECT cm.id, cm.conversation_id, cm.sender_name, cm.content,
               cm.timestamp, cc.name as conv_name
        FROM chat_messages cm
        LEFT JOIN chat_conversations cc ON cm.conversation_id = cc.id
        ORDER BY cm.conversation_id, cm.timestamp_unix
    """).fetchall()

    # Group consecutive messages in same conversation (up to 5 per group)
    groups = []  # type: List[Tuple[List[sqlite3.Row], str]]
    current_conv = None  # type: Optional[int]
    current_group = []  # type: List[sqlite3.Row]

    for row in rows:
        conv_id = row["conversation_id"]
        if conv_id != current_conv or len(current_group) >= 5:
            if current_group:
                groups.append((current_group, current_conv))
            current_group = [row]
            current_conv = conv_id
        else:
            current_group.append(row)

    if current_group:
        groups.append((current_group, current_conv))

    print(f"  chat: {len(groups):,} message groups from {total:,} messages, {len(existing_ids):,} already embedded")

    progress = Progress(len(groups), "chat")
    http_client = httpx.Client()

    batch_ids = []
    batch_texts = []
    batch_metas = []

    try:
        for group_rows, conv_id in groups:
            # Use first message's ID as the group ID
            first_row = group_rows[0]
            doc_id = f"chat_{first_row['id']}"

            if doc_id in existing_ids:
                progress.skipped += 1
                progress.advance()
                continue

            # Combine messages in group
            lines = []
            for r in group_rows:
                lines.append(format_chat_message(r))
            text = "\n".join(lines)

            if not text.strip():
                progress.skipped += 1
                progress.advance()
                continue

            meta = {
                "type": "chat",
                "item_id": str(first_row["id"]),
                "title": (first_row["conv_name"] or first_row["sender_name"] or "")[:200],
                "date": first_row["timestamp"] or "",
            }

            batch_ids.append(doc_id)
            batch_texts.append(text)
            batch_metas.append(meta)

            if len(batch_ids) >= BATCH_SIZE:
                _flush_batch(collection, http_client, batch_ids, batch_texts, batch_metas)
                progress.advance(len(batch_ids))
                batch_ids.clear()
                batch_texts.clear()
                batch_metas.clear()

        if batch_ids:
            _flush_batch(collection, http_client, batch_ids, batch_texts, batch_metas)
            progress.advance(len(batch_ids))

    finally:
        http_client.close()

    progress.finish()


def embed_contacts(conn: sqlite3.Connection, collection):
    embed_type(
        conn=conn,
        collection=collection,
        item_type="contact",
        query="SELECT * FROM contacts ORDER BY id",
        formatter=format_contact,
        meta_fn=contact_metadata,
        id_prefix="contact",
    )


def embed_drive(conn: sqlite3.Connection, collection):
    embed_type(
        conn=conn,
        collection=collection,
        item_type="drive",
        query="SELECT * FROM drive_files WHERE is_folder = 0 ORDER BY modified_unix DESC",
        formatter=format_drive,
        meta_fn=drive_metadata,
        id_prefix="drive",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build semantic embeddings for the personal archive")
    parser.add_argument(
        "--type",
        choices=["email", "calendar", "chat", "contact", "drive", "all"],
        default="all",
        help="Type of content to embed (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_EMAIL_LIMIT,
        help=f"Max emails to embed (default: {DEFAULT_EMAIL_LIMIT:,})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all embeddings and start fresh",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ChadOS Embedding Builder")
    print("=" * 60)

    # Check Ollama
    print("\nChecking Ollama...")
    if not check_ollama():
        sys.exit(1)
    print(f"  Ollama OK, model: {EMBED_MODEL}")

    # Check database
    print(f"\nDatabase: {DB_PATH}")
    if not DB_PATH.exists():
        print("  ERROR: Database not found")
        sys.exit(1)

    conn = get_db()
    counts = {
        "email": table_count(conn, "emails"),
        "calendar": table_count(conn, "calendar_events"),
        "chat": table_count(conn, "chat_messages"),
        "contact": table_count(conn, "contacts"),
        "drive": table_count(conn, "drive_files"),
    }
    print("  Item counts:")
    for k, v in counts.items():
        print(f"    {k}: {v:,}")

    # Setup ChromaDB
    print(f"\nChromaDB: {CHROMA_DIR}")
    if args.reset:
        collection = reset_collection()
    else:
        collection = get_chroma_collection()
        existing_count = collection.count()
        print(f"  Existing embeddings: {existing_count:,}")

    # Embed
    types_to_embed = (
        [args.type] if args.type != "all"
        else ["email", "calendar", "chat", "contact", "drive"]
    )

    start = time.time()
    print(f"\nEmbedding types: {', '.join(types_to_embed)}")
    print("-" * 40)

    for t in types_to_embed:
        print(f"\n[{t}]")
        try:
            if t == "email":
                embed_emails(conn, collection, args.limit)
            elif t == "calendar":
                embed_calendar(conn, collection)
            elif t == "chat":
                embed_chat(conn, collection)
            elif t == "contact":
                embed_contacts(conn, collection)
            elif t == "drive":
                embed_drive(conn, collection)
        except (httpx.ConnectError, httpx.HTTPStatusError) as e:
            print(f"\n  FAILED: {e}")
            print("  Stopping. Re-run to resume from where we left off.")
            break
        except Exception as e:
            print(f"\n  ERROR: {e}")
            import traceback
            traceback.print_exc()
            break

    conn.close()

    total_time = time.time() - start
    final_count = collection.count()
    print(f"\n{'=' * 40}")
    print(f"Total embeddings: {final_count:,}")
    print(f"Total time: {total_time / 60:.1f} minutes")
    print("Done.")


if __name__ == "__main__":
    main()
