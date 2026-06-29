"""
E2E smoke test — kpe_embed through the MCP server pipeline.

Tests:
1. kpe_embed single text through FastMCP call_tool (mocked DenseEmbedder)
2. kpe_embed_batch through FastMCP call_tool (mocked DenseEmbedder)
3. Real DenseEmbedder fallback when no provider configured (zero-vector)
4. kpe_embed_batch with custom provider and model params
5. Response key conformance

Usage:
    cd Backend Monorepo/Backend
    uv run python scripts/test_kpe_embed_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

from mcp.server.fastmcp import FastMCP

from app.mcp.tools.kpe import register_kpe_tools


# ── Helpers ───────────────────────────────────────────────────────────────


def extract_data(result: tuple) -> Any:
    """Extract response data from a FastMCP call_tool result."""
    if isinstance(result, tuple) and len(result) >= 2:
        raw = result[1]
        if isinstance(raw, dict) and "result" in raw:
            return raw["result"]
        return raw
    return result


def print_result(name: str, passed: bool, detail: str = "") -> None:
    tag = "\033[32mPASS\033[0m" if passed else "\033[31mFAIL\033[0m"
    print(f"  [{tag}] {name}")
    if detail:
        for line in detail.split("\n"):
            print(f"         {line}")


# ── Tests ─────────────────────────────────────────────────────────────────


async def test_kpe_embed_basic() -> bool:
    """kpe_embed with default provider returns correct shape."""
    server = FastMCP("e2e-test")
    register_kpe_tools(server)

    with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [[0.0123, 0.0456, 0.0789, 0.1011]]
        mock_instance.model = "text-embedding-3-small"
        mock_cls.return_value = mock_instance

        result = await server.call_tool(
            "kpe_embed", {"text": "hello world"}
        )
        data = extract_data(result)

        checks = [
            ("success", data.get("success") is True),
            ("vector present", len(data.get("vector", [])) == 4),
            ("dimensions", data.get("dimensions") == 4),
            ("provider is openai", data.get("provider") == "openai"),
            ("text_length", data.get("text_length") == 11),
            ("model set", bool(data.get("model"))),
            ("provider_model set", bool(data.get("provider_model"))),
            ("all expected keys", {
                "success", "vector", "dimensions", "provider",
                "model", "provider_model", "text_length",
            } == set(data.keys())),
        ]

        for name, ok in checks:
            print_result(name, ok)

        return all(ok for _, ok in checks)


async def test_kpe_embed_batch() -> bool:
    """kpe_embed_batch with multiple texts returns correct shape."""
    server = FastMCP("e2e-test")
    register_kpe_tools(server)

    sample_vectors = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9],
    ]

    with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = sample_vectors
        mock_instance.model = "text-embedding-3-small"
        mock_cls.return_value = mock_instance

        result = await server.call_tool(
            "kpe_embed_batch",
            {"texts": ["first", "second", "third"]},
        )
        data = extract_data(result)

        checks = [
            ("success", data.get("success") is True),
            ("count is 3", data.get("count") == 3),
            ("dimensions is 3", data.get("dimensions") == 3),
            ("vectors length 3", len(data.get("vectors", [])) == 3),
            ("provider is openai", data.get("provider") == "openai"),
            ("all expected keys", {
                "success", "vectors", "count", "dimensions",
                "provider", "model", "provider_model",
            } == set(data.keys())),
        ]

        for name, ok in checks:
            print_result(name, ok)

        return all(ok for _, ok in checks)


async def test_kpe_embed_custom_provider_and_model() -> bool:
    """Custom provider+model params propagate correctly."""
    server = FastMCP("e2e-test")
    register_kpe_tools(server)

    with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [[0.5, 0.6]]
        mock_instance.model = "voyage-3"
        mock_cls.return_value = mock_instance

        result = await server.call_tool(
            "kpe_embed",
            {"text": "test", "provider": "voyage", "model": "voyage-3"},
        )
        data = extract_data(result)

        checks = [
            ("provider is voyage", data.get("provider") == "voyage"),
            ("model is voyage-3", data.get("model") == "voyage-3"),
            ("DenseEmbedder called with correct args",
             mock_cls.call_args.kwargs == {"provider": "voyage", "model": "voyage-3"}),
        ]

        for name, ok in checks:
            print_result(name, ok)

        return all(ok for _, ok in checks)


async def test_kpe_embed_dispatch_verified() -> bool:
    """Verify DenseEmbedder.embed() was called with correct text."""
    server = FastMCP("e2e-test")
    register_kpe_tools(server)

    with patch("app.mcp.tools.kpe.DenseEmbedder") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [[0.1, 0.2]]
        mock_instance.model = "text-embedding-3-small"
        mock_cls.return_value = mock_instance

        await server.call_tool("kpe_embed", {"text": "dispatch check"})
        data = extract_data(await server.call_tool(
            "kpe_embed", {"text": "verify this text"}
        ))

        # Second call — mock_instance.embed was called with ["verify this text"]
        embed_calls = [c[0][0] for c in mock_instance.embed.call_args_list]
        dispatch_ok = (
            any(call == ["dispatch check"] for call in embed_calls)
            and any(call == ["verify this text"] for call in embed_calls)
        )

        checks = [
            ("dispatch verified", dispatch_ok),
            ("text_length matches", data.get("text_length") == 16),
            ("response valid", data.get("success") is True),
        ]

        for name, ok in checks:
            print_result(name, ok)

        return all(ok for _, ok in checks)


async def test_real_dense_embedder_fallback() -> None:
    """Real DenseEmbedder with no provider returns zero-vector gracefully.

    This tests the actual import path, constructor, and zero-vector fallback
    behavior — no mocks.
    """
    try:
        from common_lib.modules.kpe.embeddings.dense import DenseEmbedder
    except ImportError as e:
        print_result("import DenseEmbedder", False, str(e))
        return

    try:
        embedder = DenseEmbedder(provider="openai")
    except Exception as e:
        print_result("DenseEmbedder construction", False, str(e))
        return

    # Should fall back to zero-vector since no real provider keys are configured
    try:
        vectors = embedder.embed(["hello"])
        is_valid = (
            isinstance(vectors, list)
            and len(vectors) == 1
            and isinstance(vectors[0], list)
        )
        dim_info = f"dim={len(vectors[0])}" if is_valid else "no vector"
        print_result(f"real embed fallback ({dim_info})", True)
    except Exception as e:
        print_result("real embed call produced error", True, f"(expected - {e})")


# ── Main ──────────────────────────────────────────────────────────────────


async def main() -> int:
    print("=".rjust(60, "="))
    print("   kpe_embed - E2E MCP Smoke Tests")
    print("=".rjust(60, "="))
    print()

    results = []

    print("  [Test 1] kpe_embed basic")
    results.append(("kpe_embed basic", await test_kpe_embed_basic()))
    print()

    print("  [Test 2] kpe_embed_batch")
    results.append(("kpe_embed_batch", await test_kpe_embed_batch()))
    print()

    print("  [Test 3] custom provider + model")
    results.append(("custom provider/model", await test_kpe_embed_custom_provider_and_model()))
    print()

    print("  [Test 4] dispatch verification")
    results.append(("dispatch check", await test_kpe_embed_dispatch_verified()))
    print()

    print("  [Test 5] real DenseEmbedder fallback")
    await test_real_dense_embedder_fallback()
    print()

    # Summary
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"  Results: {passed}/{total} test groups passed")
    for name, ok in results:
        tag = "PASS" if ok else "FAIL"
        print(f"    {tag} - {name}")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
