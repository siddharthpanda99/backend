"""
MCP Tool: Dynamic Workflow Execution + Discovery

Exposes workflow execution AND multi-layer search to AI agents via MCP.
Agents can search workflows semantically, discover configs, find nodes by
capability, validate merges, and run workflows.

Search layers:
  1. Category filter  (exact module/category match)
  2. Keyword filter   (substring on name/description)
  3. Node filter      (find workflows containing specific node types)
  4. Semantic search  (sentence-transformers cosine similarity)
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mcp.tools.dynamic_workflows")

# ── Workflow search index (lazy-built) ──────────────────────────────────────
_WF_INDEX: Optional[Dict[str, Any]] = None


def _build_workflow_index(workflows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build an in-memory search index over all workflows."""
    global _WF_INDEX
    corpus = []
    categories: Dict[str, List[int]] = {}
    node_types: Dict[str, List[int]] = {}

    for i, wf in enumerate(workflows):
        name = wf.get("name", "") or wf.get("id", "")
        desc = wf.get("description", "") or ""
        cat = wf.get("category", "") or ""
        nodes = wf.get("nodes", []) or wf.get("node_types", []) or []

        # Build search text: name boosted, description full
        search_text = f"{name}: {desc}"
        corpus.append(search_text)

        # Category index
        if cat:
            categories.setdefault(cat.lower(), []).append(i)

        # Node type index (for "find workflows that use KSampler" queries)
        for node in nodes:
            ntype = node if isinstance(node, str) else node.get("type", "")
            if ntype:
                node_types.setdefault(ntype.lower(), []).append(i)

    _WF_INDEX = {
        "workflows": workflows,
        "corpus": corpus,
        "categories": categories,
        "node_types": node_types,
        "embeddings": None,
        "model": None,
    }
    return _WF_INDEX


def _get_wf_index():
    """Get or build the workflow search index."""
    global _WF_INDEX
    if _WF_INDEX is not None:
        return _WF_INDEX

    from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
    runner = get_dynamic_runner()
    workflows = runner.list_workflows()
    return _build_workflow_index(workflows)


def _compute_wf_embeddings(index: Dict[str, Any]) -> None:
    """Compute sentence embeddings for workflow corpus (lazy, once)."""
    if index["embeddings"] is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")
        corpus = index["corpus"]
        logger.info("Computing embeddings for %s workflows...", len(corpus))
        emb = model.encode(corpus, show_progress_bar=False, convert_to_numpy=True)
        index["embeddings"] = emb
        index["model"] = model
        logger.info("Workflow embeddings computed: shape %s", emb.shape)
    except Exception as e:
        logger.warning("Workflow embedding computation failed: %s", e)


def _search_workflows(
    query: str = "",
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    node_type: Optional[str] = None,
    top_k: int = 20,
    min_score: float = 0.15,
) -> List[Dict[str, Any]]:
    """Multi-layer workflow search with semantic ranking.

    Layers:
      1. Category filter (exact)
      2. Node type filter (workflows containing this node)
      3. Keyword filter (substring on name/description)
      4. Semantic search (cosine similarity)
    """
    index = _get_wf_index()
    candidates = list(range(len(index["workflows"])))

    # Layer 1: Category
    if category:
        cat_ids = set(index["categories"].get(category.lower(), []))
        candidates = [i for i in candidates if i in cat_ids]

    # Layer 2: Node type
    if node_type:
        node_ids = set(index["node_types"].get(node_type.lower(), []))
        candidates = [i for i in candidates if i in node_ids]

    # Layer 3: Keyword substring
    if keyword:
        kw = keyword.lower().strip()
        filtered = []
        for i in candidates:
            wf = index["workflows"][i]
            name = (wf.get("name", "") or wf.get("id", "")).lower()
            desc = (wf.get("description", "") or "").lower()
            if kw in name or kw in desc:
                filtered.append(i)
        candidates = filtered

    if not candidates:
        return []

    # Layer 4: Semantic search
    if query:
        try:
            _compute_wf_embeddings(index)
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
                    wf = dict(index["workflows"][idx])
                    wf["score"] = round(score, 4)
                    wf["match_type"] = "semantic"
                    results.append(wf)
                return results
        except Exception:
            pass

    # Fallback: keyword/filter match
    results = []
    for i in candidates[:top_k]:
        wf = dict(index["workflows"][i])
        wf["score"] = 1.0 if keyword else 0.0
        wf["match_type"] = "keyword" if keyword else "filter"
        results.append(wf)
    return results


def _get_runner_from_context():
    """Get workflow runner from plugin context if available, else fallback."""
    try:
        from app.mcp.plugin_context import get_plugin_ctx
        ctx = get_plugin_ctx()
        if ctx and ctx.has("workflow_runner"):
            return ctx.workflow_runner
    except Exception:
        pass
    # Fallback to direct import
    from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
    return get_dynamic_runner()


def register_dynamic_workflow_tools(mcp):
    """Register dynamic workflow tools with the MCP server."""

    @mcp.tool()
    async def workflow_search(
        query: str = "",
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        node_type: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Multi-layer semantic search across all YAML workflows.

        Find the right workflow for a user's natural-language request.
        Supports pre-filters (category, node_type, keyword) to narrow
        candidates before the expensive semantic match.

        Args:
            query:      Natural-language description of what the user wants
                        (e.g. "generate a cyberpunk cityscape with SD1.5").
            category:   Exact category name (e.g. "sd15", "sdxl", "face",
                        "depth", "segmentation", "controlnet").
            keyword:    Fast substring filter on workflow name + description.
            node_type:  Find workflows containing a specific node type
                        (e.g. "KSampler", "CheckpointLoaderSimple", "VAEDecode").
            top_k:      Maximum results (default 20, max 50).

        Returns:
            List of matched workflows with id, name, description, category,
            score (cosine similarity 0-1), and match_type.
        """
        top_k = min(top_k, 50)
        return _search_workflows(
            query=query,
            category=category,
            keyword=keyword,
            node_type=node_type,
            top_k=top_k,
        )

    @mcp.tool()
    async def workflow_search_categories() -> List[Dict[str, Any]]:
        """List all workflow categories with their counts.

        Use this to discover which workflow domains are available
        before narrowing a search (e.g. "sd15", "sdxl", "face", "depth").
        """
        index = _get_wf_index()
        return [
            {"category": k, "count": len(v)}
            for k, v in sorted(index["categories"].items(), key=lambda x: -len(x[1]))
        ]

    @mcp.tool()
    async def workflow_search_suggest(prefix: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Quick name-based suggestion for autocomplete-like use cases.

        Args:
            prefix: Start of a workflow name or id (e.g. "sd1" → sd15, sd15_cn).
            top_k:  Max suggestions (default 10).
        """
        index = _get_wf_index()
        p = prefix.lower()
        matches = []
        for wf in index["workflows"]:
            name = (wf.get("name", "") or wf.get("id", "")).lower()
            wf_id = (wf.get("id", "") or "").lower()
            if p in name or p in wf_id:
                matches.append({
                    "id": wf.get("id"),
                    "name": wf.get("name"),
                    "category": wf.get("category", ""),
                })
            if len(matches) >= top_k:
                break
        return matches

    @mcp.tool()
    async def workflow_config_search(
        query: str = "",
        workflow_id: Optional[str] = None,
        keyword: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search data-config YAML files by name, workflow, or parameter keys.

        Args:
            query:       Search text (matches config name, description, keys).
            workflow_id: Filter by workflow_id (e.g. "sd15", "depth_anything_v2").
            keyword:     Substring filter on config name or parameter keys.
            top_k:       Max results (default 20).
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()
        configs = runner.list_configs(workflow_id=workflow_id)

        q = (query or keyword or "").lower().strip()
        if q:
            configs = [
                c for c in configs
                if q in (c.get("name", "") or "").lower()
                or q in (c.get("id", "") or "").lower()
                or any(q in k.lower() for k in c.get("data_config_keys", []))
            ]

        return configs[:top_k]

    @mcp.tool()
    async def workflow_node_search(
        query: str = "",
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search @node wrappers that can be used as workflow nodes.

        Finds nodes by name, description, category, or tags.
        Use this to discover available nodes before building a pipeline.

        Args:
            query:    Natural-language description (e.g. "restore faces").
            category: Exact category (e.g. "face", "upscale", "sampling").
            keyword:  Substring filter on node name/description.
            top_k:    Max results (default 20).
        """
        try:
            from common_lib.modules.plugins.discovery import discover_nodes
            nodes = list(discover_nodes())
        except Exception:
            nodes = []

        q = (query or keyword or "").lower().strip()
        results = nodes

        if category:
            results = [n for n in results if (n.get("category") or "").lower() == category.lower()]

        if q:
            results = [
                n for n in results
                if q in (n.get("name") or "").lower()
                or q in (n.get("description") or "").lower()
                or any(q in t.lower() for t in (n.get("tags") or []))
            ]

        return [
            {
                "name": n.get("name", ""),
                "category": n.get("category", ""),
                "description": (n.get("description") or "")[:200],
                "tags": n.get("tags", []),
                "input_schema": n.get("input_schema", {}),
            }
            for n in results[:top_k]
        ]

    @mcp.tool()
    async def list_vision_workflows() -> List[Dict[str, Any]]:
        """
        List all available YAML workflows for image generation, face editing,
        segmentation, depth estimation, pose estimation, and other vision tasks.

        Returns a list of workflow summaries with id, name, category, node count.
        Use the workflow_id with run_vision_workflow to execute.
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()
        workflows = runner.list_workflows()
        return [
            {
                "id": w.get("id"),
                "name": w.get("name"),
                "description": w.get("description", ""),
                "category": w.get("category", ""),
                "node_count": w.get("node_count", 0),
            }
            for w in workflows
        ]

    @mcp.tool()
    async def list_workflow_configs(workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available data-config YAML files for workflows.
        Each config is a named parameter set (prompt, steps, CFG, resolution, etc.)

        Args:
            workflow_id: Optional filter — only show configs for this workflow_id.

        Returns config summaries with id, name, workflow_id, file path, and parameter keys.
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()
        return runner.list_configs(workflow_id=workflow_id)

    @mcp.tool()
    async def validate_workflow_merge(
        workflow: str,
        config: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Dry-run: merge a workflow YAML with a data-config and show the resolved
        graph without executing. Useful for debugging parameter resolution.

        Args:
            workflow: Workflow YAML path, dict, or workflow_id from registry.
            config: Data-config YAML path or dict (optional).
            overrides: Runtime parameter overrides (optional).

        Returns the merged workflow with resolved node properties and parameters.
        """
        from common_lib.modules.workflows.dynamic_runner import get_dynamic_runner
        runner = get_dynamic_runner()

        wf = runner.load_workflow(workflow)
        if not wf:
            return {"error": f"Workflow not found: {workflow}"}

        cfg = runner.load_config(config) if config else {}
        merged = runner.merge(wf, cfg, overrides)

        return {
            "workflow_id": merged.get("id"),
            "node_count": len(merged.get("nodes", [])),
            "edge_count": len(merged.get("edges", [])),
            "resolved_params": merged.get("metadata", {}).get("resolved_params", {}),
            "nodes": [
                {
                    "id": n.get("id"),
                    "type": n.get("type"),
                    "properties": n.get("properties") or n.get("inputs", {}),
                }
                for n in merged.get("nodes", [])
            ],
        }

    @mcp.tool()
    async def run_vision_workflow(
        workflow: str,
        config: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a vision workflow with a data-config. This is the primary tool
        for running image generation, face editing, segmentation, depth estimation,
        pose estimation, and other visual AI pipelines.

        Args:
            workflow: Workflow YAML path, dict, or workflow_id (e.g. "sd15", "depth_anything_v2",
                      "face_swap_codeformer", "dwpose_estimation", "yolo_world_detect").
            config: Data-config YAML path or dict with data_config block containing
                    prompt, steps, cfg, width, height, etc.
            overrides: Runtime parameter overrides applied last (highest priority).

        Returns:
            status: "completed" or "failed"
            workflow_id: The workflow that was executed
            params: Resolved parameters used
            outputs: Output data (file paths, etc.)
            duration_ms: Execution time in milliseconds
            error: Error message if failed

        Examples:
            run_vision_workflow("sd15", "data-config/sd15/cyberpunk_streetscape.yaml")
            run_vision_workflow("depth_anything_v2", overrides={"image_path": "photo.png"})
            run_vision_workflow("face_swap_codeformer", overrides={
                "source_image": "face.png",
                "target_image": "portrait.png"
            })
        """
        runner = _get_runner_from_context()

        result = await runner.run(
            workflow=workflow,
            config=config,
            overrides=overrides,
        )
        return result

    @mcp.tool()
    async def run_workflow_sse(
        workflow: str,
        config: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow and return all SSE events as a list.
        Same as run_vision_workflow but returns the full event stream
        for debugging and detailed progress tracking.

        Args:
            workflow: Workflow YAML path or workflow_id.
            config: Data-config YAML path or dict.
            overrides: Runtime parameter overrides.

        Returns:
            events: List of all SSE events from the execution
            final_status: "completed" or "failed"
        """
        runner = _get_runner_from_context()

        events = []
        async for event in runner.run_stream(
            workflow=workflow,
            config=config,
            overrides=overrides,
        ):
            events.append(event)

        final_status = "completed"
        for event in reversed(events):
            if isinstance(event, dict):
                et = event.get("event_type", "")
                if "failed" in et:
                    final_status = "failed"
                    break
                if "completed" in et:
                    final_status = "completed"
                    break

        return {
            "events": events,
            "event_count": len(events),
            "final_status": final_status,
        }

    logger.info("Dynamic workflow MCP tools registered")
