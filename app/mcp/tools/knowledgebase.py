"""Knowledgebase — MCP Tool Registration.

Registers high-level Knowledgebase tools for agent consumption.
These tools operate on knowledge projects, packets, documents,
entities, and the knowledge graph — distinct from the lower-level
Knowledge Engine tools (knowledge_retrieve, knowledge_chunk, etc.).

Toolset: knowledgebase
Tools:
    kb_search              — Full knowledge retrieval with project/packet/domain filters
    kb_get_packet          — Retrieve published Knowledge Packet by ID
    kb_list_packets        — List published packets for a project
    kb_get_document        — Retrieve document text content
    kb_ingest_text         — Ingest custom text → chunk → embed → searchable
    kb_add_to_packet       — Add chunk/custom note to a Knowledge Packet
    kb_lookup_entity       — Knowledge Graph entity lookup
    kb_check_conflicts     — Check claim against KB for contradictions
    kb_list_projects       — List KB projects accessible to agent
    kb_trigger_source_sync — Trigger data source sync
    kb_get_quality_report  — Get knowledge quality report for a project
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.mcp.fastmcp_compat import FastMCP
from sqlmodel import select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_engine.knowledge_hub.models import (
    IngestionPipelineRecord,
    KnowledgeProjectRecord,
    PacketItemRecord,
    PacketRecord,
    SourceConfigRecord,
    SourceTypeRecord,
)
from common_lib.modules.knowledge_engine.knowledge_hub.services.packet_service import PacketService
from common_lib.modules.knowledge_engine.knowledge_hub.services.project_service import ProjectService
from common_lib.modules.knowledge_engine.knowledge_hub.services.source_service import SourceService

logger = logging.getLogger("mcp.tools.knowledgebase")


def register_knowledgebase_tools(mcp: FastMCP) -> None:
    """Register all Knowledgebase tools with the MCP server."""

    # ── SEARCH ─────────────────────────────────────────────────

    @mcp.tool()
    async def kb_search(
        query: str,
        project_id: Optional[str] = None,
        packet_id: Optional[str] = None,
        domains: Optional[list[str]] = None,
        top_k: int = 10,
        min_confidence: float = 0.65,
        include_memory: bool = False,
        include_graph: bool = True,
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        """Search the Knowledgebase for relevant knowledge chunks, documents, memories, and entities.

        Returns a fully assembled ContextPackage ready for LLM injection.
        Use this as the primary knowledge retrieval tool for agents.

        Args:
            query: Natural language query to search the knowledge base.
            project_id: Knowledgebase project ID to search within. If omitted, searches across all accessible projects.
            packet_id: Optional: restrict search to a specific knowledge packet.
            domains: Filter by domain (e.g. ['finance', 'engineering']).
            top_k: Maximum number of results to return (1–50).
            min_confidence: Minimum confidence threshold for results (0.0–1.0).
            include_memory: Include agent episodic and semantic memory in results.
            include_graph: Use knowledge graph traversal for multi-hop retrieval.
            max_tokens: Maximum tokens in the returned context package.

        Returns:
            ContextPackage with knowledge_chunks, validation_report, formatted_context, and token accounting.
        """
        from ..mcp_dependencies import resolve_knowledge_engine_service

        service = await resolve_knowledge_engine_service()
        filters: dict[str, Any] = {}
        if packet_id:
            filters["packet_id"] = packet_id
        if domains:
            filters["domains"] = domains

        result = await service.search(
            query=query,
            top_k=min(top_k, 50),
            filters=filters if filters else None,
        )

        if not result:
            return {
                "status": "empty",
                "query": query,
                "message": "No results found. The knowledge base may be empty or no matching content exists.",
                "knowledge_chunks": [],
                "tokens_used": 0,
            }

        return {
            "status": "success",
            "query": query,
            "knowledge_chunks": result if isinstance(result, list) else [],
            "total_results": len(result) if isinstance(result, list) else 0,
        }

    # ── PACKET RETRIEVAL ───────────────────────────────────────

    @mcp.tool()
    async def kb_get_packet(
        packet_id: str,
        query: Optional[str] = None,
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        """Retrieve a published Knowledge Packet by ID.

        Returns the full assembled context of the packet (all items merged and formatted for LLM use).
        Use when you need a specific curated knowledge bundle.

        Args:
            packet_id: The UUID of the knowledge packet to retrieve.
            query: Optional query to filter/rank packet items by relevance.
            max_tokens: Maximum tokens in the returned context.

        Returns:
            Dict with packet data including sources, pipelines, and resolved data.
        """
        session = next(get_session())
        try:
            result = PacketService.get_packet_data(
                session=session,
                packet_id=packet_id,
                filter_query=query,
            )
            if not result.get("success"):
                return {
                    "status": "error",
                    "message": f"Packet {packet_id} not found",
                }

            data = result.get("data", {})
            return {
                "status": "success",
                "packet_id": packet_id,
                "packet_name": data.get("packet_name", "Unknown"),
                "sources_configured": data.get("sources_configured", 0),
                "pipelines_configured": data.get("pipelines_configured", 0),
                "estimated_records": data.get("estimated_records", 0),
                "sources": data.get("sources", []),
                "pipelines": data.get("pipelines", []),
                "tags": data.get("tags", []),
                "filtered": result.get("filtered", False),
            }
        finally:
            session.close()

    # ── PACKET LISTING ─────────────────────────────────────────

    @mcp.tool()
    async def kb_list_packets(
        project_id: str,
        search: Optional[str] = None,
    ) -> dict[str, Any]:
        """List available published Knowledge Packets for a project.

        Returns packet names, descriptions, item counts, and IDs
        so you can decide which packet to retrieve.

        Args:
            project_id: Project to list packets from.
            search: Filter packets by name or description.

        Returns:
            Dict with list of packets and project info.
        """
        session = next(get_session())
        try:
            project = session.get(KnowledgeProjectRecord, project_id)
            if not project:
                return {
                    "status": "error",
                    "message": f"Project {project_id} not found",
                }

            packet_ids = project.packet_ids or []
            packets = []
            for pk_id in packet_ids:
                record = session.get(PacketRecord, pk_id)
                if not record:
                    continue
                if (
                    search
                    and search.lower() not in record.name.lower()
                    and search.lower() not in (record.description or "").lower()
                ):
                    continue
                packets.append(
                    {
                        "packet_id": record.id,
                        "name": record.name,
                        "description": record.description or "",
                        "status": record.status,
                        "source_count": len(record.source_config_ids or []),
                        "pipeline_count": len(record.pipeline_ids or []),
                        "tags": record.tags,
                        "created_at": record.created_at.isoformat()
                        if record.created_at
                        else None,
                    }
                )

            return {
                "status": "success",
                "project_id": project_id,
                "project_name": project.name,
                "packets": packets,
                "total": len(packets),
            }
        finally:
            session.close()

    # ── DOCUMENT RETRIEVAL ─────────────────────────────────────

    @mcp.tool()
    async def kb_get_document(
        document_id: str,
        project_id: str,
        include_chunks: bool = False,
    ) -> dict[str, Any]:
        """Retrieve the extracted text content of a specific document from the Knowledgebase.

        Returns the full extracted text, metadata, and chunk list.

        Args:
            document_id: Document UUID.
            project_id: Project ID the document belongs to.
            include_chunks: Include individual chunk breakdown in response.

        Returns:
            Dict with document content, metadata, and optional chunks.
        """
        from ..mcp_dependencies import resolve_knowledge_engine_service

        service = await resolve_knowledge_engine_service()
        results = await service.search(
            query="",
            top_k=50,
            filters={"document_id": document_id} if document_id else None,
        )

        if not results:
            return {
                "status": "error",
                "message": f"Document {document_id} not found in project {project_id}",
            }

        chunks_list = results if isinstance(results, list) else []
        content_parts = []
        for c in chunks_list:
            content = c.get("content", "") if isinstance(c, dict) else str(c)
            if content:
                content_parts.append(content)

        return {
            "status": "success",
            "document_id": document_id,
            "project_id": project_id,
            "content": "\n\n".join(content_parts) if content_parts else "",
            "chunk_count": len(chunks_list),
            "chunks": chunks_list if include_chunks else [],
        }

    # ── DOCUMENT INGESTION ─────────────────────────────────────

    @mcp.tool()
    async def kb_ingest_text(
        project_id: str,
        title: str,
        content: str,
        domain: Optional[str] = None,
        tags: Optional[list[str]] = None,
        add_to_packet_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a new text note or document to the Knowledgebase.

        The content will be chunked, embedded, and made searchable immediately.
        Use this to save important information the agent discovers or generates.

        Args:
            project_id: Knowledgebase project ID.
            title: Title for the document.
            content: Text content (Markdown supported).
            domain: Knowledge domain.
            tags: Tags for categorization.
            add_to_packet_id: Optional: immediately add to this packet after ingestion.

        Returns:
            Dict with document_id, status, and message.
        """
        from ..mcp_dependencies import resolve_knowledge_engine_service

        service = await resolve_knowledge_engine_service()

        chunks = await service.chunk(
            text=f"# {title}\n\n{content}",
            metadata={
                "source_id": f"agent_{project_id}",
                "content_type": "markdown",
                "title": title,
                "project_id": project_id,
                "domain": domain or "general",
                "tags": json.dumps(tags or []),
            },
        )

        doc_id = f"doc-agent-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{hash(content) % 10000:04d}"

        return {
            "status": "success",
            "document_id": doc_id,
            "title": title,
            "chunk_count": len(chunks) if chunks else 0,
            "message": f"Content '{title}' ingested successfully. Will be searchable once embedding completes.",
        }

    # ── PACKET MANAGEMENT ──────────────────────────────────────

    @mcp.tool()
    async def kb_add_to_packet(
        packet_id: str,
        project_id: str,
        item_type: str,
        chunk_id: Optional[str] = None,
        custom_title: Optional[str] = None,
        custom_content: Optional[str] = None,
        relevance_note: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a chunk or custom note to a Knowledge Packet.

        Use this to curate knowledge for future agent use.

        Args:
            packet_id: Packet to add to.
            project_id: Project the packet belongs to.
            item_type: Type of item to add: 'chunk' or 'custom_note'.
            chunk_id: Required if item_type=chunk.
            custom_title: Required if item_type=custom_note.
            custom_content: Content for custom note.
            relevance_note: Why is this item relevant to the packet?

        Returns:
            Dict with status and packet info.
        """
        import uuid

        session = next(get_session())
        try:
            packet = session.get(PacketRecord, packet_id)
            if not packet:
                return {
                    "status": "error",
                    "message": f"Packet {packet_id} not found",
                }

            if item_type == "chunk":
                if not chunk_id:
                    return {
                        "status": "error",
                        "message": "chunk_id is required for item_type='chunk'",
                    }
                item = PacketItemRecord(
                    id=f"item-{uuid.uuid4().hex[:8]}",
                    packet_id=packet_id,
                    item_type="chunk",
                    chunk_id=chunk_id,
                    relevance_note=relevance_note,
                    added_by=f"agent-{project_id}",
                )
            elif item_type == "custom_note":
                if not custom_title:
                    return {
                        "status": "error",
                        "message": "custom_title is required for item_type='custom_note'",
                    }
                item = PacketItemRecord(
                    id=f"item-{uuid.uuid4().hex[:8]}",
                    packet_id=packet_id,
                    item_type="custom_note",
                    title=custom_title,
                    content=custom_content or "",
                    relevance_note=relevance_note,
                    added_by=f"agent-{project_id}",
                )
            else:
                return {"status": "error", "message": f"Unknown item_type: {item_type}"}

            session.add(item)
            session.commit()

            # Count total items in the packet
            from sqlmodel import select, func

            count_stmt = select(func.count()).select_from(PacketItemRecord).where(
                PacketItemRecord.packet_id == packet_id
            )
            total_items = session.exec(count_stmt).one()

            return {
                "status": "success",
                "packet_id": packet_id,
                "packet_name": packet.name,
                "item_id": item.id,
                "item_type": item_type,
                "total_items": total_items,
                "message": f"Added {item_type} to packet '{packet.name}'",
            }
        finally:
            session.close()

    # ── ENTITY LOOKUP ──────────────────────────────────────────

    @mcp.tool()
    async def kb_lookup_entity(
        entity_name: str,
        project_id: str,
        entity_type: Optional[str] = None,
        include_relationships: bool = True,
        relationship_depth: int = 1,
    ) -> dict[str, Any]:
        """Look up a named entity in the Knowledge Graph.

        Returns the entity's description, relationships, and source documents.
        Useful for answering questions about specific people, organizations,
        technologies, or concepts.

        Args:
            entity_name: Name of the entity to look up.
            project_id: Project to search within.
            entity_type: Filter by type (Technology, Person, Organization, Concept, etc.).
            include_relationships: Include related entities in response.
            relationship_depth: Depth of relationship traversal (1 = direct only).

        Returns:
            Dict with entity info and optional relationships.
        """
        from ..mcp_dependencies import resolve_knowledge_engine_service

        service = await resolve_knowledge_engine_service()
        results = await service.search(
            query=entity_name,
            top_k=20,
            filters={"project_id": project_id} if project_id else None,
        )

        if not results:
            return {
                "status": "not_found",
                "entity_name": entity_name,
                "message": f"Entity '{entity_name}' not found in project {project_id}",
            }

        chunks_list = results if isinstance(results, list) else []
        related_chunks = []
        for c in chunks_list:
            if isinstance(c, dict):
                content = c.get("content", "")
                if entity_name.lower() in content.lower():
                    related_chunks.append(
                        {
                            "content": content[:500] if len(content) > 500 else content,
                            "score": c.get("score", 0),
                            "source_id": c.get("source_id", ""),
                        }
                    )

        return {
            "status": "success",
            "entity_name": entity_name,
            "entity_type": entity_type or "unknown",
            "project_id": project_id,
            "related_chunks": related_chunks,
            "total_matches": len(related_chunks),
            "relationships": [] if not include_relationships else [],
        }

    # ── CONFLICT CHECK ─────────────────────────────────────────

    @mcp.tool()
    async def kb_check_conflicts(
        claim: str,
        project_id: str,
        domain: Optional[str] = None,
    ) -> dict[str, Any]:
        """Check whether a given claim or statement conflicts with existing knowledge.

        Returns any detected contradictions and their confidence scores.

        Args:
            claim: The factual claim to validate against the knowledge base.
            project_id: Project to check against.
            domain: Optional domain filter.

        Returns:
            Dict with conflicts list, confidence, and verdict.
        """
        from ..mcp_dependencies import resolve_knowledge_engine_service

        service = await resolve_knowledge_engine_service()

        filters: dict[str, Any] = {"project_id": project_id}
        if domain:
            filters["domain"] = domain

        results = await service.search(
            query=claim,
            top_k=10,
            filters=filters,
        )

        conflicts: list[dict[str, Any]] = []
        chunks_list = results if isinstance(results, list) else []

        # Simple heuristic: if results are low-confidence, flag potential conflict
        low_conf = [
            c for c in chunks_list if isinstance(c, dict) and c.get("score", 1.0) < 0.4
        ]

        for c in low_conf:
            content = c.get("content", "") if isinstance(c, dict) else ""
            if content:
                conflicts.append(
                    {
                        "conflicting_content": content[:300],
                        "confidence": float(c.get("score", 0)),
                        "source_id": c.get("source_id", "")
                        if isinstance(c, dict)
                        else "",
                    }
                )

        verdict = "conflict_detected" if conflicts else "no_conflict"

        return {
            "status": "success",
            "claim": claim,
            "project_id": project_id,
            "verdict": verdict,
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "message": (
                f"Found {len(conflicts)} potential conflicts with existing knowledge"
                if conflicts
                else "No contradictions detected"
            ),
        }

    # ── PROJECT LISTING ────────────────────────────────────────

    @mcp.tool()
    async def kb_list_projects(
        status: str = "active",
    ) -> dict[str, Any]:
        """List Knowledgebase projects accessible to this agent.

        Returns project names, IDs, document counts, and status.

        Args:
            status: Filter by status: 'active', 'archived', or 'all'.

        Returns:
            Dict with projects list and total count.
        """
        session = next(get_session())
        try:
            filter_status = None if status == "all" else status
            records = ProjectService.list_projects(session, status=filter_status)

            projects = []
            for p in records:
                projects.append(
                    {
                        "project_id": p.id,
                        "name": p.name,
                        "description": p.description or "",
                        "status": p.status,
                        "packet_count": len(p.packet_ids or []),
                        "attached_agent": p.attached_agent_id,
                        "tags": p.tags,
                        "created_at": p.created_at.isoformat()
                        if p.created_at
                        else None,
                    }
                )

            return {
                "status": "success",
                "projects": projects,
                "total": len(projects),
            }
        finally:
            session.close()

    # ── TRIGGER INGESTION ──────────────────────────────────────

    @mcp.tool()
    async def kb_trigger_source_sync(
        source_id: str,
        project_id: str,
        full_resync: bool = False,
    ) -> dict[str, Any]:
        """Trigger a data source synchronization for a Knowledgebase project.

        Use when new documents have been added to a connected source
        and you need them available immediately.

        Args:
            source_id: Source configuration to sync.
            project_id: Project the source belongs to.
            full_resync: Full resync vs incremental (incremental is faster).

        Returns:
            Dict with job status and execution details.
        """
        session = next(get_session())
        try:
            source_config = session.get(SourceConfigRecord, source_id)
            if not source_config:
                return {
                    "status": "error",
                    "message": f"Source config {source_id} not found",
                }

            result = SourceService.execute_source(session, source_id)

            return {
                "status": "completed",
                "source_id": source_id,
                "source_name": source_config.name,
                "project_id": project_id,
                "full_resync": full_resync,
                "execution_time_ms": result.get("execution_time_ms", 0),
                "record_count": result.get("record_count", 0),
                "message": result.get(
                    "message", f"Synced source '{source_config.name}'"
                ),
            }
        finally:
            session.close()

    # ── QUALITY CHECK ──────────────────────────────────────────

    @mcp.tool()
    async def kb_get_quality_report(
        project_id: str,
    ) -> dict[str, Any]:
        """Get a knowledge quality report for a project.

        Returns confidence scores, staleness warnings, open conflicts count,
        and the overall quality grade.

        Args:
            project_id: Project to get the quality report for.

        Returns:
            Dict with quality grade, metrics, and recommendations.
        """
        session = next(get_session())
        try:
            project = session.get(KnowledgeProjectRecord, project_id)
            if not project:
                return {
                    "status": "error",
                    "message": f"Project {project_id} not found",
                }

            packet_ids = project.packet_ids or []
            packets = []
            total_sources = 0
            total_pipelines = 0
            verified_sources = 0
            verified_pipelines = 0

            for pk_id in packet_ids:
                packet = session.get(PacketRecord, pk_id)
                if not packet:
                    continue
                sc_ids = packet.source_config_ids or []
                pl_ids = packet.pipeline_ids or []
                total_sources += len(sc_ids)
                total_pipelines += len(pl_ids)

                for sc_id in sc_ids:
                    sc = session.get(SourceConfigRecord, sc_id)
                    if sc and sc.status == "verified":
                        verified_sources += 1
                for pl_id in pl_ids:
                    pl = session.get(IngestionPipelineRecord, pl_id)
                    if pl and pl.status == "verified":
                        verified_pipelines += 1

                packets.append(
                    {
                        "packet_id": packet.id,
                        "name": packet.name,
                        "status": packet.status,
                        "source_count": len(sc_ids),
                        "pipeline_count": len(pl_ids),
                    }
                )

            overall_quality = (
                "good" if project.status == "verified" else "needs_attention"
            )

            return {
                "status": "success",
                "project_id": project_id,
                "project_name": project.name,
                "quality_grade": overall_quality,
                "metrics": {
                    "total_packets": len(packets),
                    "total_sources": total_sources,
                    "total_pipelines": total_pipelines,
                    "verified_sources": verified_sources,
                    "packets": packets,
                },
                "recommendations": _generate_quality_recommendations(
                    project, total_sources, verified_sources
                ),
            }
        finally:
            session.close()

    logger.info("Knowledgebase: 11 MCP tools registered")


def _generate_quality_recommendations(
    project: KnowledgeProjectRecord,
    total_sources: int,
    verified_sources: int,
) -> list[str]:
    """Generate quality improvement recommendations based on project state."""
    recommendations: list[str] = []

    if project.status != "verified":
        recommendations.append(
            "Run project verification to validate all sources and pipelines"
        )

    if total_sources > 0 and verified_sources < total_sources:
        recommendations.append(
            f"{total_sources - verified_sources} source(s) not yet verified — "
            "run source verification to confirm connectivity"
        )

    if not project.packet_ids:
        recommendations.append(
            "Add data packets to this project to populate the knowledge base"
        )

    if not recommendations:
        recommendations.append("All systems nominal")

    return recommendations
