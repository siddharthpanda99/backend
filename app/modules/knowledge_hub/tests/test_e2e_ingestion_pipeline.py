"""
E2E tests for the full ingestion pipeline flow.

Tests the complete source → pipeline → packet → project lifecycle
using seed data sources that return real records (src-arxiv-001,
src-github-001). Includes execution, verification, data object
building, and agent attach/detach.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python -m pytest app/modules/knowledge_hub/tests/test_e2e_ingestion_pipeline.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

PREFIX = "/api/v1/knowledge-hub"

# ═══════════════════════════════════════════════════════════════════
# Phase 1: Source Execution & Verification
# ═══════════════════════════════════════════════════════════════════


class TestSourceExecution:
    """Execute and verify seed data sources."""

    def test_01_execute_arxiv_source(self, client: TestClient) -> None:
        """Execute the ArXiv source — should return sample data."""
        resp = client.post(f"{PREFIX}/sources/src-arxiv-001/execute")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "completed"
        assert body["source_config_id"] == "src-arxiv-001"
        assert body["record_count"] > 0
        assert isinstance(body["data"], list)
        assert len(body["data"]) == body["record_count"]
        assert body["execution_time_ms"] >= 0

    def test_02_execute_github_source(self, client: TestClient) -> None:
        """Execute the GitHub source — should return sample data."""
        resp = client.post(f"{PREFIX}/sources/src-github-001/execute")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "completed"
        assert body["source_config_id"] == "src-github-001"
        assert body["record_count"] > 0
        assert isinstance(body["data"], list)

    def test_03_execute_remaining_seed_sources(self, client: TestClient) -> None:
        """Execute remaining seed sources that actually exist."""
        for src_id in ["src-techcrunch-001", "src-reddit-001"]:
            resp = client.post(f"{PREFIX}/sources/{src_id}/execute")
            assert resp.status_code == 200, f"Failed to execute {src_id}"
            assert resp.json()["status"] == "completed"

    def test_04_verify_arxiv_source(self, client: TestClient) -> None:
        """Verify the ArXiv source after execution."""
        resp = client.post(f"{PREFIX}/sources/src-arxiv-001/verify")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "verified"
        assert resp.json()["data"]["verified_at"] is not None

    def test_05_verify_github_source(self, client: TestClient) -> None:
        """Verify the GitHub source after execution."""
        resp = client.post(f"{PREFIX}/sources/src-github-001/verify")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "verified"

    def test_06_preview_arxiv_source(self, client: TestClient) -> None:
        """Preview returns sample data from the ArXiv source."""
        resp = client.get(f"{PREFIX}/sources/src-arxiv-001/preview?limit=3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["preview"]) <= 3
        assert len(body["preview"]) > 0


# ═══════════════════════════════════════════════════════════════════
# Phase 2: Pipeline Creation & Execution
# ═══════════════════════════════════════════════════════════════════


class TestPipelineExecution:
    """Create, execute, and verify ingestion pipelines."""

    PIPE_IDS: list[str] = []

    def test_07_validate_pipeline_definition(self, client: TestClient) -> None:
        """Validate a pipeline definition is structurally correct."""
        resp = client.post(
            f"{PREFIX}/pipelines/validate",
            json={
                "pipeline_definition": {
                    "version": "1.0",
                    "type": "extract_transform",
                    "steps": [
                        {"name": "fetch", "operation": "api_query", "config": {}},
                        {"name": "parse", "operation": "json_parse", "config": {"fields": ["id", "title"]}},
                    ],
                    "output": {"format": "structured_records"},
                }
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["valid"] is True
        assert resp.json()["data"]["steps_count"] == 2
        assert len(resp.json()["data"]["errors"]) == 0

    def test_08_validate_malformed_pipeline(self, client: TestClient) -> None:
        """Validating a malformed pipeline returns errors."""
        resp = client.post(
            f"{PREFIX}/pipelines/validate",
            json={"pipeline_definition": {"version": "1.0"}},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["valid"] is False
        assert len(resp.json()["data"]["errors"]) > 0

    def test_09_create_arxiv_pipeline(self, client: TestClient) -> None:
        """Create a pipeline for the ArXiv source."""
        resp = client.post(
            f"{PREFIX}/pipelines",
            json={
                "id": "e2e-pipe-arxiv",
                "name": "E2E ArXiv Pipeline",
                "description": "Pipeline for E2E testing with ArXiv source",
                "source_config_id": "src-arxiv-001",
                "pipeline_definition": {
                    "version": "1.0",
                    "type": "extract_transform",
                    "steps": [
                        {"name": "fetch", "operation": "api_query", "config": {}},
                        {"name": "parse", "operation": "json_parse", "config": {"fields": ["id", "title", "summary"]}},
                    ],
                    "output": {"format": "structured_records"},
                },
            },
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["id"] == "e2e-pipe-arxiv"
        assert d["name"] == "E2E ArXiv Pipeline"
        assert d["status"] == "draft"
        assert d["last_executed_at"] is None
        self.PIPE_IDS.append("e2e-pipe-arxiv")

    def test_10_create_github_pipeline(self, client: TestClient) -> None:
        """Create a pipeline for the GitHub source."""
        resp = client.post(
            f"{PREFIX}/pipelines",
            json={
                "id": "e2e-pipe-github",
                "name": "E2E GitHub Pipeline",
                "source_config_id": "src-github-001",
                "pipeline_definition": {
                    "version": "1.0",
                    "type": "extract",
                    "steps": [{"name": "search", "operation": "api_query", "config": {}}],
                    "output": {"format": "structured_records"},
                },
            },
        )
        assert resp.status_code == 201
        self.PIPE_IDS.append("e2e-pipe-github")

    def test_11_execute_arxiv_pipeline(self, client: TestClient) -> None:
        """Execute the ArXiv pipeline — should produce records."""
        resp = client.post(f"{PREFIX}/pipelines/e2e-pipe-arxiv/execute")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "completed"
        assert body["total_records"] > 0

        # Verify step results
        assert len(body["steps"]) > 0
        for step in body["steps"]:
            assert step["status"] == "completed"
            assert step["records_processed"] > 0
            assert step["duration_ms"] >= 0  # Can be 0 for very fast steps

        # Verify pipeline record updated
        get_resp = client.get(f"{PREFIX}/pipelines/e2e-pipe-arxiv")
        assert get_resp.json()["data"]["last_executed_at"] is not None
        assert get_resp.json()["data"]["last_execution_result"] is not None

    def test_12_execute_github_pipeline(self, client: TestClient) -> None:
        """Execute the GitHub pipeline."""
        resp = client.post(f"{PREFIX}/pipelines/e2e-pipe-github/execute")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["status"] == "completed"

    def test_13_verify_arxiv_pipeline(self, client: TestClient) -> None:
        """Verify the ArXiv pipeline after successful execution."""
        resp = client.post(f"{PREFIX}/pipelines/e2e-pipe-arxiv/verify")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "verified"
        assert resp.json()["data"]["verified_by"] == "system"
        assert "verified successfully" in resp.json()["message"]

    def test_14_verify_github_pipeline(self, client: TestClient) -> None:
        """Verify the GitHub pipeline after successful execution."""
        resp = client.post(f"{PREFIX}/pipelines/e2e-pipe-github/verify")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "verified"


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Packet Creation & Verification
# ═══════════════════════════════════════════════════════════════════


class TestPacketLifecycle:
    """Create, resolve, test-all, and verify data packets."""

    PKT_IDS: list[str] = []

    def test_15_create_multi_source_packet(self, client: TestClient) -> None:
        """Create a packet that links both ArXiv and GitHub sources."""
        resp = client.post(
            f"{PREFIX}/packets",
            json={
                "id": "e2e-pkt-multi",
                "name": "E2E Multi-Source Packet",
                "description": "Packet combining ArXiv and GitHub data for E2E testing",
                "source_config_ids": ["src-arxiv-001", "src-github-001"],
                "pipeline_ids": ["e2e-pipe-arxiv", "e2e-pipe-github"],
                "tags": ["e2e-test", "multi-source"],
            },
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["id"] == "e2e-pkt-multi"
        assert d["name"] == "E2E Multi-Source Packet"
        assert d["status"] == "draft"
        assert len(d["source_config_ids"]) == 2
        assert len(d["pipeline_ids"]) == 2
        self.PKT_IDS.append("e2e-pkt-multi")

    def test_16_create_arxiv_only_packet(self, client: TestClient) -> None:
        """Create a packet that only uses the ArXiv source."""
        resp = client.post(
            f"{PREFIX}/packets",
            json={
                "id": "e2e-pkt-arxiv-only",
                "name": "E2E ArXiv Only Packet",
                "source_config_ids": ["src-arxiv-001"],
                "pipeline_ids": ["e2e-pipe-arxiv"],
            },
        )
        assert resp.status_code == 201
        self.PKT_IDS.append("e2e-pkt-arxiv-only")

    def test_17_resolve_multi_source_packet(self, client: TestClient) -> None:
        """Resolve the multi-source packet — should aggregate data."""
        resp = client.post(f"{PREFIX}/packets/e2e-pkt-multi/resolve")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["status"] == "resolved"

        resolved = body["resolved_data"]
        assert resolved["sources_configured"] == 2
        assert resolved["pipelines_configured"] == 2
        assert resolved["estimated_records"] > 0

        sources = resolved["sources"]
        assert len(sources) == 2
        source_ids = {s["source_config_id"] for s in sources}
        assert "src-arxiv-001" in source_ids
        assert "src-github-001" in source_ids
        assert all(s["status"] == "completed" for s in sources)

        pipelines = resolved["pipelines"]
        assert len(pipelines) == 2
        # After verification, pipeline status may be "verified" rather than "completed"
        valid_statuses = {"completed", "verified"}
        for p in pipelines:
            assert p["status"] in valid_statuses, (
                f"Expected status in {valid_statuses}, got '{p['status']}'"
            )

    def test_18_resolve_arxiv_packet(self, client: TestClient) -> None:
        """Resolve the ArXiv-only packet."""
        resp = client.post(f"{PREFIX}/packets/e2e-pkt-arxiv-only/resolve")
        assert resp.status_code == 200
        assert resp.json()["resolved_data"]["sources_configured"] == 1

    def test_19_test_all_multi_packet(self, client: TestClient) -> None:
        """Run test-all on multi-source packet — all should pass."""
        resp = client.post(f"{PREFIX}/packets/e2e-pkt-multi/test-all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["all_passed"] is True
        assert len(body["source_tests"]) == 2
        assert len(body["pipeline_tests"]) == 2
        assert all(st["passed"] is True for st in body["source_tests"])
        assert all(pt["passed"] is True for pt in body["pipeline_tests"])
        assert body["passed_sources"] == body["total_sources"]
        assert body["passed_pipelines"] == body["total_pipelines"]

    def test_20_verify_multi_packet(self, client: TestClient) -> None:
        """Verify the multi-source packet."""
        resp = client.post(f"{PREFIX}/packets/e2e-pkt-multi/verify")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "verified"
        assert resp.json()["data"]["verified_by"] == "system"

    def test_21_verify_arxiv_packet(self, client: TestClient) -> None:
        """Verify the ArXiv-only packet."""
        resp = client.post(f"{PREFIX}/packets/e2e-pkt-arxiv-only/verify")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "verified"

    def test_22_get_packet_data(self, client: TestClient) -> None:
        """Get resolved data for the verified multi-source packet."""
        resp = client.get(f"{PREFIX}/packets/e2e-pkt-multi/data")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["filtered"] is False
        data = body["data"]
        assert data["packet_id"] == "e2e-pkt-multi"
        assert data["sources_configured"] == 2

    def test_23_get_filtered_packet_data(self, client: TestClient) -> None:
        """Get packet data with a text filter."""
        resp = client.get(f"{PREFIX}/packets/e2e-pkt-multi/data?filter=test")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Phase 4: Project Lifecycle
# ═══════════════════════════════════════════════════════════════════


class TestProjectLifecycle:
    """Create, verify, build data object, and attach projects."""

    def test_24_create_project(self, client: TestClient) -> None:
        """Create a project using the verified multi-source packet."""
        resp = client.post(
            f"{PREFIX}/projects",
            json={
                "id": "e2e-proj-pipeline",
                "name": "E2E Pipeline Test Project",
                "description": "Project created to test the full ingestion pipeline E2E flow",
                "packet_ids": ["e2e-pkt-multi", "e2e-pkt-arxiv-only"],
                "tags": ["e2e-test", "pipeline"],
            },
        )
        assert resp.status_code == 201
        d = resp.json()["data"]
        assert d["id"] == "e2e-proj-pipeline"
        assert d["name"] == "E2E Pipeline Test Project"
        assert d["status"] == "draft"
        assert len(d["packet_ids"]) == 2
        assert d["attached_agent_id"] is None
        assert "data_object_schema" in d
        assert "methods" in d["data_object_schema"]

    def test_25_test_all_project(self, client: TestClient) -> None:
        """Run test-all on the project — all packets should pass."""
        resp = client.post(f"{PREFIX}/projects/e2e-proj-pipeline/test-all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["all_passed"] is True
        assert body["packets_tested"] == 2
        assert len(body["packet_results"]) == 2
        assert all(pr["all_passed"] is True for pr in body["packet_results"])
        assert body["passed_sources"] == body["total_sources"]
        assert body["passed_pipelines"] == body["total_pipelines"]

    def test_26_verify_project(self, client: TestClient) -> None:
        """Verify the project."""
        resp = client.post(f"{PREFIX}/projects/e2e-proj-pipeline/verify")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "verified"
        assert resp.json()["data"]["verified_at"] is not None

    def test_27_build_data_object(self, client: TestClient) -> None:
        """Build the data object for the verified project."""
        resp = client.post(f"{PREFIX}/projects/e2e-proj-pipeline/build-data-object")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

        data_object = body["data_object"]
        assert data_object["project"]["name"] == "E2E Pipeline Test Project"
        assert "packets" in data_object
        assert "sources" in data_object
        assert "methods" in data_object
        assert "statistics" in data_object

        # Check packets
        assert len(data_object["packets"]) == 2
        pkt_names = {p["name"] for p in data_object["packets"]}
        assert "E2E Multi-Source Packet" in pkt_names
        assert "E2E ArXiv Only Packet" in pkt_names

        # Check sources
        assert len(data_object["sources"]) >= 2
        src_type_ids = {s["type_id"] for s in data_object["sources"]}
        assert "arxiv_api" in src_type_ids

        # Check methods
        methods = data_object["methods"]
        assert "search_sources" in methods
        assert "get_packet" in methods
        assert "get_verified_sources" in methods
        assert "get_project_summary" in methods
        assert "test_connection" in methods

        # Check statistics
        stats = data_object["statistics"]
        assert stats["total_packets"] >= 2
        assert stats["verified_packets"] >= 2
        assert stats["total_sources"] >= 2

    def test_28_get_data_object_schema(self, client: TestClient) -> None:
        """Get the data object schema."""
        resp = client.get(f"{PREFIX}/projects/e2e-proj-pipeline/data-object")
        assert resp.status_code == 200
        schema = resp.json()["data_object_schema"]
        assert "type" in schema
        assert "methods" in schema

    def test_29_attach_to_agent(self, client: TestClient) -> None:
        """Attach the verified project to an agent."""
        resp = client.post(
            f"{PREFIX}/projects/e2e-proj-pipeline/attach",
            json={"agent_id": "e2e-agent-researcher-002"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["attached_agent_id"] == "e2e-agent-researcher-002"
        assert "attached to agent" in resp.json()["message"]

        # Verify persistence
        get_resp = client.get(f"{PREFIX}/projects/e2e-proj-pipeline")
        assert get_resp.json()["data"]["attached_agent_id"] == "e2e-agent-researcher-002"

    def test_30_detach_from_agent(self, client: TestClient) -> None:
        """Detach the project from its agent."""
        resp = client.post(f"{PREFIX}/projects/e2e-proj-pipeline/detach")
        assert resp.status_code == 200
        assert resp.json()["data"]["attached_agent_id"] is None
        assert "detached" in resp.json()["message"]

        # Verify persistence
        get_resp = client.get(f"{PREFIX}/projects/e2e-proj-pipeline")
        assert get_resp.json()["data"]["attached_agent_id"] is None

    def test_31_list_pipelines_with_filter(self, client: TestClient) -> None:
        """List pipelines filtered by source config."""
        resp = client.get(f"{PREFIX}/pipelines?source_config_id=src-arxiv-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert all(p["source_config_id"] == "src-arxiv-001" for p in body["data"])

    def test_32_list_sources_with_filter(self, client: TestClient) -> None:
        """List sources filtered by source type."""
        resp = client.get(f"{PREFIX}/sources?source_type_id=arxiv_api")
        assert resp.status_code == 200
        assert all(s["source_type_id"] == "arxiv_api" for s in resp.json()["data"])


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Cleanup — Remove all E2E test resources
# ═══════════════════════════════════════════════════════════════════


class TestCleanup:
    """Remove all resources created during E2E testing."""

    def test_33_cleanup_project(self, client: TestClient) -> None:
        """Delete the E2E project."""
        resp = client.delete(f"{PREFIX}/projects/e2e-proj-pipeline")
        assert resp.status_code == 200
        get_resp = client.get(f"{PREFIX}/projects/e2e-proj-pipeline")
        assert get_resp.status_code == 404

    def test_34_cleanup_packets(self, client: TestClient) -> None:
        """Delete E2E test packets."""
        for pkt_id in ["e2e-pkt-multi", "e2e-pkt-arxiv-only"]:
            resp = client.delete(f"{PREFIX}/packets/{pkt_id}")
            assert resp.status_code == 200
            get_resp = client.get(f"{PREFIX}/packets/{pkt_id}")
            assert get_resp.status_code == 404

    def test_35_cleanup_pipelines(self, client: TestClient) -> None:
        """Delete E2E test pipelines."""
        for pipe_id in ["e2e-pipe-arxiv", "e2e-pipe-github"]:
            resp = client.delete(f"{PREFIX}/pipelines/{pipe_id}")
            assert resp.status_code == 200
            get_resp = client.get(f"{PREFIX}/pipelines/{pipe_id}")
            assert get_resp.status_code == 404

    def test_36_verify_clean_state(self, client: TestClient) -> None:
        """Verify all E2E resources are cleaned up."""
        for resource_id in [
            ("projects", "e2e-proj-pipeline"),
            ("packets", "e2e-pkt-multi"),
            ("packets", "e2e-pkt-arxiv-only"),
            ("pipelines", "e2e-pipe-arxiv"),
            ("pipelines", "e2e-pipe-github"),
        ]:
            resp = client.get(f"{PREFIX}/{resource_id[0]}/{resource_id[1]}")
            assert resp.status_code == 404, (
                f"Resource still exists: {resource_id[0]}/{resource_id[1]}"
            )
