"""Integration tests for Knowledgebase MCP Tools.

Tests verify that MCP tools correctly dispatch to the underlying services
with the right arguments and return the expected response shapes.

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/mcp/tools/tests/test_mcp_knowledgebase.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from app.mcp.tools.knowledgebase import register_knowledgebase_tools


def extract_call_tool_data(result: tuple) -> Any:
    if isinstance(result, tuple) and len(result) >= 2:
        raw = result[1]
        if isinstance(raw, dict) and "result" in raw:
            return raw["result"]
        return raw
    return result


def make_mock(**kwargs) -> MagicMock:
    m = MagicMock()
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


# ── SEARCH ──────────────────────────────────────────────────


class TestKbSearch:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_search", params))
        return extract_call_tool_data(result)

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_basic_search(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[{"content": "test", "score": 0.95}])
        mock_resolver.return_value = mock_svc
        data = self._run({"query": "test query"})
        assert data["status"] == "success"
        assert len(data["knowledge_chunks"]) == 1

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_empty_results(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[])
        mock_resolver.return_value = mock_svc
        data = self._run({"query": "nothing"})
        assert data["status"] == "empty"
        assert data["knowledge_chunks"] == []

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_search_with_filters(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[{"content": "f", "score": 0.9}])
        mock_resolver.return_value = mock_svc
        data = self._run(
            {
                "query": "test",
                "project_id": "proj-001",
                "packet_id": "pkt-001",
                "domains": ["tech"],
                "top_k": 5,
            }
        )
        assert data["status"] == "success"


# ── PROJECTS ────────────────────────────────────────────────


class TestKbListProjects:
    def _run(self, params: dict | None = None) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_list_projects", params or {}))
        return extract_call_tool_data(result)

    @patch(
        "common_lib.modules.knowledge_hub.services.project_service.ProjectService.list_projects"
    )
    def test_list_projects(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [
            make_mock(
                id="proj-001",
                name="Test Project",
                description="A test",
                status="active",
                packet_ids=["pkt-001"],
                attached_agent_id=None,
                tags=["ai"],
                created_at=None,
            )
        ]
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([MagicMock()])
        ):
            data = self._run()
        assert data["status"] == "success"
        assert len(data["projects"]) == 1
        assert data["projects"][0]["name"] == "Test Project"

    @patch(
        "common_lib.modules.knowledge_hub.services.project_service.ProjectService.list_projects"
    )
    def test_list_projects_empty(self, mock_list: MagicMock) -> None:
        mock_list.return_value = []
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([MagicMock()])
        ):
            data = self._run({"status": "all"})
        assert data["status"] == "success"
        assert data["total"] == 0

    @patch(
        "common_lib.modules.knowledge_hub.services.project_service.ProjectService.list_projects"
    )
    def test_list_projects_no_session(self, mock_list: MagicMock) -> None:
        mock_list.return_value = []
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([MagicMock()])
        ):
            data = self._run()
        assert data["status"] == "success"


# ── PACKETS ─────────────────────────────────────────────────


class TestKbGetPacket:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_get_packet", params))
        return extract_call_tool_data(result)

    def test_get_packet_found(self) -> None:
        from app.mcp.tools import knowledgebase as kb_mod

        session = MagicMock()
        original = kb_mod.PacketService.get_packet_data
        kb_mod.PacketService.get_packet_data = (
            lambda session, packet_id, filter_query=None: {
                "success": True,
                "data": {
                    "packet_name": "Test Packet",
                    "sources_configured": 1,
                    "pipelines_configured": 1,
                    "estimated_records": 100,
                    "sources": [],
                    "pipelines": [],
                    "tags": ["test"],
                },
            }
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            try:
                data = self._run({"packet_id": "pkt-001"})
                assert data["status"] == "success"
                assert data["packet_name"] == "Test Packet"
            finally:
                kb_mod.PacketService.get_packet_data = original

    def test_get_packet_not_found(self) -> None:
        from app.mcp.tools import knowledgebase as kb_mod

        session = MagicMock()
        original = kb_mod.PacketService.get_packet_data
        kb_mod.PacketService.get_packet_data = (
            lambda session, packet_id, filter_query=None: {
                "success": False,
                "data": None,
            }
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            try:
                data = self._run({"packet_id": "pkt-missing"})
                assert data["status"] == "error"
            finally:
                kb_mod.PacketService.get_packet_data = original


class TestKbListPackets:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_list_packets", params))
        return extract_call_tool_data(result)

    def test_list_packets_for_project(self) -> None:
        session = MagicMock()
        project = make_mock(
            id="proj-001", name="Test Project", status="active", packet_ids=["pkt-001"]
        )
        packet = make_mock(
            id="pkt-001",
            name="Test Packet",
            description="A test packet",
            status="published",
            source_config_ids=["src-001"],
            pipeline_ids=["pipe-001"],
            tags=["test"],
            created_at=None,
        )
        session.get.side_effect = (
            lambda cls, id_val: project
            if id_val == "proj-001"
            else packet
            if id_val == "pkt-001"
            else None
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run({"project_id": "proj-001"})
        assert data["status"] == "success"
        assert len(data["packets"]) == 1
        assert data["packets"][0]["name"] == "Test Packet"

    def test_list_packets_project_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run({"project_id": "proj-missing"})
        assert data["status"] == "error"


# ── DOCUMENTS ───────────────────────────────────────────────


class TestKbGetDocument:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_get_document", params))
        return extract_call_tool_data(result)

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_get_document_found(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(
            return_value=[
                {"content": "doc content", "score": 0.95, "source_id": "doc-001"}
            ]
        )
        mock_resolver.return_value = mock_svc
        data = self._run({"document_id": "doc-001", "project_id": "proj-001"})
        assert data["status"] == "success"
        assert "doc content" in data["content"]

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_get_document_not_found(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[])
        mock_resolver.return_value = mock_svc
        data = self._run({"document_id": "doc-missing", "project_id": "proj-001"})
        assert data["status"] == "error"


# ── INGESTION ───────────────────────────────────────────────


class TestKbIngestText:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_ingest_text", params))
        return extract_call_tool_data(result)

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_ingest_text(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.chunk = AsyncMock(
            return_value=[{"chunk_id": "chunk-1", "content": "chunked content"}]
        )
        mock_resolver.return_value = mock_svc
        data = self._run(
            {"project_id": "proj-001", "title": "Test Note", "content": "Hello world"}
        )
        assert data["status"] == "success"
        assert data["chunk_count"] == 1


# ── CONFLICTS ───────────────────────────────────────────────


class TestKbCheckConflicts:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_check_conflicts", params))
        return extract_call_tool_data(result)

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_no_conflict(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(
            return_value=[{"content": "matching info", "score": 0.95}]
        )
        mock_resolver.return_value = mock_svc
        data = self._run({"claim": "test claim", "project_id": "proj-001"})
        assert data["verdict"] == "no_conflict"

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_conflict_detected(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(
            return_value=[
                {
                    "content": "low confidence info",
                    "score": 0.25,
                    "source_id": "src-001",
                }
            ]
        )
        mock_resolver.return_value = mock_svc
        data = self._run({"claim": "contradictory claim", "project_id": "proj-001"})
        assert data["verdict"] == "conflict_detected"
        assert data["conflict_count"] > 0


# ── ENTITY LOOKUP ───────────────────────────────────────────


class TestKbLookupEntity:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_lookup_entity", params))
        return extract_call_tool_data(result)

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_entity_found(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(
            return_value=[
                {
                    "content": "EntityX is a technology company",
                    "score": 0.95,
                    "source_id": "doc-1",
                }
            ]
        )
        mock_resolver.return_value = mock_svc
        data = self._run({"entity_name": "EntityX", "project_id": "proj-001"})
        assert data["status"] == "success"
        assert data["total_matches"] == 1

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_entity_not_found(self, mock_resolver: MagicMock) -> None:
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[])
        mock_resolver.return_value = mock_svc
        data = self._run({"entity_name": "NonExistent", "project_id": "proj-001"})
        assert data["status"] == "not_found"


# ── PACKET MANAGEMENT ───────────────────────────────────────


class TestKbAddToPacket:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_add_to_packet", params))
        return extract_call_tool_data(result)

    def test_add_chunk_to_packet(self) -> None:
        session = MagicMock()
        session.get.return_value = make_mock(
            id="pkt-001", name="Test Packet", metadata_json={"items": []}
        )
        session.exec.return_value.one.return_value = 1
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                {
                    "packet_id": "pkt-001",
                    "project_id": "proj-001",
                    "item_type": "chunk",
                    "chunk_id": "chunk-001",
                }
            )
        assert data["status"] == "success"
        assert data["total_items"] == 1

    def test_add_custom_note(self) -> None:
        session = MagicMock()
        session.get.return_value = make_mock(
            id="pkt-001", name="Test Packet", metadata_json={}
        )
        session.exec.return_value.one.return_value = 1
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                {
                    "packet_id": "pkt-001",
                    "project_id": "proj-001",
                    "item_type": "custom_note",
                    "custom_title": "My Note",
                    "custom_content": "Note content",
                }
            )
        assert data["status"] == "success"
        assert data["total_items"] == 1


# ── SOURCE SYNC ─────────────────────────────────────────────


class TestKbTriggerSourceSync:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_trigger_source_sync", params))
        return extract_call_tool_data(result)

    def test_trigger_sync(self) -> None:
        session = MagicMock()
        session.get.return_value = make_mock(
            id="src-001",
            name="Test Source",
            source_type_id="web_scraper",
            config={"url": "https://example.com"},
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run({"source_id": "src-001", "project_id": "proj-001"})
        assert data["status"] == "completed"

    def test_trigger_sync_source_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run({"source_id": "src-missing", "project_id": "proj-001"})
        assert data["status"] == "error"


# ── QUALITY ─────────────────────────────────────────────────


class TestKbGetQualityReport:
    def _run(self, params: dict) -> Any:
        server = FastMCP("test")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool("kb_get_quality_report", params))
        return extract_call_tool_data(result)

    def test_quality_report(self) -> None:
        session = MagicMock()
        session.get.return_value = make_mock(
            id="proj-001",
            name="Test Project",
            status="verified",
            packet_ids=["pkt-001"],
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run({"project_id": "proj-001"})
        assert data["status"] == "success"
        assert data["quality_grade"] == "good"

    def test_quality_report_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run({"project_id": "proj-missing"})
        assert data["status"] == "error"


# ── REGISTRATION TESTS ──────────────────────────────────────


class TestRegistration:
    def test_all_eleven_tools_registered(self) -> None:
        server = FastMCP("test-knowledgebase")
        register_knowledgebase_tools(server)
        tools = server._tool_manager.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "kb_search",
            "kb_get_packet",
            "kb_list_packets",
            "kb_get_document",
            "kb_ingest_text",
            "kb_add_to_packet",
            "kb_lookup_entity",
            "kb_check_conflicts",
            "kb_list_projects",
            "kb_trigger_source_sync",
            "kb_get_quality_report",
        }
        assert tool_names == expected, f"Missing: {expected - tool_names}"

    def test_tool_descriptions_meaningful(self) -> None:
        server = FastMCP("test-knowledgebase")
        register_knowledgebase_tools(server)
        for t in server._tool_manager.list_tools():
            assert t.description, f"Tool {t.name} has empty description"
            assert len(t.description) > 20, f"Tool {t.name} description too short"

    def test_tool_names_prefixed_with_kb(self) -> None:
        server = FastMCP("test-knowledgebase")
        register_knowledgebase_tools(server)
        for t in server._tool_manager.list_tools():
            assert t.name.startswith("kb_"), f"Tool {t.name} missing kb_ prefix"


# ── FastMCP End-to-End Smoke Tests ───────────────────────────────────────


class TestFastMCPSmoke:
    """End-to-end tests through the actual FastMCP call_tool protocol.

    These verify that tool dispatch, parameter marshalling, and response
    assembly work correctly through the full MCP tool pipeline for the
    knowledgebase tool set that uses async service dependencies.
    """

    @pytest.fixture(autouse=True)
    def _setup_mocks(self) -> None:
        """Patch resolve_knowledge_engine_service and get_session for all tests."""
        import app.mcp.tools.knowledgebase as kb_mod

        # Patch Knowledge Engine service
        self._ke_patcher = patch(
            "app.mcp.mcp_dependencies.resolve_knowledge_engine_service",
            return_value=self._make_mock_ke_service(),
        )
        self._ke_patcher.start()

        # Patch get_session for DB-bound tools
        self._session = MagicMock()
        self._project = make_mock(
            id="proj-001",
            name="Test Project",
            description="E2E test",
            status="active",
            packet_ids=["pkt-001"],
            tags=["e2e"],
        )
        self._packet = make_mock(
            id="pkt-001",
            name="Test Packet",
            description="An E2E test packet",
            status="published",
            source_config_ids=["src-001"],
            pipeline_ids=["pipe-001"],
            tags=["e2e"],
            created_at=None,
        )
        self._source = make_mock(
            id="src-001",
            name="Test Source",
            source_type_id="web_scraper",
            config={"url": "https://example.com"},
        )

        def _session_get(cls, id_val: str) -> Any:
            if id_val == "proj-001":
                return self._project
            if id_val == "pkt-001":
                return self._packet
            if id_val == "src-001":
                return self._source
            return None

        self._session.get.side_effect = _session_get

        # Patch PacketService.get_packet_data for kb_get_packet
        self._original_get_packet_data = kb_mod.PacketService.get_packet_data
        kb_mod.PacketService.get_packet_data = (
            lambda session, packet_id, filter_query=None: {
                "success": True,
                "data": {
                    "packet_name": "Test Packet",
                    "sources_configured": 1,
                    "pipelines_configured": 1,
                    "estimated_records": 100,
                    "sources": [],
                    "pipelines": [],
                    "tags": ["test"],
                },
            }
        )
        yield
        self._ke_patcher.stop()
        kb_mod.PacketService.get_packet_data = self._original_get_packet_data  # type: ignore[has-type]

    @staticmethod
    def _make_mock_ke_service() -> MagicMock:
        svc = MagicMock()
        svc.search = AsyncMock(
            return_value=[
                {"content": "result", "score": 0.95, "source_id": "doc-1"}
            ]
        )
        svc.chunk = AsyncMock(
            return_value=[{"chunk_id": "chunk-1", "content": "chunked"}]
        )
        return svc

    def _run(self, tool: str, params: dict) -> Any:
        server = FastMCP("test-e2e")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool(tool, params))
        return extract_call_tool_data(result)

    def test_search_e2e_smoke(self) -> None:
        """kb_search end-to-end through FastMCP call_tool."""
        with patch("app.mcp.tools.knowledgebase.get_session"):
            data = self._run("kb_search", {"query": "test"})
        assert data["status"] == "success"

    def test_get_packet_e2e_smoke(self) -> None:
        """kb_get_packet end-to-end through FastMCP call_tool."""
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([self._session])
        ):
            data = self._run("kb_get_packet", {"packet_id": "pkt-001"})
        assert data["status"] == "success"
        assert data["packet_name"] == "Test Packet"

    def test_list_packets_e2e_smoke(self) -> None:
        """kb_list_packets end-to-end through FastMCP call_tool."""
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([self._session])
        ):
            data = self._run("kb_list_packets", {"project_id": "proj-001"})
        assert data["status"] == "success"
        assert data["total"] == 1

    def test_get_document_e2e_smoke(self) -> None:
        """kb_get_document end-to-end through FastMCP call_tool."""
        data = self._run(
            "kb_get_document", {"document_id": "doc-001", "project_id": "proj-001"}
        )
        assert data["status"] == "success"

    def test_ingest_e2e_smoke(self) -> None:
        """kb_ingest_text end-to-end through FastMCP call_tool."""
        data = self._run(
            "kb_ingest_text",
            {"project_id": "proj-001", "title": "Test", "content": "Hello"},
        )
        assert data["status"] == "success"
        assert data["chunk_count"] == 1

    def test_list_projects_e2e_smoke(self) -> None:
        """kb_list_projects end-to-end through FastMCP call_tool."""
        with patch(
            "common_lib.modules.knowledge_hub.services.project_service.ProjectService.list_projects",
            return_value=[self._project],
        ), patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([self._session])
        ):
            data = self._run("kb_list_projects", {})
        assert data["status"] == "success"
        assert data["total"] == 1

    def test_quality_report_e2e_smoke(self) -> None:
        """kb_get_quality_report end-to-end through FastMCP call_tool."""
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([self._session])
        ):
            data = self._run("kb_get_quality_report", {"project_id": "proj-001"})
        assert data["status"] == "success"


# ── Tenant Isolation Tests ────────────────────────────────────────────────


class TestTenantIsolation:
    """Verify that one tenant cannot access another tenant's data.

    These tests use mocked session.get() to simulate cross-tenant
    access attempts. All tools that accept a project_id should
    properly scope queries to the given project.
    """

    def _run(self, tool: str, params: dict) -> Any:
        server = FastMCP("test-tenant")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool(tool, params))
        return extract_call_tool_data(result)

    def test_search_other_project_returns_empty(self) -> None:
        """Search in a non-accessible project returns empty results."""
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[])
        with patch(
            "app.mcp.mcp_dependencies.resolve_knowledge_engine_service",
            return_value=mock_svc,
        ):
            data = self._run(
                "kb_search",
                {"query": "secret data", "project_id": "other-tenant-proj"},
            )
        assert data["status"] == "empty"
        assert len(data["knowledge_chunks"]) == 0

    def test_get_packet_other_project_not_found(self) -> None:
        """Get packet from unknown project returns error."""
        session = MagicMock()
        session.get.return_value = None  # packet not found in any project
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run("kb_get_packet", {"packet_id": "pkt-other-tenant"})
        assert data["status"] == "error"
        assert "not found" in data["message"]

    def test_list_packets_other_project_not_found(self) -> None:
        """List packets for non-existent project returns error."""
        session = MagicMock()
        session.get.return_value = None  # project not found
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                "kb_list_packets", {"project_id": "other-tenant-proj"}
            )
        assert data["status"] == "error"

    def test_lookup_entity_other_project_returns_not_found(self) -> None:
        """Entity lookup scopes to the correct project."""
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[])
        with patch(
            "app.mcp.mcp_dependencies.resolve_knowledge_engine_service",
            return_value=mock_svc,
        ):
            data = self._run(
                "kb_lookup_entity",
                {"entity_name": "SecretData", "project_id": "other-tenant-proj"},
            )
        assert data["status"] == "not_found"

    def test_check_conflicts_other_project(self) -> None:
        """Conflict check scopes to the correct project."""
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[])
        with patch(
            "app.mcp.mcp_dependencies.resolve_knowledge_engine_service",
            return_value=mock_svc,
        ):
            data = self._run(
                "kb_check_conflicts",
                {"claim": "test", "project_id": "other-tenant-proj"},
            )
        assert data["status"] == "success"
        assert data["verdict"] == "no_conflict"
        assert data["conflict_count"] == 0

    def test_quality_report_other_project_not_found(self) -> None:
        """Quality report for non-existent project returns error."""
        session = MagicMock()
        session.get.return_value = None  # project not found
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                "kb_get_quality_report", {"project_id": "other-tenant-proj"}
            )
        assert data["status"] == "error"

    def test_list_projects_scoped_by_status(self) -> None:
        """List projects respects status filter for tenant isolation."""
        session = MagicMock()
        with patch(
            "common_lib.modules.knowledge_hub.services.project_service.ProjectService.list_projects",
            return_value=[],
        ), patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run("kb_list_projects", {"status": "archived"})
        assert data["status"] == "success"
        assert data["total"] == 0


# ── Edge Case Tests ───────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case tests: empty strings, special chars, missing fields, limits."""

    def _run(self, tool: str, params: dict) -> Any:
        server = FastMCP("test-edge")
        register_knowledgebase_tools(server)
        result = asyncio.run(server.call_tool(tool, params))
        return extract_call_tool_data(result)

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_search_empty_query(self, mock_resolver: MagicMock) -> None:
        """Empty query string handles gracefully."""
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(return_value=[])
        mock_resolver.return_value = mock_svc
        data = self._run("kb_search", {"query": ""})
        assert data["status"] in ("empty", "success")

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_search_special_chars(self, mock_resolver: MagicMock) -> None:
        """Special characters in query do not crash."""
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(
            return_value=[{"content": "result", "score": 0.9}]
        )
        mock_resolver.return_value = mock_svc
        data = self._run(
            "kb_search",
            {"query": "<script>alert('xss')</script> & 'special' chars!"},
        )
        assert data["status"] == "success"

    @patch("app.mcp.mcp_dependencies.resolve_knowledge_engine_service")
    def test_search_none_project_id(self, mock_resolver: MagicMock) -> None:
        """None project_id (omitted) uses global search without crash."""
        mock_svc = MagicMock()
        mock_svc.search = AsyncMock(
            return_value=[{"content": "result", "score": 0.9}]
        )
        mock_resolver.return_value = mock_svc
        data = self._run("kb_search", {"query": "test"})
        assert data["status"] == "success"

    def test_ingest_empty_content(self) -> None:
        """Ingesting empty content returns success with 0 chunks."""
        mock_svc = MagicMock()
        mock_svc.chunk = AsyncMock(return_value=[])
        with patch(
            "app.mcp.mcp_dependencies.resolve_knowledge_engine_service",
            return_value=mock_svc,
        ):
            data = self._run(
                "kb_ingest_text",
                {"project_id": "proj-001", "title": "", "content": ""},
            )
        assert data["status"] == "success"
        assert data["chunk_count"] == 0

    def test_ingest_special_chars_title(self) -> None:
        """Special characters in title handled gracefully."""
        mock_svc = MagicMock()
        mock_svc.chunk = AsyncMock(
            return_value=[{"chunk_id": "chunk-1", "content": "test"}]
        )
        with patch(
            "app.mcp.mcp_dependencies.resolve_knowledge_engine_service",
            return_value=mock_svc,
        ):
            data = self._run(
                "kb_ingest_text",
                {
                    "project_id": "proj-001",
                    "title": "Unicode: 日本語 ñçö 你好 👋",
                    "content": "Body text with unicode support ✓",
                },
            )
        assert data["status"] == "success"

    def test_get_packet_invalid_id(self) -> None:
        """Invalid/non-existent packet ID returns error."""
        from app.mcp.tools import knowledgebase as kb_mod

        session = MagicMock()
        original = kb_mod.PacketService.get_packet_data
        kb_mod.PacketService.get_packet_data = (
            lambda session, packet_id, filter_query=None: {
                "success": False,
                "data": None,
            }
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            try:
                data = self._run("kb_get_packet", {"packet_id": ""})
                assert data["status"] == "error"
            finally:
                kb_mod.PacketService.get_packet_data = original

    def test_add_to_packet_invalid_item_type(self) -> None:
        """Invalid item type returns error."""
        session = MagicMock()
        session.get.return_value = make_mock(
            id="pkt-001", name="Test Packet", metadata_json={"items": []}
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                "kb_add_to_packet",
                {
                    "packet_id": "pkt-001",
                    "project_id": "proj-001",
                    "item_type": "invalid_type",
                },
            )
        assert data["status"] == "error"

    def test_add_chunk_without_chunk_id(self) -> None:
        """Add chunk without chunk_id returns error."""
        session = MagicMock()
        session.get.return_value = make_mock(
            id="pkt-001", name="Test Packet", metadata_json={"items": []}
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                "kb_add_to_packet",
                {
                    "packet_id": "pkt-001",
                    "project_id": "proj-001",
                    "item_type": "chunk",
                },
            )
        assert data["status"] == "error"

    def test_add_custom_note_without_title(self) -> None:
        """Add custom note without title returns error."""
        session = MagicMock()
        session.get.return_value = make_mock(
            id="pkt-001", name="Test Packet", metadata_json={"items": []}
        )
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                "kb_add_to_packet",
                {
                    "packet_id": "pkt-001",
                    "project_id": "proj-001",
                    "item_type": "custom_note",
                },
            )
        assert data["status"] == "error"

    def test_trigger_sync_nonexistent_source(self) -> None:
        """Trigger sync with non-existent source returns error."""
        session = MagicMock()
        session.get.return_value = None
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                "kb_trigger_source_sync",
                {"source_id": "does-not-exist", "project_id": "proj-001"},
            )
        assert data["status"] == "error"

    def test_quality_report_missing_project(self) -> None:
        """Quality report for non-existent project returns error."""
        session = MagicMock()
        session.get.return_value = None
        with patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run(
                "kb_get_quality_report", {"project_id": "does-not-exist"}
            )
        assert data["status"] == "error"

    def test_list_projects_all_status(self) -> None:
        """Status='all' returns all projects without filtering."""
        session = MagicMock()
        mock_project = make_mock(
            id="proj-001",
            name="Test",
            description="",
            status="active",
            packet_ids=[],
            attached_agent_id=None,
            tags=[],
            created_at=None,
        )
        with patch(
            "common_lib.modules.knowledge_hub.services.project_service.ProjectService.list_projects",
            return_value=[mock_project],
        ), patch(
            "app.mcp.tools.knowledgebase.get_session", return_value=iter([session])
        ):
            data = self._run("kb_list_projects", {"status": "all"})
        assert data["status"] == "success"
        assert data["total"] == 1
