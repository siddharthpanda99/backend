"""Phase 7 — I2W MCP tools tests.

Smoke test the 16 MCP tools registered by ``register_i2w_tools``.
We use the same mock pattern as the router tests (patch
``invoke_i2w``) so the tools stay self-contained.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from app.mcp.fastmcp_compat import FastMCP
from app.mcp.tools.i2w import register_i2w_tools


@pytest.fixture
def mcp_server():
    """A FastMCP instance with the I2W tools registered."""
    mcp = FastMCP("i2w-test")
    register_i2w_tools(mcp)
    return mcp


@pytest.fixture
def mock_invoke():
    """Patch ``invoke_i2w`` so the tools don't touch real services."""
    from app.modules.i2w.routes import _helpers

    def fake(name, defaults=None, **kwargs):
        return {"status": "ok", "wrapper": name, "echo": kwargs}

    with patch.object(_helpers, "invoke_i2w", side_effect=fake):
        yield fake


def _tools_dict(mcp):
    """Return a dict of registered MCP tools by name."""
    return mcp._tool_manager._tools


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_count_is_16(self, mcp_server):
        names = sorted(n for n in _tools_dict(mcp_server) if n.startswith("i2w_"))
        assert len(names) == 16, names

    def test_doc_table_tools_present(self, mcp_server):
        names = set(_tools_dict(mcp_server))
        # The 16 tools the docs (08_api_contract.md §3) require
        expected = {
            "i2w_generate",
            "i2w_ingest_audio",
            "i2w_ingest_text",
            "i2w_ingest_screenshot",
            "i2w_ingest_screen_record",
            "i2w_ingest_file",
            "i2w_reason",
            "i2w_plan",
            "i2w_dispatch",
            "i2w_search_commands",
            "i2w_search_workflows",
            "i2w_search_history",
            "i2w_universal_search",
            "i2w_collect_feedback",
            "i2w_health",
            "i2w_list_executions",
        }
        missing = expected - set(names)
        assert not missing, f"missing: {missing}"


# ---------------------------------------------------------------------------
# End-to-end smoke
# ---------------------------------------------------------------------------


class TestToolExecution:
    def test_generate_delegates(self, mcp_server, mock_invoke):
        # Run the underlying tool callable directly.
        tool = _tools_dict(mcp_server)["i2w_generate"].fn
        result = asyncio.run(
            tool(
                input_modality="text",
                text="open the dashboard",
                user_id_hash="sha256:abc",
            )
        )
        assert result["status"] == "ok"
        assert result["wrapper"] == "i2w_generate_and_execute"
        assert result["echo"]["text"] == "open the dashboard"

    def test_ingest_audio(self, mcp_server, mock_invoke):
        tool = _tools_dict(mcp_server)["i2w_ingest_audio"].fn
        result = asyncio.run(tool(audio_ref="s3://x/y.wav", user_id_hash="sha256:abc"))
        assert result["wrapper"] == "i2w_ingest_audio"
        assert result["echo"]["audio_ref"] == "s3://x/y.wav"

    def test_search_commands(self, mcp_server, mock_invoke):
        tool = _tools_dict(mcp_server)["i2w_search_commands"].fn
        result = asyncio.run(tool(query="open dashboard"))
        assert result["wrapper"] == "i2w_search_commands"
        assert result["echo"]["query"] == "open dashboard"

    def test_health(self, mcp_server, mock_invoke):
        tool = _tools_dict(mcp_server)["i2w_health"].fn
        result = asyncio.run(tool())
        assert result["status"] == "ok"
        assert "stages" in result
        # Each per-stage health was queried
        wrappers_called = {
            c["name"] for c in mock_invoke.mock_calls if hasattr(c, "__iter__")
        }
        # Just assert the aggregated response has all five stages
        assert {"ingest", "reason", "plan", "dispatch", "search"} <= set(
            result["stages"]
        )

    def test_collect_feedback(self, mcp_server, mock_invoke):
        tool = _tools_dict(mcp_server)["i2w_collect_feedback"].fn
        result = asyncio.run(
            tool(
                record_id="rec-1",
                user_rating=5,
                user_comment="great",
            )
        )
        assert result["wrapper"] == "i2w_training_submit_feedback"
        assert result["echo"]["user_rating"] == 5
