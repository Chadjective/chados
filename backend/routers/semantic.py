"""
Semantic search API router.

Provides vector similarity search across all archive content types
using Ollama embeddings and ChromaDB.
"""

from pathlib import Path
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from models import (
    SemanticSearchItem,
    SemanticSearchResponse,
    SemanticSearchTypeGroup,
    SemanticStatusResponse,
    SemanticTypeCounts,
)

router = APIRouter(prefix="/api/semantic", tags=["semantic"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHROMA_DIR = Path.home() / "personal-archive-data" / "chroma"
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
COLLECTION_NAME = "archive_embeddings"
OLLAMA_TIMEOUT = 30.0

# Valid content types for filtering
VALID_TYPES = {"email", "calendar", "chat", "contact", "drive"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_collection():
    """Get the ChromaDB collection. Returns None if unavailable."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        return None


def _embed_query(text: str) -> List[float]:
    """Embed a search query using Ollama."""
    resp = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": [text]},
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["embeddings"][0]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/search", response_model=SemanticSearchResponse)
async def semantic_search(
    q: str = Query(..., min_length=1, description="Search query"),
    types: Optional[str] = Query(
        None,
        description="Comma-separated content types to search (email,calendar,chat,contact,drive)",
    ),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
):
    """
    Semantic search across all embedded archive content.

    Embeds the query using Ollama, searches ChromaDB for similar content,
    and returns results grouped by content type with relevance scores.
    """
    # Parse type filter
    type_filter = None  # type: Optional[List[str]]
    if types:
        type_filter = [t.strip().lower() for t in types.split(",") if t.strip()]
        invalid = [t for t in type_filter if t not in VALID_TYPES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid types: {invalid}. Valid: {sorted(VALID_TYPES)}",
            )

    # Get ChromaDB collection
    collection = _get_collection()
    if collection is None or collection.count() == 0:
        raise HTTPException(
            status_code=503,
            detail="Semantic search not available. Run embedder.py first to build the index.",
        )

    # Embed the query
    try:
        query_embedding = _embed_query(q)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Ensure it is running (ollama serve).",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama error: {e.response.status_code}",
        )

    # Build ChromaDB query
    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": limit,
        "include": ["metadatas", "documents", "distances"],
    }

    if type_filter:
        if len(type_filter) == 1:
            query_kwargs["where"] = {"type": type_filter[0]}
        else:
            query_kwargs["where"] = {"type": {"$in": type_filter}}

    # Search
    try:
        results = collection.query(**query_kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

    # Parse results
    items = []  # type: List[SemanticSearchItem]
    if results and results["ids"] and results["ids"][0]:
        ids = results["ids"][0]
        metadatas = results["metadatas"][0]
        documents = results["documents"][0]
        distances = results["distances"][0]

        for i, doc_id in enumerate(ids):
            meta = metadatas[i]
            doc_text = documents[i] or ""
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (distance / 2)
            distance = distances[i]
            score = round(1.0 - (distance / 2.0), 4)

            # Build snippet from document text
            snippet = doc_text[:300].replace("\n", " ").strip()
            if len(doc_text) > 300:
                snippet += "..."

            items.append(SemanticSearchItem(
                type=meta.get("type", "unknown"),
                id=int(meta.get("item_id", 0)),
                title=meta.get("title", ""),
                snippet=snippet,
                date=meta.get("date", ""),
                score=score,
            ))

    # Group by type
    groups = {}  # type: Dict[str, List[SemanticSearchItem]]
    for item in items:
        if item.type not in groups:
            groups[item.type] = []
        groups[item.type].append(item)

    grouped = {
        k: SemanticSearchTypeGroup(items=v, count=len(v))
        for k, v in groups.items()
    }

    return SemanticSearchResponse(
        query=q,
        total=len(items),
        results=items,
        grouped=grouped,
    )


@router.get("/status", response_model=SemanticStatusResponse)
async def semantic_status():
    """
    Return the current state of the embedding index.

    Reports total embedded items, counts per type, and whether the
    system is ready for queries.
    """
    collection = _get_collection()

    if collection is None:
        return SemanticStatusResponse(
            total_embedded=0,
            by_type=SemanticTypeCounts(),
            chroma_ready=False,
        )

    total = collection.count()

    # Count by type
    type_counts = {}  # type: Dict[str, int]
    for t in VALID_TYPES:
        try:
            result = collection.get(where={"type": t}, include=[])
            type_counts[t] = len(result["ids"]) if result and result["ids"] else 0
        except Exception:
            type_counts[t] = 0

    # Check Ollama availability
    ollama_ok = False
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0)
        ollama_ok = resp.status_code == 200
    except Exception:
        pass

    return SemanticStatusResponse(
        total_embedded=total,
        by_type=SemanticTypeCounts(
            email=type_counts.get("email", 0),
            calendar=type_counts.get("calendar", 0),
            chat=type_counts.get("chat", 0),
            contact=type_counts.get("contact", 0),
            drive=type_counts.get("drive", 0),
        ),
        chroma_ready=total > 0,
        ollama_available=ollama_ok,
    )
