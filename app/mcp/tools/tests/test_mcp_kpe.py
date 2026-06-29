"""
Unit tests for KPE Embedding MCP Tools (kpe_embed, kpe_embed_batch).

Tests verify that kpe_embed and kpe_embed_batch correctly dispatch to
DenseEmbedder with the right provider/model args and return expected
response shapes.

All tests use the FastMCP call_tool protocol since the tools are local
functions inside register_kpe_tools() and not module-level exports.

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/mcp/tools/tests/test_mcp_kpe.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from app.mcp.tools.kpe import register_kpe_tools


# ── Sample data ───────────────────────────────────────────────────────────

SAMPLE_VECTOR = [0.0123, 0.0456, 0.0789, 0.1011, 0.1213]
SAMPLE_VECTORS = [
    [0.0123, 0.0456, 0.0789],
    [0.0987, 0.0654, 0.0321],
    [0.1111, 0.2222, 0.3333],
]


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


def make_embedder(vectors: list | None = None, model: str = "text-embedding-3-small") -> MagicMock:
    """Create a mocked DenseEmbedder with configurable return values."""
    mock = MagicMock()
    mock.embed.return_value = vectors if vectors is not None else [SAMPLE_VECTOR]
    mock.model = model
    return mock


def _run_tool(tool_name: str, params: dict) -> Any:
    """Run an MCP tool in a fully isolated server with patched DenseEmbedder.

    Creates a fresh server, registers tools, patches DenseEmbedder, and
    calls the tool. Returns the extracted result data.
    """
    with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [SAMPLE_VECTOR]
        mock_instance.model = "text-embedding-3-small"
        mock_cls.return_value = mock_instance

        server = FastMCP("test-kpe")
        register_kpe_tools(server)
        result = asyncio.run(server.call_tool(tool_name, params))
        return extract_call_tool_data(result), mock_cls, mock_instance


def _run_tool_with_mock(tool_name: str, params: dict, mock_instance: MagicMock) -> Any:
    """Run an MCP tool with a pre-configured mock instance."""
    with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
        mock_cls.return_value = mock_instance

        server = FastMCP("test-kpe")
        register_kpe_tools(server)
        result = asyncio.run(server.call_tool(tool_name, params))
        return extract_call_tool_data(result)


# ── Tests: kpe_embed (via FastMCP call_tool) ──────────────────────────────


class TestKpeEmbed:
    """Single text embedding tool — response shape and dispatch verification."""

    def test_basic_embed(self) -> None:
        """Verify basic embedding with default provider."""
        data, mock_cls, mock_instance = _run_tool("kpe_embed", {"text": "hello world"})

        mock_cls.assert_called_once_with(provider="openai")
        mock_instance.embed.assert_called_once_with(["hello world"])
        assert data["success"] is True
        assert data["vector"] == SAMPLE_VECTOR
        assert data["dimensions"] == 5
        assert data["provider"] == "openai"
        assert data["text_length"] == 11

    def test_embed_with_custom_provider(self) -> None:
        """Verify custom provider is passed through."""
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [SAMPLE_VECTOR]
        mock_instance.model = "BAAI/bge-small-en-v1.5"

        data = _run_tool_with_mock(
            "kpe_embed",
            {"text": "embed me", "provider": "bge"},
            mock_instance,
        )

        assert data["provider"] == "bge"
        assert data["model"] == "BAAI/bge-small-en-v1.5"

    def test_embed_with_custom_model(self) -> None:
        """Verify explicit model overrides provider default."""
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [SAMPLE_VECTOR]
        mock_instance.model = "text-embedding-3-large"

        data = _run_tool_with_mock(
            "kpe_embed",
            {"text": "test", "provider": "openai", "model": "text-embedding-3-large"},
            mock_instance,
        )

        assert data["model"] == "text-embedding-3-large"

    def test_embed_empty_text(self) -> None:
        """Verify empty text produces a zero-length vector."""
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [[]]
        mock_instance.model = "text-embedding-3-small"

        data = _run_tool_with_mock("kpe_embed", {"text": ""}, mock_instance)

        assert data["success"] is True
        assert data["dimensions"] == 0
        assert data["text_length"] == 0

    def test_embed_response_keys(self) -> None:
        """Verify all expected response keys are present."""
        data, _mock_cls, _mock_instance = _run_tool("kpe_embed", {"text": "test"})

        expected_keys = {
            "success", "vector", "dimensions",
            "provider", "model", "provider_model",
            "text_length",
        }
        assert set(data.keys()) == expected_keys

    def test_embed_success_always_true(self) -> None:
        """Verify success is always True."""
        data, _mock_cls, _mock_instance = _run_tool("kpe_embed", {"text": "anything"})
        assert data["success"] is True


# ── Tests: kpe_embed_batch (via FastMCP call_tool) ────────────────────────


class TestKpeEmbedBatch:
    """Batch embedding tool — response shape and dispatch verification."""

    def test_basic_batch(self) -> None:
        """Verify batch embedding returns multiple vectors."""
        mock_instance = MagicMock()
        mock_instance.embed.return_value = SAMPLE_VECTORS
        mock_instance.model = "text-embedding-3-small"

        data = _run_tool_with_mock(
            "kpe_embed_batch",
            {"texts": ["first text", "second text", "third text"]},
            mock_instance,
        )

        assert data["success"] is True
        assert data["count"] == 3
        assert data["vectors"] == SAMPLE_VECTORS
        assert data["dimensions"] == 3

    def test_batch_single_text(self) -> None:
        """Verify batch works with a single text."""
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [[0.1, 0.2, 0.3]]
        mock_instance.model = "text-embedding-3-small"

        data = _run_tool_with_mock(
            "kpe_embed_batch",
            {"texts": ["single"]},
            mock_instance,
        )

        assert data["count"] == 1
        assert data["dimensions"] == 3

    def test_batch_empty_list(self) -> None:
        """Verify empty batch returns empty vectors list."""
        mock_instance = MagicMock()
        mock_instance.embed.return_value = []
        mock_instance.model = "text-embedding-3-small"

        data = _run_tool_with_mock(
            "kpe_embed_batch",
            {"texts": []},
            mock_instance,
        )

        assert data["count"] == 0
        assert data["vectors"] == []
        assert data["dimensions"] == 0

    def test_batch_custom_provider_and_model(self) -> None:
        """Verify custom provider and model are passed through."""
        mock_return = [[0.1, 0.2], [0.3, 0.4]]  # 2 vectors for 2 texts
        mock_instance = MagicMock()
        mock_instance.embed.return_value = mock_return
        mock_instance.model = "voyage-3"

        with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
            mock_cls.return_value = mock_instance

            server = FastMCP("test-kpe")
            register_kpe_tools(server)
            result = asyncio.run(
                server.call_tool(
                    "kpe_embed_batch",
                    {"texts": ["a", "b"], "provider": "voyage", "model": "voyage-3"},
                )
            )
            data = extract_call_tool_data(result)

            mock_cls.assert_called_once_with(provider="voyage", model="voyage-3")
            assert data["provider"] == "voyage"
            assert data["model"] == "voyage-3"
            assert data["count"] == 2
            assert len(data["vectors"]) == 2

    def test_batch_response_keys(self) -> None:
        """Verify all expected response keys are present in batch."""
        mock_instance = MagicMock()
        mock_instance.embed.return_value = SAMPLE_VECTORS
        mock_instance.model = "text-embedding-3-small"

        data = _run_tool_with_mock(
            "kpe_embed_batch",
            {"texts": ["a", "b", "c"]},
            mock_instance,
        )

        expected_keys = {
            "success", "vectors", "count",
            "dimensions", "provider", "model", "provider_model",
        }
        assert set(data.keys()) == expected_keys

    def test_batch_provider_passthrough(self) -> None:
        """Verify provider is passed to DenseEmbedder constructor."""
        with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.embed.return_value = [[0.1], [0.2]]
            mock_instance.model = "voyage-2"
            mock_cls.return_value = mock_instance

            server = FastMCP("test-kpe")
            register_kpe_tools(server)
            result = asyncio.run(
                server.call_tool(
                    "kpe_embed_batch",
                    {"texts": ["x", "y"], "provider": "voyage"},
                )
            )
            data = extract_call_tool_data(result)

            mock_cls.assert_called_once_with(provider="voyage")
            assert data["provider"] == "voyage"
            assert data["model"] == "voyage-2"
            assert data["count"] == 2
            assert len(data["vectors"]) == 2


# ── Registration Tests ──────────────────────────────────────────────────


class TestRegistration:
    """MCP tool registration integrity tests."""

    def test_embed_tools_resolve_via_call_tool(self) -> None:
        """Verify kpe_embed and kpe_embed_batch tools can be called by name."""
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [SAMPLE_VECTOR]
        mock_instance.model = "text-embedding-3-small"

        with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
            mock_cls.return_value = mock_instance

            server = FastMCP("test-kpe")
            register_kpe_tools(server)

            # kpe_embed responds
            result = asyncio.run(
                server.call_tool("kpe_embed", {"text": "test"})
            )
            data = extract_call_tool_data(result)
            assert data["success"] is True

        # kpe_embed_batch with its own mock to avoid state leak
        mock_instance2 = MagicMock()
        mock_instance2.embed.return_value = [[0.1], [0.2]]
        mock_instance2.model = "text-embedding-3-small"

        with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls2:
            mock_cls2.return_value = mock_instance2

            server2 = FastMCP("test-kpe-2")
            register_kpe_tools(server2)

            batch_result = asyncio.run(
                server2.call_tool("kpe_embed_batch", {"texts": ["a", "b"]})
            )
            batch_data = extract_call_tool_data(batch_result)
            assert batch_data["success"] is True
            assert batch_data["count"] == 2

    def test_tool_descriptions_meaningful(self) -> None:
        """Verify embed tools have meaningful descriptions."""
        server = FastMCP("test-kpe-desc")
        register_kpe_tools(server)
        tools = server._tool_manager.list_tools()  # type: ignore[union-attr]

        embed_tool = next(t for t in tools if t.name == "kpe_embed")
        assert embed_tool.description, "kpe_embed description is empty"
        assert len(embed_tool.description) > 30, "kpe_embed description too short"
        assert "vector" in embed_tool.description.lower()

        batch_tool = next(t for t in tools if t.name == "kpe_embed_batch")
        assert batch_tool.description, "kpe_embed_batch description is empty"
        assert len(batch_tool.description) > 30, "kpe_embed_batch description too short"
        assert "batch" in batch_tool.description.lower()

    def test_param_names(self) -> None:
        """Verify embed tools accept correct parameter names via call_tool."""
        # kpe_embed — no need for complex mock, just verify the param names work
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [[0.5]]
        mock_instance.model = "voyage-3"

        with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
            mock_cls.return_value = mock_instance

            server = FastMCP("test-kpe-params")
            register_kpe_tools(server)

            # text, provider, model all accepted
            result = asyncio.run(
                server.call_tool(
                    "kpe_embed",
                    {"text": "t", "provider": "voyage", "model": "voyage-3"},
                )
            )
            data = extract_call_tool_data(result)
            assert data["provider"] == "voyage"
            assert data["model"] == "voyage-3"

        # kpe_embed_batch — separate mock + server
        mock_instance2 = MagicMock()
        mock_instance2.embed.return_value = [[0.1], [0.2]]
        mock_instance2.model = "bge-base"

        with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls2:
            mock_cls2.return_value = mock_instance2

            server2 = FastMCP("test-kpe-params-2")
            register_kpe_tools(server2)

            batch_result = asyncio.run(
                server.call_tool(
                    "kpe_embed_batch",
                    {
                        "texts": ["x", "y"],
                        "provider": "bge",
                        "model": "BAAI/bge-base-en-v1.5",
                    },
                )
            )
            batch_data = extract_call_tool_data(batch_result)
            assert batch_data["provider"] == "bge"
            assert batch_data["count"] == 2
            assert len(batch_data["vectors"]) == 2
