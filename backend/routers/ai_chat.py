"""Phase 4C: AI Chat endpoints — RAG-powered chat using Ollama + ChromaDB."""

import json
import logging
import sqlite3
from typing import Optional, List

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from config import DB_DIR
from database import get_connection
from models import (
    AIChatRequest,
    AIChatStatusResponse,
    AISuggestResponse,
    AISource,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

OLLAMA_BASE = "http://localhost:11434"
CHAT_MODEL = "llama3.1:8b"
EMBED_MODEL = "nomic-embed-text"
CHROMA_DIR = str(DB_DIR / "chroma")

SYSTEM_PROMPT = (
    "You are an AI assistant helping the user explore their personal Google archive. "
    "You have access to their emails, photos, calendar events, contacts, chat messages, "
    "and drive files. Answer questions based on the provided context. Always cite specific "
    "items (email subjects, dates, contact names) when relevant. If you don't have enough "
    "context to answer, say so."
)

# Type-to-collection mapping for ChromaDB scope filtering
SCOPE_TYPES = {"email", "photo", "calendar", "chat", "drive", "contact", "note"}


def _get_chroma_client():
    """Get a persistent ChromaDB client."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        return client
    except Exception as e:
        logger.error("Failed to connect to ChromaDB: %s", e)
        return None


def _get_chroma_collection(client):
    """Get or create the archive collection."""
    try:
        return client.get_or_create_collection(
            name="archive",
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.error("Failed to get ChromaDB collection: %s", e)
        return None


async def _embed_text(text: str) -> Optional[List[float]]:
    """Embed text using Ollama nomic-embed-text model."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embedding")
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        return None


async def _check_ollama() -> bool:
    """Check if Ollama is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def _check_model_loaded() -> bool:
    """Check if the chat model is available in Ollama."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            if resp.status_code != 200:
                return False
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(CHAT_MODEL in m for m in models)
    except Exception:
        return False


def _query_chroma(query_embedding: List[float], n_results: int = 10,
                  scope: Optional[List[str]] = None) -> List[dict]:
    """Query ChromaDB for relevant documents."""
    client = _get_chroma_client()
    if not client:
        return []

    collection = _get_chroma_collection(client)
    if not collection:
        return []

    try:
        where_filter = None
        if scope and len(scope) > 0:
            valid_scope = [s for s in scope if s in SCOPE_TYPES]
            if valid_scope:
                if len(valid_scope) == 1:
                    where_filter = {"type": valid_scope[0]}
                else:
                    where_filter = {"type": {"$in": valid_scope}}

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = collection.query(**kwargs)

        documents = []
        if results and results.get("ids") and len(results["ids"]) > 0:
            ids = results["ids"][0]
            docs = results["documents"][0] if results.get("documents") else []
            metas = results["metadatas"][0] if results.get("metadatas") else []
            distances = results["distances"][0] if results.get("distances") else []

            for i, doc_id in enumerate(ids):
                doc = {
                    "id": doc_id,
                    "content": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "distance": distances[i] if i < len(distances) else 1.0,
                }
                documents.append(doc)

        return documents
    except Exception as e:
        logger.error("ChromaDB query failed: %s", e)
        return []


def _build_context_prompt(documents: List[dict]) -> str:
    """Build context section from retrieved documents."""
    if not documents:
        return "\n\n[No relevant context found in the archive.]"

    sections = []
    for i, doc in enumerate(documents, 1):
        meta = doc.get("metadata", {})
        doc_type = meta.get("type", "unknown")
        title = meta.get("title", "Untitled")
        date = meta.get("date", "")
        content = doc.get("content", "")[:500]  # Limit context per doc

        header = f"[{i}] ({doc_type}) {title}"
        if date:
            header += f" — {date}"
        sections.append(f"{header}\n{content}")

    return "\n\nRelevant context from the archive:\n---\n" + "\n---\n".join(sections)


def _extract_sources(documents: List[dict]) -> List[dict]:
    """Extract source references from retrieved documents."""
    sources = []
    for doc in documents:
        meta = doc.get("metadata", {})
        source = {
            "type": meta.get("type", "unknown"),
            "id": meta.get("source_id", doc.get("id", "")),
            "title": meta.get("title", "Untitled"),
            "date": meta.get("date"),
            "relevance_score": round(1.0 - doc.get("distance", 1.0), 4),
        }
        sources.append(source)
    return sources


async def _stream_chat(messages: List[dict], sources: List[dict]):
    """Stream chat response from Ollama as SSE events."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": CHAT_MODEL,
                    "messages": messages,
                    "stream": True,
                },
            ) as resp:
                if resp.status_code != 200:
                    error_body = ""
                    async for chunk in resp.aiter_text():
                        error_body += chunk
                    yield f"data: {json.dumps({'error': f'Ollama error: {resp.status_code} {error_body[:200]}'})}\n\n"
                    return

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

        # Send done event with sources
        yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"

    except httpx.ConnectError:
        yield f"data: {json.dumps({'error': 'Cannot connect to Ollama. Make sure it is running at ' + OLLAMA_BASE})}\n\n"
    except httpx.ReadTimeout:
        yield f"data: {json.dumps({'error': 'Ollama response timed out. The model may be loading.'})}\n\n"
    except Exception as e:
        logger.error("Stream chat error: %s", e)
        yield f"data: {json.dumps({'error': f'Chat error: {str(e)}'})}\n\n"


@router.post("/chat")
async def ai_chat(request: AIChatRequest):
    """RAG-powered chat endpoint with streaming SSE response."""
    # 1. Check Ollama availability
    if not await _check_ollama():
        async def error_stream():
            yield f"data: {json.dumps({'error': 'Ollama is not available. Please start Ollama and try again.'})}\n\n"
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 2. Embed the user's message
    embedding = await _embed_text(request.message)

    # 3. Query ChromaDB for relevant context
    documents = []
    sources = []
    if embedding:
        documents = _query_chroma(embedding, n_results=10, scope=request.scope)
        sources = _extract_sources(documents)

    # 4. Build messages for Ollama
    context_text = _build_context_prompt(documents)
    system_message = SYSTEM_PROMPT + context_text

    messages = [{"role": "system", "content": system_message}]

    # Add conversation history
    if request.conversation_history:
        for msg in request.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": request.message})

    # 5. Stream response
    return StreamingResponse(
        _stream_chat(messages, sources),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status", response_model=AIChatStatusResponse)
async def ai_status():
    """Check Ollama and ChromaDB status."""
    ollama_available = await _check_ollama()
    model_loaded = await _check_model_loaded() if ollama_available else False

    chroma_ready = False
    embedded_count = 0
    try:
        client = _get_chroma_client()
        if client:
            collection = _get_chroma_collection(client)
            if collection:
                chroma_ready = True
                embedded_count = collection.count()
    except Exception as e:
        logger.error("ChromaDB status check failed: %s", e)

    return AIChatStatusResponse(
        ollama_available=ollama_available,
        model_loaded=model_loaded,
        chroma_ready=chroma_ready,
        embedded_count=embedded_count,
    )


@router.post("/suggest", response_model=AISuggestResponse)
async def ai_suggest():
    """Generate suggested questions based on recent archive data."""
    suggestions = []

    try:
        conn = get_connection(readonly=True)
        cursor = conn.cursor()

        # Get a recent email subject for a suggestion
        try:
            row = cursor.execute(
                "SELECT subject, from_name FROM emails WHERE subject IS NOT NULL "
                "AND subject != '' ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if row and row["subject"]:
                suggestions.append(
                    f"What emails have I received from {row['from_name'] or 'my contacts'} recently?"
                )
        except sqlite3.OperationalError:
            pass

        # Get a recent calendar event
        try:
            row = cursor.execute(
                "SELECT summary FROM calendar_events WHERE summary IS NOT NULL "
                "AND summary != '' ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
            if row and row["summary"]:
                suggestions.append("What upcoming events do I have on my calendar?")
        except sqlite3.OperationalError:
            pass

        # Get a contact name for suggestion
        try:
            row = cursor.execute(
                "SELECT name FROM contacts WHERE name IS NOT NULL AND name != '' "
                "ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
            if row and row["name"]:
                suggestions.append(f"What do I know about {row['name']}?")
        except sqlite3.OperationalError:
            pass

        # Generic suggestions to fill up to 5
        generic = [
            "Summarize my most important emails from the last month",
            "What photos did I take last summer?",
            "Who are my most frequent email contacts?",
            "What chat conversations have I had recently?",
            "What files are in my Google Drive?",
        ]

        for g in generic:
            if len(suggestions) >= 5:
                break
            if g not in suggestions:
                suggestions.append(g)

        conn.close()
    except Exception as e:
        logger.error("Suggest error: %s", e)
        # Fall back to generic suggestions
        suggestions = [
            "Summarize my most important emails from the last month",
            "What photos did I take last summer?",
            "Who are my most frequent email contacts?",
            "What upcoming events do I have on my calendar?",
            "What files are in my Google Drive?",
        ]

    return AISuggestResponse(suggestions=suggestions[:5])
