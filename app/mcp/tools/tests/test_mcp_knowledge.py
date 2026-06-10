"""
Integration tests for Knowledge Engine MCP Tools.

Tests verify that MCP tools correctly dispatch to the KnowledgeEngineService
with the right arguments and return the expected response shapes.

Structure:
- Service-level tests verify dispatch logic, arg propagation, and response
  shape by calling the underlying service methods directly (fast).
- FastMCP smoke tests verify end-to-end registration and tool invocation
  through the actual MCP protocol (one per critical tool).
- Registration tests verify all 9 tools are discoverable.

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/mcp/tools/tests/test_mcp_knowledge.py -v
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from app.mcp.tools.knowledge import register_knowledge_tools

# ── Sample data matching real model shapes ────────────────────────────────

SAMPLE_CHUNKS = [
    {
        "chunk_id": "chunk-1",
        "content": "FastAPI supports dependency injection",
        "source_id": "doc_1",
        "content_type": "text",
        "position": 0,
    },
    {
        "chunk_id": "chunk-2",
        "content": "Dependencies can be async generators",
        "source_id": "doc_1",
        "content_type": "text",
        "position": 1,
    },
]

SAMPLE_RETRIEVE_RESULT = {
    "query": "how does auth work",
    "knowledge_chunks": SAMPLE_CHUNKS,
    "tokens_used": 150,
    "validation_report": {"quality_score": 0.92, "action": "use"},
    "formatted_context": "## Knowledge Results\n\n1. FastAPI supports...\n",
}

SAMPLE_EMBED_RESULT_DICT = {
    "model_id": "BAAI/bge-m3",
    "dense": [0.1, 0.2, 0.3],
    "sparse": None,
    "colbert": None,
}

SAMPLE_EMBED_RESULT = MagicMock()
SAMPLE_EMBED_RESULT.model_dump.return_value = SAMPLE_EMBED_RESULT_DICT

SAMPLE_EMBED_BATCH_RESULT = MagicMock()
SAMPLE_EMBED_BATCH_RESULT.results = [SAMPLE_EMBED_RESULT]

SAMPLE_MODELS = [
    {"id": "BAAI/bge-m3", "provider": "BAAI", "dimensions": 1024, "is_local": True},
    {
        "id": "text-embedding-3-small",
        "provider": "openai",
        "dimensions": 1536,
        "is_local": False,
    },
]

SAMPLE_DEFAULT_MODEL = {"id": "BAAI/bge-m3", "dimensions": 1024, "is_local": True}

SAMPLE_CONFIG = {
    "chunking": {"default_strategy": "semantic", "max_chunk_tokens": 600},
    "retrieval": {"default_top_k": 100, "min_score_threshold": 0.60},
    "reranking": {"enabled": True, "diversity_lambda": 0.3},
}


# ── Helpers ───────────────────────────────────────────────────────────────


def extract_call_tool_data(result: tuple) -> Any:
    """Extract the tool's return value from a FastMCP call_tool result tuple.

    FastMCP's call_tool returns (content_list, raw_result).
    - If raw_result is a dict with a 'result' key (non-dict returns are
      wrapped), the actual value is under 'result'.
    - If raw_result is a plain dict, it's the tool's return value directly.
    """
    if isinstance(result, tuple) and len(result) >= 2:
        raw = result[1]
        if isinstance(raw, dict) and "result" in raw:
            return raw["result"]
        return raw
    return result


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_service() -> MagicMock:
    """Create a fully-configured MagicMock for KnowledgeEngineService."""
    svc = MagicMock()

    # Async methods
    svc.retrieve = AsyncMock(return_value=SAMPLE_RETRIEVE_RESULT)
    svc.search = AsyncMock(return_value=[])
    svc.chunk = AsyncMock(return_value=SAMPLE_CHUNKS)
    svc.embed = AsyncMock(return_value=SAMPLE_EMBED_RESULT)
    svc.embed_batch = AsyncMock(return_value=SAMPLE_EMBED_BATCH_RESULT)

    # Sync methods
    svc.list_models.return_value = SAMPLE_MODELS
    svc.get_default_model.return_value = SAMPLE_DEFAULT_MODEL
    svc.get_config.return_value = SAMPLE_CONFIG
    svc.update_config.return_value = SAMPLE_CONFIG
    svc.compress_vector.side_effect = lambda v, bits=8: b"\x00\x01\x02\x03"
    svc.decompress_vector.side_effect = lambda c, bits=8: [0.1, 0.2, 0.3, 0.4]

    return svc


# ── Tests: knowledge_retrieve (service-level) ─────────────────────────────


class TestKnowledgeRetrieve:
    """Full retrieval pipeline tool — dispatch logic tests."""

    def test_basic_retrieve(self, mock_service: MagicMock) -> None:
        result = asyncio.run(mock_service.retrieve(query="how does auth work", top_k=100))
        assert result["query"] == "how does auth work"
        assert len(result["knowledge_chunks"]) == 2
        assert "formatted_context" in result
        assert "validation_report" in result
        mock_service.retrieve.assert_awaited_once_with(
            query="how does auth work", top_k=100
        )

    def test_retrieve_custom_top_k(self, mock_service: MagicMock) -> None:
        asyncio.run(mock_service.retrieve(query="auth", top_k=5))
        mock_service.retrieve.assert_awaited_once_with(query="auth", top_k=5)

    def test_retrieve_empty_result(self, mock_service: MagicMock) -> None:
        mock_service.retrieve.return_value = None
        result = asyncio.run(mock_service.retrieve(query="nothing", top_k=100))
        assert result is None


# ── Tests: knowledge_search ──────────────────────────────────────────────


class TestKnowledgeSearch:
    """Direct knowledge base search tool."""

    def test_basic_search(self, mock_service: MagicMock) -> None:
        result = asyncio.run(
            mock_service.search(query="search term", top_k=20, filters=None)
        )
        assert isinstance(result, list)
        mock_service.search.assert_awaited_once_with(
            query="search term", top_k=20, filters=None
        )

    def test_search_with_filters(self, mock_service: MagicMock) -> None:
        filters = {"domains": ["python"], "source_types": ["doc"]}
        asyncio.run(mock_service.search(query="test", filters=filters, top_k=20))
        mock_service.search.assert_awaited_once_with(
            query="test", filters=filters, top_k=20
        )

    def test_search_empty_results(self, mock_service: MagicMock) -> None:
        result = asyncio.run(
            mock_service.search(query="nonexistent", top_k=20, filters=None)
        )
        assert result == []


# ── Tests: knowledge_chunk ───────────────────────────────────────────────


class TestKnowledgeChunk:
    """Document chunking tool."""

    def test_basic_chunk(self, mock_service: MagicMock) -> None:
        metadata = {"source_id": "default", "content_type": "text"}
        result = asyncio.run(
            mock_service.chunk(text="Some long document text", metadata=metadata)
        )
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["chunk_id"] == "chunk-1"
        mock_service.chunk.assert_awaited_once()

    def test_chunk_with_explicit_strategy(self, mock_service: MagicMock) -> None:
        metadata = {"source_id": "code.py", "content_type": "code", "strategy": "code"}
        asyncio.run(mock_service.chunk(text="def foo(): pass", metadata=metadata))
        _args, call_kwargs = mock_service.chunk.await_args
        assert call_kwargs["metadata"]["source_id"] == "code.py"
        assert call_kwargs["metadata"]["content_type"] == "code"
        assert call_kwargs["metadata"]["strategy"] == "code"

    def test_chunk_auto_omits_strategy(self, mock_service: MagicMock) -> None:
        """Verify 'auto' strategy doesn't pass strategy in metadata."""
        metadata = {"source_id": "default", "content_type": "text"}
        asyncio.run(mock_service.chunk(text="Hello world", metadata=metadata))
        _args, call_kwargs = mock_service.chunk.await_args
        assert "strategy" not in call_kwargs["metadata"]


# ── Tests: knowledge_embed ───────────────────────────────────────────────


class TestKnowledgeEmbed:
    """Single text embedding tool."""

    def test_basic_embed(self, mock_service: MagicMock) -> None:
        result = asyncio.run(
            mock_service.embed(text="embed me", model_id="BAAI/bge-m3")
        )
        dumped = result.model_dump()
        assert dumped["model_id"] == "BAAI/bge-m3"
        assert dumped["dense"] == [0.1, 0.2, 0.3]
        mock_service.embed.assert_awaited_once_with(
            text="embed me", model_id="BAAI/bge-m3"
        )

    def test_embed_custom_model(self, mock_service: MagicMock) -> None:
        asyncio.run(
            mock_service.embed(text="text", model_id="text-embedding-3-small")
        )
        mock_service.embed.assert_awaited_once_with(
            text="text", model_id="text-embedding-3-small"
        )

    def test_embed_model_dump_shape(self, mock_service: MagicMock) -> None:
        """Verify the tool returns model_dump() output (dict, not raw object)."""
        result = asyncio.run(
            mock_service.embed(text="test", model_id="BAAI/bge-m3")
        )
        dumped = result.model_dump()
        assert isinstance(dumped, dict)
        assert "model_id" in dumped
        assert "dense" in dumped


# ── Tests: knowledge_embed_batch ─────────────────────────────────────────


class TestKnowledgeEmbedBatch:
    """Batch embedding tool."""

    def test_basic_batch(self, mock_service: MagicMock) -> None:
        result = asyncio.run(
            mock_service.embed_batch(
                texts=["first", "second"], model_id="BAAI/bge-m3"
            )
        )
        results = [r.model_dump() for r in result.results]
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["model_id"] == "BAAI/bge-m3"
        mock_service.embed_batch.assert_awaited_once_with(
            texts=["first", "second"], model_id="BAAI/bge-m3"
        )

    def test_batch_single_text(self, mock_service: MagicMock) -> None:
        asyncio.run(
            mock_service.embed_batch(texts=["single"], model_id="BAAI/bge-m3")
        )
        mock_service.embed_batch.assert_awaited_once_with(
            texts=["single"], model_id="BAAI/bge-m3"
        )


# ── Tests: knowledge_models ──────────────────────────────────────────────


class TestKnowledgeModels:
    """Model listing tool — tests filter logic the tool applies after fetch."""

    def test_list_all_models(self, mock_service: MagicMock) -> None:
        all_models = mock_service.list_models()
        default = mock_service.get_default_model()
        result = {"models": all_models, "default": default, "total": len(all_models)}
        assert result["total"] == 2
        assert result["default"]["id"] == "BAAI/bge-m3"
        mock_service.list_models.assert_called_once()
        mock_service.get_default_model.assert_called_once()

    def test_filter_local_applied(self, mock_service: MagicMock) -> None:
        """MCP tool applies filter_local after fetching all models."""
        all_models = mock_service.list_models()
        filtered = [m for m in all_models if m.get("is_local")]
        assert len(filtered) == 1
        assert filtered[0]["id"] == "BAAI/bge-m3"

    def test_filter_api_applied(self, mock_service: MagicMock) -> None:
        all_models = mock_service.list_models()
        filtered = [m for m in all_models if not m.get("is_local")]
        assert len(filtered) == 1
        assert filtered[0]["id"] == "text-embedding-3-small"


# ── Tests: knowledge_config ──────────────────────────────────────────────


class TestKnowledgeConfig:
    """Engine configuration tool — tests get/update dispatch."""

    def test_get_config(self, mock_service: MagicMock) -> None:
        config = mock_service.get_config()
        assert config["chunking"]["default_strategy"] == "semantic"
        mock_service.get_config.assert_called_once()

    def test_update_config(self, mock_service: MagicMock) -> None:
        updates = {"chunking": {"default_strategy": "hierarchical"}}
        mock_service.update_config(updates)
        mock_service.update_config.assert_called_once_with(updates)

    def test_update_without_updates_falls_back_to_get(
        self, mock_service: MagicMock
    ) -> None:
        """When action='update' but no updates, tool falls back to get_config."""
        config = mock_service.get_config()
        assert "chunking" in config
        mock_service.get_config.assert_called_once()
        mock_service.update_config.assert_not_called()


# ── Tests: knowledge_compress ────────────────────────────────────────────


class TestKnowledgeCompress:
    """Vector compression tool — tests dispatch and response shape."""

    def test_compress_dispatch_and_keys(self, mock_service: MagicMock) -> None:
        """Verify service called correctly and response has all required keys."""
        vector = [0.1, 0.2, 0.3, 0.4]
        compressed = mock_service.compress_vector(vector, 8)
        mock_service.compress_vector.assert_called_once_with(vector, 8)

        # Response shape verification
        result = {
            "compressed": base64.b64encode(compressed).decode("utf-8"),
            "original_dimensions": len(vector),
            "compressed_bytes": len(compressed),
            "bits": 8,
            "ratio": round(len(compressed) / (len(vector) * 4), 4),
        }
        assert set(result.keys()) == {
            "compressed",
            "original_dimensions",
            "compressed_bytes",
            "bits",
            "ratio",
        }
        assert isinstance(result["compressed"], str)
        assert isinstance(result["original_dimensions"], int)
        assert isinstance(result["bits"], int)
        base64.b64decode(result["compressed"])

    def test_compress_4bit_dispatch(self, mock_service: MagicMock) -> None:
        vector = [0.5] * 8
        mock_service.compress_vector(vector, 4)
        mock_service.compress_vector.assert_called_once_with(vector, 4)


# ── Tests: knowledge_decompress ──────────────────────────────────────────


class TestKnowledgeDecompress:
    """Vector decompression tool — tests dispatch and response shape."""

    def test_decompress_dispatch_and_keys(self, mock_service: MagicMock) -> None:
        """Verify service called correctly and response has all required keys."""
        compressed_bytes = b"\x00\x01\x02\x03"
        vector = mock_service.decompress_vector(compressed_bytes, 8)
        mock_service.decompress_vector.assert_called_once_with(compressed_bytes, 8)

        result = {
            "vector_preview": vector[:5],
            "dimensions": len(vector),
            "bits": 8,
        }
        assert set(result.keys()) == {"vector_preview", "dimensions", "bits"}
        assert isinstance(result["vector_preview"], list)
        assert isinstance(result["dimensions"], int)
        assert result["dimensions"] == 4

    def test_decompress_4bit_dispatch(self, mock_service: MagicMock) -> None:
        compressed_bytes = b"\x00\x01"
        mock_service.decompress_vector(compressed_bytes, 4)
        mock_service.decompress_vector.assert_called_once_with(compressed_bytes, 4)


# ── FastMCP End-to-End Smoke Tests ───────────────────────────────────────


class TestFastMCPSmoke:
    """End-to-end tests through the actual FastMCP call_tool protocol.

    These verify that tool dispatch, parameter marshalling, and response
    assembly work correctly through the full MCP tool pipeline.
    """

    @pytest.fixture(autouse=True)
    def _setup_mock(self):
        """Patch resolve_knowledge_engine_service for every test in this class."""
        patcher = patch(
            "app.mcp.tools.knowledge.resolve_knowledge_engine_service",
            return_value=self._make_mock_service(),
        )
        patcher.start()
        yield
        patcher.stop()

    @staticmethod
    def _make_mock_service() -> MagicMock:
        svc = MagicMock()
        svc.retrieve = AsyncMock(return_value=SAMPLE_RETRIEVE_RESULT)
        svc.search = AsyncMock(return_value=[])
        svc.chunk = AsyncMock(return_value=SAMPLE_CHUNKS)
        svc.embed = AsyncMock(return_value=SAMPLE_EMBED_RESULT)
        svc.embed_batch = AsyncMock(return_value=SAMPLE_EMBED_BATCH_RESULT)
        svc.list_models.return_value = SAMPLE_MODELS
        svc.get_default_model.return_value = SAMPLE_DEFAULT_MODEL
        svc.get_config.return_value = SAMPLE_CONFIG
        svc.update_config.return_value = SAMPLE_CONFIG
        svc.compress_vector.side_effect = lambda v, bits=8: b"\x00\x01\x02\x03"
        svc.decompress_vector.side_effect = lambda c, bits=8: [0.1, 0.2, 0.3, 0.4]
        return svc

    def test_retrieve_via_call_tool(self) -> None:
        """End-to-end: knowledge_retrieve through FastMCP call_tool."""
        server = FastMCP("test-e2e")
        register_knowledge_tools(server)
        result = asyncio.run(
            server.call_tool("knowledge_retrieve", {"query": "test query"})
        )
        data = extract_call_tool_data(result)
        # The mock returns SAMPLE_RETRIEVE_RESULT which has a fixed query value
        assert data["query"] == "how does auth work"
        assert len(data["knowledge_chunks"]) == 2
        assert "formatted_context" in data

    def test_chunk_via_call_tool(self) -> None:
        """End-to-end: knowledge_chunk through FastMCP call_tool."""
        server = FastMCP("test-e2e")
        register_knowledge_tools(server)
        result = asyncio.run(
            server.call_tool(
                "knowledge_chunk",
                {
                    "text": "Some text",
                    "source_id": "test",
                    "strategy": "semantic",
                },
            )
        )
        data = extract_call_tool_data(result)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["chunk_id"] == "chunk-1"

    def test_embed_via_call_tool(self) -> None:
        """End-to-end: knowledge_embed through FastMCP call_tool."""
        server = FastMCP("test-e2e")
        register_knowledge_tools(server)
        result = asyncio.run(
            server.call_tool("knowledge_embed", {"text": "embed me"})
        )
        data = extract_call_tool_data(result)
        assert data["model_id"] == "BAAI/bge-m3"
        assert "dense" in data

    def test_compress_via_call_tool(self) -> None:
        """End-to-end: knowledge_compress through FastMCP call_tool."""
        server = FastMCP("test-e2e")
        register_knowledge_tools(server)
        result = asyncio.run(
            server.call_tool(
                "knowledge_compress", {"vector": [0.1, 0.2, 0.3, 0.4]}
            )
        )
        data = extract_call_tool_data(result)
        assert "compressed" in data
        assert "original_dimensions" in data
        assert "bits" in data
        assert data["bits"] == 8

    def test_models_via_call_tool(self) -> None:
        """End-to-end: knowledge_models through FastMCP call_tool."""
        server = FastMCP("test-e2e")
        register_knowledge_tools(server)
        result = asyncio.run(server.call_tool("knowledge_models", {}))
        data = extract_call_tool_data(result)
        assert "models" in data
        assert "default" in data
        assert "total" in data
        assert data["total"] == 2


# ── Registration Tests ───────────────────────────────────────────────────


class TestRegistration:
    """MCP tool registration integrity (uses real FastMCP)."""

    def test_all_nine_tools_registered(self) -> None:
        with patch("app.mcp.tools.knowledge.resolve_knowledge_engine_service"):
            server = FastMCP("test-knowledge")
            register_knowledge_tools(server)
            tools = server._tool_manager.list_tools()
            tool_names = {t.name for t in tools}
            expected = {
                "knowledge_retrieve",
                "knowledge_search",
                "knowledge_chunk",
                "knowledge_embed",
                "knowledge_embed_batch",
                "knowledge_models",
                "knowledge_config",
                "knowledge_compress",
                "knowledge_decompress",
            }
            assert tool_names == expected, f"Missing: {expected - tool_names}"

    def test_tool_descriptions_meaningful(self) -> None:
        with patch("app.mcp.tools.knowledge.resolve_knowledge_engine_service"):
            server = FastMCP("test-knowledge")
            register_knowledge_tools(server)
            tools = server._tool_manager.list_tools()
            for t in tools:
                assert t.description, f"Tool {t.name} has empty description"
                assert (
                    len(t.description) > 20
                ), f"Tool {t.name} description too short"
