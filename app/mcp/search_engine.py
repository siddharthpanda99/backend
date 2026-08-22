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
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.mcp.search_engine")
_INDEX: Optional[Dict[str, Any]] = None
_MODEL_CACHE: Optional[Any] = None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

_MODEL_LOAD_ATTEMPTED = False


def _get_semantic_model():
    """Lazy-load the sentence-transformers model (cached, CPU, ~500MB RAM)."""
    global _MODEL_CACHE, _MODEL_LOAD_ATTEMPTED
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    if _MODEL_LOAD_ATTEMPTED:
        return None
    _MODEL_LOAD_ATTEMPTED = True
    try:
        import os
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from sentence_transformers import SentenceTransformer
        # device='cpu' prevents meta-tensor errors on Windows/torch 2.6+
        _MODEL_CACHE = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        logger.info("sentence-transformers model loaded: all-MiniLM-L6-v2")
        return _MODEL_CACHE
    except Exception as e:
        logger.warning("sentence-transformers unavailable: %s", e)
        _MODEL_CACHE = None
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
        _get_semantic_model()  # uses global cache

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
# Layer 6: LLM Re-ranking
# ---------------------------------------------------------------------------

_LLM_RERANK_CACHE: Dict[str, Any] = {}


def _get_llm_client():
    """Get an LLM client for re-ranking. Tries multiple backends."""
    # Try OpenAI first
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            import openai
            return openai.OpenAI(api_key=api_key), "gpt-4o-mini"
        except Exception:
            pass

    # Try DeepSeek
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        try:
            import openai
            return openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            ), "deepseek-chat"
        except Exception:
            pass

    # Try vLLM local
    try:
        import requests
        resp = requests.get("http://localhost:8001/v1/models", timeout=2)
        if resp.status_code == 200:
            import openai
            return openai.OpenAI(
                api_key="not-needed",
                base_url="http://localhost:8001/v1"
            ), ""
    except Exception:
        pass

    return None, None


def _build_rerank_prompt(query: str, candidates: List[Dict[str, Any]]) -> str:
    """Build a structured prompt for LLM re-ranking.

    The LLM scores each tool 0-10 on relevance to the query.
    Returns JSON array with scores and reasoning.
    """
    tools_text = []
    for i, c in enumerate(candidates, 1):
        name = c.get("name", "unknown")
        desc = c.get("description", "")[:150]
        cat = c.get("category", "")
        tools_text.append(f"{i}. {name} [{cat}]: {desc}")

    return f"""You are a tool relevance scorer. Score each tool 0-10 on how well it matches the user's query.

Query: {query}

Tools:
{chr(10).join(tools_text)}

Return ONLY a JSON array (no markdown, no explanation):
[{{"name": "tool_name", "score": N, "reason": "brief reason"}}]

Score guide:
- 10: Perfect match, this is exactly what the user needs
- 7-9: Strong match, very relevant to the query
- 4-6: Partial match, related but not primary
- 1-3: Weak match, tangentially related
- 0: Not relevant at all"""


def _parse_rerank_response(response_text: str, candidates: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """Parse LLM re-ranking response into re-scored candidates."""
    import json
    import re

    # Try to extract JSON from the response
    text = response_text.strip()

    # Remove markdown code fences if present
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)

    # Try to find JSON array
    match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if not match:
        logger.warning("Could not parse LLM rerank response: %s", text[:200])
        return None

    try:
        scores = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error in rerank: %s", e)
        return None

    # Map scores back to candidates
    name_to_score = {}
    for item in scores:
        name = item.get("name", "")
        score = item.get("score", 0)
        reason = item.get("reason", "")
        if name and isinstance(score, (int, float)):
            name_to_score[name] = (score, reason)

    # Re-score candidates
    reranked = []
    for c in candidates:
        name = c.get("name", "")
        if name in name_to_score:
            llm_score, reason = name_to_score[name]
            # Blend: 60% LLM score + 40% semantic score
            semantic_score = c.get("score", 0) * 10  # normalize 0-1 to 0-10
            blended = 0.6 * llm_score + 0.4 * semantic_score
            enriched = dict(c)
            enriched["llm_score"] = llm_score
            enriched["llm_reason"] = reason
            enriched["score"] = round(blended / 10, 4)  # normalize back to 0-1
            enriched["match_type"] = "llm_reranked"
            reranked.append(enriched)
        else:
            # Keep original score for tools not scored by LLM
            reranked.append(c)

    # Sort by blended score
    reranked.sort(key=lambda x: -x.get("score", 0))
    return reranked


async def rerank_with_llm(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 5,
    max_candidates: int = 15,
) -> List[Dict[str, Any]]:
    """Re-rank search results using LLM relevance scoring.

    Takes the top-N candidates from semantic search and asks an LLM to
    score each on a 0-10 relevance scale. Results are blended:
      final_score = 0.6 * llm_score + 0.4 * semantic_score

    Falls back to original ranking if LLM is unavailable.

    Args:
        query:       The user's search query.
        candidates:  Pre-ranked tool dicts from semantic search.
        top_k:       Number of results to return.
        max_candidates: Max candidates to send to LLM (keeps prompt small).

    Returns:
        Re-ranked list of tool dicts with 'match_type' = 'llm_reranked'.
    """
    if not candidates:
        return []

    # Trim to max_candidates for LLM context
    to_rerank = candidates[:max_candidates]

    # Get LLM client
    client, model = _get_llm_client()
    if client is None:
        logger.debug("No LLM available for reranking — using semantic scores")
        return candidates[:top_k]

    try:
        prompt = _build_rerank_prompt(query, to_rerank)
        messages = [
            {"role": "system", "content": "You are a precise tool relevance scorer. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ]

        # Use minimal tokens — we just need a JSON array
        response = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
        )

        response_text = response.choices[0].message.content or ""
        reranked = _parse_rerank_response(response_text, to_rerank)

        if reranked is not None:
            logger.info(
                "LLM rerank: %d candidates -> %d re-scored",
                len(to_rerank),
                len([r for r in reranked if r.get("match_type") == "llm_reranked"]),
            )
            return reranked[:top_k]
        else:
            logger.warning("LLM rerank parse failed — falling back to semantic scores")
            return candidates[:top_k]

    except Exception as e:
        logger.warning("LLM rerank failed: %s — falling back to semantic scores", e)
        return candidates[:top_k]


def rerank_with_llm_sync(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 5,
    max_candidates: int = 15,
) -> List[Dict[str, Any]]:
    """Synchronous wrapper for rerank_with_llm."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context — run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    rerank_with_llm(query, candidates, top_k, max_candidates)
                ).result()
        else:
            return loop.run_until_complete(
                rerank_with_llm(query, candidates, top_k, max_candidates)
            )
    except RuntimeError:
        return asyncio.run(rerank_with_llm(query, candidates, top_k, max_candidates))


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
    rerank: bool = False,
) -> List[Dict[str, Any]]:
    """Multi-layer tool search with semantic + LLM re-ranking.

    Layers:
      1. Category filter  (exact, optional)
      2. Audience filter  (exact, optional)
      3. Tag filter       (any-of, optional)
      4. Keyword filter   (substring on name/description, optional)
      5. Semantic search  (embedding cosine similarity via MiniLM)
      6. LLM re-ranking   (OpenAI/DeepSeek/vLLM scores 0-10, blended 60/40)

    Args:
        query:          Natural-language query for semantic matching.
        category:       Exact category name (e.g. "audio", "memory").
        audience:       Exact audience (e.g. "planner", "executor", "system").
        tags:           Any-of tag filter (e.g. ["search", "rag"]).
        keyword:        Substring filter on name + description.
        top_k:          Max results to return (default 20).
        min_score:      Minimum cosine similarity for semantic results.
        tools:          Optional tool list (if index not yet built).
        rerank:         Enable LLM re-ranking (default False, costs API call).

    Returns:
        List of tool dicts with added 'score' and 'match_type' fields.
    """
    # If rerank=True, we fetch extra candidates for LLM re-ranking
    if rerank and top_k < 15:
        fetch_k = min(top_k * 3, 15)  # fetch 3x for re-ranking pool
    else:
        fetch_k = top_k

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
            scored = scored[:fetch_k]

            results = []
            for idx, score in scored:
                t = dict(index["tools"][idx])
                t["score"] = round(score, 4)
                t["match_type"] = "semantic"
                results.append(t)
            # Layer 6: LLM re-ranking (if enabled)
            if rerank and query and len(results) > 1:
                results = rerank_with_llm_sync(query, results, top_k=top_k)
            return results[:top_k]

    # Fallback: no model — use keyword scoring on query words
    if query:
        query_words = _clean(query).split()
        scored_candidates = []
        for i in candidates:
            t = index["tools"][i]
            name = _clean(t.get("name", ""))
            desc = _clean(t.get("description", ""))
            tags = " ".join(t.get("tags", []))
            searchable = f"{name} {desc} {tags}"
            # Score: count query word matches
            score = sum(1 for w in query_words if w in searchable)
            if score > 0:
                scored_candidates.append((i, score / len(query_words)))
        scored_candidates.sort(key=lambda x: -x[1])
        scored_candidates = scored_candidates[:fetch_k]
        results = []
        for idx, score in scored_candidates:
            t = dict(index["tools"][idx])
            t["score"] = round(score, 4)
            t["match_type"] = "keyword"
            results.append(t)
        # Layer 6: LLM re-ranking (if enabled)
        if rerank and query and len(results) > 1:
            results = rerank_with_llm_sync(query, results, top_k=top_k)
        return results[:top_k]

    # No query — return filtered
    results = []
    for i in candidates[:top_k]:
        t = dict(index["tools"][i])
        t["score"] = 0.0
        t["match_type"] = "filter"
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
