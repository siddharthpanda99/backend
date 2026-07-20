"""Semantic search engine for MCP tools.

Multi-layer filtering + embedding-based similarity to find the right tool
from 2,900+ candidates without scanning everything every time.

Layers (applied in order):
  1. Category filter  — exact match on module/category
  2. Audience filter  — "planner", "executor", "system"
  3. Tag filter       — any tag keyword match
  4. Keyword filter   — substring match on name/description
  5. Semantic search  — sentence-transformers cosine similarity
  6. LLM re-ranking   — (the caller reads descriptions and picks)
"""

import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.mcp.search_engine")

_INDEX: Optional[Dict[str, Any]] = None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _get_semantic_model():
    """Lazy-load the sentence-transformers model (CPU, ~500MB RAM)."""
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as e:
        logger.warning("sentence-transformers unavailable: %s", e)
        return None


def build_index(tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build in-memory search index from a list of tool dicts.

    Each tool dict must have: name, description, inputSchema (optional).
    @node wrappers also carry: category, tags, audience.
    """
    global _INDEX

    corpus = []
    categories: Dict[str, List[int]] = {}
    audiences: Dict[str, List[int]] = {}
    tags_index: Dict[str, List[int]] = {}

    for i, t in enumerate(tools):
        name = t.get("name", "")
        desc = t.get("description", "") or ""
        cat = t.get("category", "") or ""
        aud = t.get("audience", [])
        tags = t.get("tags", []) or []

        # Build search text: name boosted, description full
        search_text = f"{name}: {desc}"
        corpus.append(search_text)

        # Inverted indexes
        if cat:
            categories.setdefault(cat, []).append(i)
        for a in aud if isinstance(aud, list) else [aud]:
            if a:
                audiences.setdefault(a, []).append(i)
        for tag in tags:
            tags_index.setdefault(tag.lower(), []).append(i)

    index: Dict[str, Any] = {
        "tools": tools,
        "corpus": corpus,
        "categories": categories,
        "audiences": audiences,
        "tags": tags_index,
        "embeddings": None,
        "model": None,
    }
    _INDEX = index

    # Eagerly load sentence-transformers model in a thread so the first
    # search call doesn't block the async event loop for 20-45s.
    import threading

    def _preload():
        try:
            from sentence_transformers import SentenceTransformer

            SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            pass

    t = threading.Thread(target=_preload, daemon=True)
    t.start()

    return index


def ensure_index(tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Get or build the search index."""
    global _INDEX
    if _INDEX is None:
        if tools is None:
            raise RuntimeError("Search index not built — call build_index(tools) first")
        _INDEX = build_index(tools)
    return _INDEX


def _compute_embeddings(index: Dict[str, Any]) -> None:
    """Compute sentence embeddings for the corpus (lazy, once)."""
    if index["embeddings"] is not None:
        return
    model = _get_semantic_model()
    if model is None:
        return
    try:
        import numpy as np

        corpus = index["corpus"]
        logger.info("Computing embeddings for %s tool descriptions...", len(corpus))
        emb = model.encode(corpus, show_progress_bar=False, convert_to_numpy=True)
        index["embeddings"] = emb
        index["model"] = model
        logger.info("Embeddings computed: shape %s", emb.shape)
    except Exception as e:
        logger.warning("Embedding computation failed: %s", e)


async def compute_embeddings_async(index: Dict[str, Any]) -> None:
    """Async-safe embedding computation via thread pool.

    Call this from async MCP tool handlers instead of the sync _compute_embeddings.
    """
    if index["embeddings"] is not None:
        return
    import asyncio

    await asyncio.to_thread(_compute_embeddings, index)


# ---------------------------------------------------------------------------
# Multi-layer search
# ---------------------------------------------------------------------------


def search_tools(
    query: str = "",
    *,
    category: Optional[str] = None,
    audience: Optional[str] = None,
    tags: Optional[List[str]] = None,
    keyword: Optional[str] = None,
    top_k: int = 20,
    min_score: float = 0.15,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Multi-layer tool search with semantic ranking.

    Layers:
      1. Category filter  (exact, optional)
      2. Audience filter  (exact, optional)
      3. Tag filter       (any-of, optional)
      4. Keyword filter   (substring on name/description, optional)
      5. Semantic search  (embedding cosine similarity)
      6. LLM re-ranking   (caller's responsibility — we return descriptions)

    Args:
        query:          Natural-language query for semantic matching.
        category:       Exact category name (e.g. "audio", "memory").
        audience:       Exact audience (e.g. "planner", "executor", "system").
        tags:           Any-of tag filter (e.g. ["search", "rag"]).
        keyword:        Substring filter on name + description.
        top_k:          Max results to return (default 20).
        min_score:      Minimum cosine similarity for semantic results.
        tools:          Optional tool list (if index not yet built).

    Returns:
        List of tool dicts with added 'score' and 'match_type' fields.
    """
    index = ensure_index(tools)
    candidates = list(range(len(index["tools"])))

    # -- Layer 1: Category ------------------------------------------------
    if category:
        cat_ids = index["categories"].get(category, [])
        cat_set = set(cat_ids)
        candidates = [i for i in candidates if i in cat_set]

    # -- Layer 2: Audience ------------------------------------------------
    if audience:
        aud_ids = index["audiences"].get(audience, [])
        aud_set = set(aud_ids)
        candidates = [i for i in candidates if i in aud_set]

    # -- Layer 3: Tags (any match) ----------------------------------------
    if tags:
        tag_ids: set = set()
        for t in tags:
            tag_ids.update(index["tags"].get(t.lower(), []))
        candidates = [i for i in candidates if i in tag_ids]

    # -- Layer 4: Keyword substring ---------------------------------------
    if keyword:
        kw = _clean(keyword)
        filtered = []
        for i in candidates:
            t = index["tools"][i]
            if kw in _clean(t.get("name", "")) or kw in _clean(
                t.get("description", "")
            ):
                filtered.append(i)
        candidates = filtered

    if not candidates:
        return []

    # -- Layer 5: Semantic search -----------------------------------------
    if query and _get_semantic_model() is not None:
        _compute_embeddings(index)
        if index["embeddings"] is not None:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            q_emb = index["model"].encode([query], convert_to_numpy=True)
            candidate_embs = index["embeddings"][candidates]
            sims = cosine_similarity(q_emb, candidate_embs)[0]

            scored = [
                (candidates[i], float(sims[i]))
                for i in range(len(candidates))
                if sims[i] >= min_score
            ]
            scored.sort(key=lambda x: -x[1])
            scored = scored[:top_k]

            results = []
            for idx, score in scored:
                t = dict(index["tools"][idx])
                t["score"] = round(score, 4)
                t["match_type"] = "semantic"
                results.append(t)
            return results

    # Fallback: no query or no model — return filtered with keyword match
    results = []
    for i in candidates[:top_k]:
        t = dict(index["tools"][i])
        t["score"] = 1.0 if keyword else 0.0
        t["match_type"] = "keyword" if keyword else "filter"
        results.append(t)
    return results


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def list_categories() -> List[Dict[str, Any]]:
    """List all tool categories with counts."""
    index = ensure_index()
    counts: Dict[str, int] = {}
    for t in index["tools"]:
        c = t.get("category", "") or "uncategorized"
        counts[c] = counts.get(c, 0) + 1
    return [
        {"category": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]


def list_audiences() -> List[Dict[str, Any]]:
    """List all tool audiences with counts."""
    index = ensure_index()
    counts: Dict[str, int] = {}
    for t in index["tools"]:
        aud = t.get("audience", [])
        if isinstance(aud, list):
            for a in aud:
                counts[a] = counts.get(a, 0) + 1
        elif aud:
            counts[aud] = counts.get(aud, 0) + 1
    return [
        {"audience": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]


def list_tags(top_n: int = 30) -> List[Dict[str, Any]]:
    """List most common tool tags."""
    index = ensure_index()
    counts: Dict[str, int] = {}
    for t in index["tools"]:
        for tag in t.get("tags", []) or []:
            counts[tag.lower()] = counts.get(tag.lower(), 0) + 1
    return [
        {"tag": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])[:top_n]
    ]


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """Find a tool by exact name."""
    index = ensure_index()
    for t in index["tools"]:
        if t.get("name") == name:
            return t
    return None


def rebuild_index(tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Force rebuild the search index (drops cached embeddings)."""
    global _INDEX
    _INDEX = None
    if tools:
        return build_index(tools)
    return {}
