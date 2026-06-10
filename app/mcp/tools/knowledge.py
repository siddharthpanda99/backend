"""
Knowledge Engine — MCP Tool Registration.

Registers Knowledge Engine capabilities as MCP tools for agent consumption.
Provides retrieval, chunking, embedding, search, and configuration tools
that agents can call via MCP protocol.

Usage:
    # In app/mcp/server.py:
    from app.mcp.tools.knowledge import register_knowledge_tools
    register_knowledge_tools(mcp_server)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ..mcp_dependencies import resolve_knowledge_engine_service

logger = logging.getLogger("mcp.tools.knowledge")


def register_knowledge_tools(mcp: FastMCP) -> None:
    """Register all Knowledge Engine tools with the MCP server.

    Registers 7 tools covering retrieval, chunking, embedding, search,
    model listing, configuration, and vector compression.
    """

    # ── Retrieval ─────────────────────────────────────────────

    @mcp.tool()
    async def knowledge_retrieve(
        query: str,
        top_k: int = 100,
    ) -> dict[str, Any]:
        """Execute the full retrieval pipeline: query understanding → hybrid search → rerank → context fusion.

        Returns a structured ContextPackage with ranked knowledge chunks,
        validation results, token accounting, and formatted markdown
        ready for LLM consumption.

        Args:
            query: Natural language query to search against.
            top_k: Number of initial candidates to retrieve (1-500).

        Returns:
            ContextPackage dict with knowledge_chunks, validation_report,
            formatted_context, and token accounting.
        """
        service = await resolve_knowledge_engine_service()
        result = await service.retrieve(query=query, top_k=top_k)
        if result is None:
            return {"status": "empty", "message": "No results returned (pipeline uninitialized)"}
        return result

    @mcp.tool()
    async def knowledge_search(
        query: str,
        top_k: int = 20,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Search the knowledge base directly without the full retrieval pipeline.

        Fast, lightweight search suitable for quick lookups. Supports
        optional metadata filters for domain, source type, date range, etc.

        Args:
            query: Search query string.
            top_k: Maximum number of results (1-100).
            filters: Optional metadata filters (domains, source_types, etc.).

        Returns:
            List of matching RetrievedChunks with scores.
        """
        service = await resolve_knowledge_engine_service()
        return await service.search(query=query, filters=filters, top_k=top_k)

    # ── Chunking ──────────────────────────────────────────────

    @mcp.tool()
    async def knowledge_chunk(
        text: str,
        source_id: str = "default",
        content_type: str = "text",
        strategy: str = "auto",
    ) -> list[dict[str, Any]]:
        """Split a document into knowledge chunks using the optimal strategy.

        Automatically detects the best chunking strategy based on content
        type and structure, or you can specify one explicitly.

        Args:
            text: Document text to chunk.
            source_id: Source identifier for provenance tracking.
            content_type: Content type hint (text, code, markdown, qa, faq).
            strategy: Chunking strategy (auto, semantic, hierarchical,
                     proposition, code, late, single).

        Returns:
            List of KnowledgeChunk objects with content, position,
            hierarchy, and metadata.
        """
        service = await resolve_knowledge_engine_service()
        metadata = {"source_id": source_id, "content_type": content_type}
        if strategy != "auto":
            metadata["strategy"] = strategy
        return await service.chunk(text=text, metadata=metadata)

    # ── Embedding ─────────────────────────────────────────────

    @mcp.tool()
    async def knowledge_embed(
        text: str,
        model_id: str = "BAAI/bge-m3",
    ) -> dict[str, Any]:
        """Generate a vector embedding for text.

        Default model is BAAI/bge-m3 (1024-dimensional). For BGE-M3,
        also returns sparse and ColBERT vectors in addition to dense.

        Args:
            text: Text to embed (minimum 1 character).
            model_id: Embedding model ID (default: BAAI/bge-m3).

        Returns:
            EmbeddingResult with dense vector and optionally sparse + ColBERT.
        """
        service = await resolve_knowledge_engine_service()
        result = await service.embed(text=text, model_id=model_id)
        return result.model_dump()

    @mcp.tool()
    async def knowledge_embed_batch(
        texts: list[str],
        model_id: str = "BAAI/bge-m3",
    ) -> list[dict[str, Any]]:
        """Generate embeddings for multiple texts in batch.

        More efficient than calling knowledge_embed repeatedly.
        Maximum 100 texts per batch.

        Args:
            texts: List of texts to embed (1-100).
            model_id: Embedding model ID (default: BAAI/bge-m3).

        Returns:
            List of EmbeddingResult objects.
        """
        service = await resolve_knowledge_engine_service()
        result = await service.embed_batch(texts=texts, model_id=model_id)
        return [r.model_dump() for r in result.results]

    # ── Model Registry ────────────────────────────────────────

    @mcp.tool()
    async def knowledge_models(
        filter_local: bool = False,
        filter_api: bool = False,
    ) -> dict[str, Any]:
        """List available embedding models with metadata.

        Shows all 7 registered models with their dimensions, capabilities,
        cost, latency, and availability status.

        Args:
            filter_local: If True, show only locally-hosted models.
            filter_api: If True, show only API-based models.

        Returns:
            Dict with models list, default model, and total count.
        """
        service = await resolve_knowledge_engine_service()
        all_models = service.list_models()
        default = service.get_default_model()

        if filter_local:
            all_models = [m for m in all_models if m.get("is_local")]
        if filter_api:
            all_models = [m for m in all_models if not m.get("is_local")]

        return {"models": all_models, "default": default, "total": len(all_models)}

    # ── Configuration ─────────────────────────────────────────

    @mcp.tool()
    async def knowledge_config(
        action: str = "get",
        updates: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Get or update Knowledge Engine configuration.

        Returns the full configuration when action='get'.
        Applies partial updates when action='update' (only specified
        fields are modified).

        Args:
            action: 'get' to retrieve config, 'update' to modify.
            updates: Config fields to update (required when action='update').

        Returns:
            Full Knowledge Engine configuration dict.
        """
        service = await resolve_knowledge_engine_service()
        if action == "update" and updates:
            return service.update_config(updates)
        return service.get_config()

    # ── Vector Compression ────────────────────────────────────

    @mcp.tool()
    async def knowledge_compress(
        vector: list[float],
        bits: int = 8,
    ) -> dict[str, Any]:
        """Compress an embedding vector using TurboQuant quantization.

        8-bit: ~4x size reduction (near-lossless reconstruction).
        4-bit: ~8x size reduction.

        Args:
            vector: Float32 embedding vector to compress.
            bits: Quantization bits (4 or 8).

        Returns:
            Dict with base64-encoded compressed bytes, dimensions, and ratio.
        """
        import base64

        service = await resolve_knowledge_engine_service()
        compressed = service.compress_vector(vector, bits)
        return {
            "compressed": base64.b64encode(compressed).decode("utf-8"),
            "original_dimensions": len(vector),
            "compressed_bytes": len(compressed),
            "bits": bits,
            "ratio": round(len(compressed) / (len(vector) * 4), 4),
        }

    @mcp.tool()
    async def knowledge_decompress(
        compressed: str,
        bits: int = 8,
    ) -> dict[str, Any]:
        """Decompress a TurboQuant-compressed embedding vector.

        Reconstructs an approximate float32 vector from base64-encoded
        compressed data.

        Args:
            compressed: Base64-encoded compressed bytes.
            bits: Quantization bits used during compression (4 or 8).

        Returns:
            Dict with decompressed vector preview and dimensions.
        """
        import base64

        service = await resolve_knowledge_engine_service()
        compressed_bytes = base64.b64decode(compressed)
        vector = service.decompress_vector(compressed_bytes, bits)
        return {
            "vector_preview": vector[:5],
            "dimensions": len(vector),
            "bits": bits,
        }

    # ── PII Redaction ──────────────────────────────────────────

    @mcp.tool()
    async def knowledge_redact_pii(
        text: str,
        strategy: str = "redact",
    ) -> dict[str, Any]:
        """Detect and redact Personally Identifiable Information (PII) from text.

        Scans text for emails, phone numbers, SSNs, credit cards,
        addresses, and other PII using Microsoft Presidio. Returns
        sanitized text with detected entities.

        Args:
            text: Text content to scan and redact.
            strategy: Redaction strategy:
                - "redact": Replace matches with [REDACTED]
                - "mask": Partially mask sensitive portions
                - "hash": Replace with SHA-256 hash (irreversible)
                - "replace": Replace with realistic fake values

        Returns:
            Dict with redacted_text, entity_count, entities list,
            and strategy used.
        """
        from common_lib.modules.knowledge_engine.security import (
            KnowledgePIIRedactor,
        )

        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: KnowledgePIIRedactor(use_presidio=True).redact(text=text, strategy=strategy)
        )

    @mcp.tool()
    async def knowledge_detect_pii(
        text: str,
    ) -> dict[str, Any]:
        """Detect PII entities in text without modifying it.

        Scans for personally identifiable information and returns
        detected entities with types, confidence scores, and positions.
        Useful for previewing what would be redacted.

        Args:
            text: Text content to scan for PII.

        Returns:
            Dict with has_pii, entity_count, and entities list.
        """
        from common_lib.modules.knowledge_engine.security import (
            KnowledgePIIRedactor,
        )

        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: KnowledgePIIRedactor(use_presidio=True).detect(text=text)
        )

    logger.info("Knowledge Engine: 11 MCP tools registered (9 + 2 PII)")
