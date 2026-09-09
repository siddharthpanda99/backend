"""
Unified Knowledge API — MCP Tool Registration (Track B).

Registers the knowledge_api facade ops as MCP tools for agent
consumption. Thin transport only: every handler delegates to
``common_lib.modules.knowledge_engine.knowledge_api.service``.

Registration is gated by ``KNOWLEDGE_MCP_ENABLED`` (off in
production by default) — see ``app/mcp/server.py``.

Usage:
    # In app/mcp/server.py:
    from app.mcp.tools.knowledge_api import register_knowledge_api_tools
    register_knowledge_api_tools(mcp_server)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.mcp.fastmcp_compat import FastMCP

from ..mcp_dependencies import resolve_knowledge_api_service

logger = logging.getLogger("mcp.tools.knowledge_api")


def register_knowledge_api_tools(mcp: FastMCP) -> None:
    """Register all unified knowledge API tools with the MCP server.

    Registers 8 tools: combined search, entity facts/changes/timeline,
    fact evidence, remember-to-pending, review decide, ontology lookup.
    """
    from common_lib.modules.knowledge_engine.knowledge_api.feature_flags import (
        is_knowledge_mcp_enabled,
    )

    if not is_knowledge_mcp_enabled():
        logger.info("knowledge_api MCP tools skipped (KNOWLEDGE_MCP_ENABLED off)")
        return

    @mcp.tool()
    async def knowledge_api_search(
        query: str,
        kb_id: str,
        store_id: Optional[str] = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Kb-scoped combined chunk + entity search.

        Args:
            query: Natural-language search query.
            kb_id: Knowledge-base scope id.
            store_id: Optional document store id (searches all stores when omitted).
            limit: Max hits per section.

        Returns:
            Dict with chunks, entities, and total.
        """
        service = resolve_knowledge_api_service()
        return service.knowledge_search(query, kb_id, store_id=store_id, limit=limit)

    @mcp.tool()
    async def knowledge_api_entity_facts(
        kb_id: str,
        entity_id: str,
        include_invalidated: bool = True,
    ) -> dict[str, Any]:
        """Facts + evidence for one entity.

        Args:
            kb_id: Knowledge-base scope id.
            entity_id: Entity id within the kb.
            include_invalidated: Include superseded history.

        Returns:
            Dict with current, invalidated, chains, and evidence.
        """
        service = resolve_knowledge_api_service()
        return service.entity_facts(
            kb_id, entity_id, include_invalidated=include_invalidated
        )

    @mcp.tool()
    async def knowledge_api_entity_changes(
        kb_id: str,
        entity_id: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record-axis changes for one entity in an optional time window.

        Args:
            kb_id: Knowledge-base scope id.
            entity_id: Entity id within the kb.
            since: ISO-8601 window start (optional).
            until: ISO-8601 window end (optional).

        Returns:
            Dict with added, ended, and corrected lists.
        """
        service = resolve_knowledge_api_service()
        return service.entity_changes(kb_id, entity_id, since=since, until=until)

    @mcp.tool()
    async def knowledge_api_entity_timeline(
        kb_id: str,
        entity_id: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> dict[str, Any]:
        """Time-ordered event stream for one entity.

        Args:
            kb_id: Knowledge-base scope id.
            entity_id: Entity id within the kb.
            since: ISO-8601 window start (optional).
            until: ISO-8601 window end (optional).

        Returns:
            Dict with events and total.
        """
        service = resolve_knowledge_api_service()
        return service.entity_timeline(kb_id, entity_id, since=since, until=until)

    @mcp.tool()
    async def knowledge_api_fact_evidence(
        kb_id: str,
        fact_id: str,
    ) -> dict[str, Any]:
        """Chunk-provenance rows for one fact.

        Args:
            kb_id: Knowledge-base scope id.
            fact_id: Fact id within the kb.

        Returns:
            Dict with fact_id, items, and total.
        """
        service = resolve_knowledge_api_service()
        return service.fact_evidence(kb_id, fact_id)

    @mcp.tool()
    async def knowledge_api_remember(
        kb_id: str,
        text: str,
        source_chunk: Optional[str] = None,
        source_doc: Optional[str] = None,
    ) -> dict[str, Any]:
        """Stage a fact candidate for human review (PENDING ONLY, never graph).

        Requires human approval before execution.

        Args:
            kb_id: Knowledge-base scope id.
            text: Fact candidate text.
            source_chunk: Source chunk id for provenance (optional).
            source_doc: Source document id for provenance (optional).

        Returns:
            The pending row.
        """
        service = resolve_knowledge_api_service()
        return service.remember(
            kb_id,
            text,
            source_chunk=source_chunk,
            source_doc=source_doc,
            permission="write",
        )

    @mcp.tool()
    async def knowledge_api_review_decide(
        pending_id: str,
        decision: str,
        reviewer: str = "mcp",
        mapping: Optional[dict[str, Any]] = None,
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve (promote to graph) or reject a pending fact.

        Requires human approval before execution.

        Args:
            pending_id: Pending row id.
            decision: approve or reject.
            reviewer: Reviewer identity.
            mapping: Approve mapping (subject_id, predicate, object...).
            reason: Decision reason.

        Returns:
            Dict with pending plus fact.
        """
        service = resolve_knowledge_api_service()
        return service.review_decide(
            pending_id,
            decision,
            reviewer=reviewer,
            mapping=mapping,
            reason=reason,
            permission="write",
        )

    @mcp.tool()
    async def knowledge_api_ontology_lookup(
        kb_id: str,
        surface: str,
    ) -> dict[str, Any]:
        """Resolve a surface predicate to its governed relation key.

        Args:
            kb_id: Knowledge-base scope id.
            surface: Surface predicate string.

        Returns:
            Dict with resolution and types.
        """
        service = resolve_knowledge_api_service()
        return service.ontology_lookup(kb_id, surface)
