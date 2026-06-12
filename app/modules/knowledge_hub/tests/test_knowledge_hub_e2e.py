"""
E2E tests for Knowledge Sources Hub API.

Tests all CRUD endpoints, execute/verify flows, and the agent data object
for the AI Impact Research project. Uses SQLite in-memory database configured
in conftest.py with seed data.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python -m pytest app/modules/knowledge_hub/tests/test_knowledge_hub_e2e.py -v
"""

from __future__ import annotations

from typing import Any, Dict, Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


# ═══════════════════════════════════════════════════════════════════
# Sources — Source Types CRUD + Configs CRUD + Execute/Verify
# ═══════════════════════════════════════════════════════════════════


class TestSourceTypes:
    """Tests for /knowledge-hub/source-types endpoints."""

    def test_list_source_types(self, client: TestClient) -> None:
        """GET /knowledge-hub/source-types returns all seed source types."""
        response = client.get("/api/v1/knowledge-hub/source-types")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total"] == 8
        assert len(body["data"]) == 8

    def test_list_source_types_filtered_by_category(
        self, client: TestClient
    ) -> None:
        """GET with ?category=api returns only API-based source types."""
        response = client.get(
            "/api/v1/knowledge-hub/source-types?category=api"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert all(st["category"] == "api" for st in body["data"])

    def test_get_source_type(self, client: TestClient) -> None:
        """GET /knowledge-hub/source-types/{id} returns the record."""
        response = client.get(
            "/api/v1/knowledge-hub/source-types/arxiv_api"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["id"] == "arxiv_api"
        assert body["data"]["name"] == "ArXiv API"
        assert body["data"]["category"] == "api"
        assert "config_schema" in body["data"]

    def test_get_source_type_not_found(self, client: TestClient) -> None:
        """GET for a non-existent ID returns 404."""
        response = client.get(
            "/api/v1/knowledge-hub/source-types/nonexistent"
        )
        assert response.status_code == 404

    def test_create_source_type(self, client: TestClient) -> None:
        """POST creates a new source type and returns it with 201."""
        response = client.post(
            "/api/v1/knowledge-hub/source-types",
            json={
                "id": "test_api",
                "name": "Test API",
                "description": "A test source type",
                "icon": "🧪",
                "category": "api",
                "config_schema": {"type": "object", "properties": {}},
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["id"] == "test_api"
        assert body["data"]["name"] == "Test API"

        # Cleanup
        client.delete("/api/v1/knowledge-hub/source-types/test_api")

    def test_update_source_type(self, client: TestClient) -> None:
        """PUT updates name and description."""
        client.post(
            "/api/v1/knowledge-hub/source-types",
            json={
                "id": "updatable_type",
                "name": "Original Name",
                "category": "api",
            },
        )
        response = client.put(
            "/api/v1/knowledge-hub/source-types/updatable_type",
            json={"name": "Updated Name", "description": "Updated desc"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["name"] == "Updated Name"
        assert body["data"]["description"] == "Updated desc"
        client.delete("/api/v1/knowledge-hub/source-types/updatable_type")

    def test_delete_source_type(self, client: TestClient) -> None:
        """DELETE removes the source type and returns success."""
        client.post(
            "/api/v1/knowledge-hub/source-types",
            json={"id": "deletable_type", "name": "To Delete", "category": "api"},
        )
        response = client.delete(
            "/api/v1/knowledge-hub/source-types/deletable_type"
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        get_resp = client.get(
            "/api/v1/knowledge-hub/source-types/deletable_type"
        )
        assert get_resp.status_code == 404

    def test_delete_source_type_not_found(self, client: TestClient) -> None:
        """DELETE on non-existent ID returns 404."""
        response = client.delete(
            "/api/v1/knowledge-hub/source-types/nonexistent"
        )
        assert response.status_code == 404


class TestSourceConfigs:
    """Tests for /knowledge-hub/sources endpoints."""

    def test_list_source_configs(self, client: TestClient) -> None:
        """GET returns all seed source configs."""
        response = client.get("/api/v1/knowledge-hub/sources")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total"] >= 6
        assert len(body["data"]) >= 6

    def test_list_source_configs_filtered_by_status(
        self, client: TestClient
    ) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/sources?status=verified"
        )
        assert response.status_code == 200
        body = response.json()
        assert all(c["status"] == "verified" for c in body["data"])

    def test_list_source_configs_filtered_by_source_type(
        self, client: TestClient
    ) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/sources?source_type_id=arxiv_api"
        )
        assert response.status_code == 200
        body = response.json()
        assert all(c["source_type_id"] == "arxiv_api" for c in body["data"])

    def test_get_source_config(self, client: TestClient) -> None:
        """GET /sources/{id} returns the config record."""
        response = client.get(
            "/api/v1/knowledge-hub/sources/src-arxiv-001"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["id"] == "src-arxiv-001"
        assert body["data"]["name"] == "ArXiv AI Papers Feed"
        assert body["data"]["source_type_id"] == "arxiv_api"
        assert body["data"]["status"] == "verified"
        assert "config" in body["data"]

    def test_get_source_config_not_found(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/sources/nonexistent-src"
        )
        assert response.status_code == 404

    def test_create_and_delete_source_config(
        self, client: TestClient
    ) -> None:
        create_resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "id": "src-test-001",
                "source_type_id": "arxiv_api",
                "name": "Test Source Config",
                "description": "A temporary test config",
                "config": {"categories": ["cs.AI"], "max_results": 10},
                "tags": ["test"],
            },
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["data"]["name"] == "Test Source Config"

        get_resp = client.get(
            "/api/v1/knowledge-hub/sources/src-test-001"
        )
        assert get_resp.status_code == 200

        del_resp = client.delete(
            "/api/v1/knowledge-hub/sources/src-test-001"
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        get_resp2 = client.get(
            "/api/v1/knowledge-hub/sources/src-test-001"
        )
        assert get_resp2.status_code == 404

    def test_update_source_config(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "id": "src-update-001",
                "source_type_id": "arxiv_api",
                "name": "Original",
                "config": {},
            },
        )
        response = client.put(
            "/api/v1/knowledge-hub/sources/src-update-001",
            json={"name": "Updated Source", "description": "Updated description"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Updated Source"
        client.delete("/api/v1/knowledge-hub/sources/src-update-001")

    def test_execute_source(self, client: TestClient) -> None:
        """POST /sources/{id}/execute returns sample data."""
        response = client.post(
            "/api/v1/knowledge-hub/sources/src-arxiv-001/execute"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "completed"
        assert "data" in body
        assert body["record_count"] > 0

    def test_execute_source_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/sources/fake-id/execute"
        )
        assert response.status_code == 404

    def test_verify_source(self, client: TestClient) -> None:
        """POST /sources/{id}/verify marks a draft source as verified."""
        client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "id": "src-to-verify",
                "source_type_id": "github_api",
                "name": "To Verify",
                "config": {"search_query": "test", "min_stars": 10},
            },
        )
        response = client.post(
            "/api/v1/knowledge-hub/sources/src-to-verify/verify"
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "verified"
        client.delete("/api/v1/knowledge-hub/sources/src-to-verify")

    def test_preview_source(self, client: TestClient) -> None:
        """GET /sources/{id}/preview returns sample data records."""
        response = client.get(
            "/api/v1/knowledge-hub/sources/src-arxiv-001/preview?limit=5"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "preview" in body
        assert len(body["preview"]) <= 5


# ═══════════════════════════════════════════════════════════════════
# Ingestion Pipelines — CRUD + Validate + Execute + Verify
# ═══════════════════════════════════════════════════════════════════


class TestPipelines:
    """Tests for /knowledge-hub/pipelines endpoints."""

    def test_list_pipelines(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge-hub/pipelines")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total"] == 5
        names = [p["name"] for p in body["data"]]
        assert "ArXiv Papers Collector" in names
        assert "Tech News Aggregator" in names

    def test_list_pipelines_filtered_by_status(
        self, client: TestClient
    ) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/pipelines?status=verified"
        )
        assert response.status_code == 200
        assert all(p["status"] == "verified" for p in response.json()["data"])

    def test_get_pipeline(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/pipelines/pipe-arxiv-001"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["name"] == "ArXiv Papers Collector"

    def test_get_pipeline_not_found(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/pipelines/nonexistent-pipe"
        )
        assert response.status_code == 404

    def test_create_pipeline(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "name": "Test Pipeline",
                "source_config_id": "src-arxiv-001",
                "pipeline_definition": {
                    "version": "1.0",
                    "type": "extract_transform",
                    "steps": [{"name": "fetch", "operation": "api_query", "config": {}}],
                    "output": {"format": "structured_records"},
                },
            },
        )
        assert response.status_code == 201
        pipe_id = response.json()["data"]["id"]
        client.delete(f"/api/v1/knowledge-hub/pipelines/{pipe_id}")

    def test_validate_pipeline(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/pipelines/validate",
            json={
                "pipeline_definition": {
                    "version": "1.0",
                    "type": "extract_transform",
                    "steps": [{"name": "fetch", "operation": "api_query", "config": {}}],
                    "output": {"format": "structured_records"},
                }
            },
        )
        assert response.status_code == 200
        assert response.json()["data"]["valid"] is True

    def test_validate_invalid_pipeline(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/pipelines/validate",
            json={"pipeline_definition": {"version": "1.0"}},
        )
        assert response.status_code == 200
        assert response.json()["data"]["valid"] is False
        assert len(response.json()["data"]["errors"]) > 0

    def test_execute_pipeline(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/pipelines/pipe-arxiv-001/execute"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "completed"
        assert len(body["steps"]) > 0

    def test_execute_pipeline_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/pipelines/fake-pipe/execute"
        )
        assert response.status_code == 404

    def test_verify_pipeline(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "name": "Verify Test Pipe",
                "source_config_id": "src-github-001",
                "pipeline_definition": {
                    "version": "1.0",
                    "type": "extract",
                    "steps": [{"name": "search", "operation": "api_query", "config": {}}],
                    "output": {"format": "structured_records"},
                },
            },
        )
        pipe_id = create_resp.json()["data"]["id"]
        response = client.post(
            f"/api/v1/knowledge-hub/pipelines/{pipe_id}/verify"
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "verified"
        client.delete(f"/api/v1/knowledge-hub/pipelines/{pipe_id}")


# ═══════════════════════════════════════════════════════════════════
# Data Packets — CRUD + Resolve + Test All + Verify + Data
# ═══════════════════════════════════════════════════════════════════


class TestPackets:
    """Tests for /knowledge-hub/packets endpoints."""

    def test_list_packets(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge-hub/packets")
        assert response.status_code == 200
        assert response.json()["total"] == 6

    def test_list_packets_filtered_by_status(
        self, client: TestClient
    ) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/packets?status=verified"
        )
        assert response.status_code == 200
        assert all(p["status"] == "verified" for p in response.json()["data"])

    def test_get_packet(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/packets/pkt-academic-001"
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Academic Research"

    def test_get_packet_not_found(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/packets/nonexistent-pkt"
        )
        assert response.status_code == 404

    def test_create_packet(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/packets",
            json={
                "name": "Test Packet",
                "source_config_ids": ["src-arxiv-001"],
                "pipeline_ids": ["pipe-arxiv-001"],
                "tags": ["test"],
            },
        )
        assert response.status_code == 201
        pkt_id = response.json()["data"]["id"]
        client.delete(f"/api/v1/knowledge-hub/packets/{pkt_id}")

    def test_resolve_packet(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/packets/pkt-academic-001/resolve"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["status"] == "resolved"
        assert body["resolved_data"]["sources_configured"] > 0

    def test_resolve_packet_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/packets/fake-pkt/resolve"
        )
        assert response.status_code == 404

    def test_get_packet_data(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/packets/pkt-news-001/data"
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "data" in response.json()

    def test_test_all_packet(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/packets/pkt-academic-001/test-all"
        )
        assert response.status_code == 200
        body = response.json()
        assert "all_passed" in body
        assert "source_tests" in body
        assert body["total_sources"] > 0

    def test_test_all_packet_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/packets/fake-pkt/test-all"
        )
        assert response.status_code == 404

    def test_verify_packet(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={
                "name": "Verifiable Packet",
                "source_config_ids": ["src-arxiv-001"],
                "pipeline_ids": ["pipe-arxiv-001"],
            },
        )
        pkt_id = create_resp.json()["data"]["id"]
        response = client.post(
            f"/api/v1/knowledge-hub/packets/{pkt_id}/verify"
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "verified"
        client.delete(f"/api/v1/knowledge-hub/packets/{pkt_id}")

    def test_verify_packet_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/packets/fake-pkt/verify"
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Knowledge Projects — CRUD + Test All + Verify + Attach/Detach +
#                     Build Data Object + Get Data Object
# ═══════════════════════════════════════════════════════════════════


class TestProjects:
    """Tests for /knowledge-hub/projects endpoints."""

    def test_list_projects(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge-hub/projects")
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["data"][0]["name"] == "AI Impact Research"

    def test_get_project(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001"
        )
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["name"] == "AI Impact Research"
        assert len(body["packet_ids"]) == 6
        assert body["status"] == "draft"
        assert body["attached_agent_id"] is None

    def test_get_project_not_found(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/projects/fake-proj"
        )
        assert response.status_code == 404

    def test_create_project(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/projects",
            json={
                "name": "Test Project",
                "description": "A test project",
                "packet_ids": ["pkt-academic-001", "pkt-news-001"],
                "tags": ["test"],
            },
        )
        assert response.status_code == 201
        proj_id = response.json()["data"]["id"]
        client.delete(f"/api/v1/knowledge-hub/projects/{proj_id}")

    def test_test_all_project(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/test-all"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "all_passed" in body
        assert body["packets_tested"] > 0
        assert body["total_sources"] > 0
        assert body["total_pipelines"] > 0

    def test_verify_project(self, client: TestClient) -> None:
        """Verify the seed project (mutates state)."""
        response = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/verify"
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "verified"

    def test_attach_project_to_agent(self, client: TestClient) -> None:
        """POST /projects/{id}/attach links verified project to an agent."""
        client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/verify"
        )
        response = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/attach",
            json={"agent_id": "agent-ai-researcher-001"},
        )
        assert response.status_code == 200
        assert response.json()["data"][
            "attached_agent_id"
        ] == "agent-ai-researcher-001"
        assert "attached to agent" in response.json()["message"]

    def test_detach_project_from_agent(self, client: TestClient) -> None:
        client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/verify"
        )
        client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/attach",
            json={"agent_id": "agent-test"},
        )
        response = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/detach"
        )
        assert response.status_code == 200
        assert response.json()["data"]["attached_agent_id"] is None

    def test_attach_unverified_project(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={"name": "Unverified Project"},
        )
        proj_id = create_resp.json()["data"]["id"]
        response = client.post(
            f"/api/v1/knowledge-hub/projects/{proj_id}/attach",
            json={"agent_id": "agent-test"},
        )
        assert response.status_code == 400
        client.delete(f"/api/v1/knowledge-hub/projects/{proj_id}")

    def test_detach_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/projects/fake-proj/detach"
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Agent Data Object — Build + Get + Verify Structure
# ═══════════════════════════════════════════════════════════════════


class TestDataObject:
    """Tests for the agent data object endpoints and structure."""

    def test_build_data_object(self, client: TestClient) -> None:
        """POST /projects/{id}/build-data-object returns structured data."""
        response = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/build-data-object"
        )
        assert response.status_code == 200
        data_object = response.json()["data_object"]
        assert data_object["project"]["name"] == "AI Impact Research"
        assert "packets" in data_object
        assert "sources" in data_object
        assert "methods" in data_object
        assert "statistics" in data_object
        assert len(data_object["packets"]) > 0

        methods = data_object["methods"]
        assert "search_sources" in methods
        assert "get_packet" in methods
        assert "get_verified_sources" in methods
        assert "get_project_summary" in methods
        assert "test_connection" in methods

        stats = data_object["statistics"]
        assert stats["total_packets"] > 0
        assert stats["total_sources"] > 0

    def test_get_data_object(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/data-object"
        )
        assert response.status_code == 200
        assert "data_object_schema" in response.json()

    def test_data_object_contains_all_source_types(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/build-data-object"
        )
        sources = response.json()["data_object"]["sources"]
        type_ids = {s["type_id"] for s in sources}
        assert "arxiv_api" in type_ids
        assert "web_scraper" in type_ids
        assert "github_api" in type_ids
        assert "reddit_api" in type_ids

    def test_data_object_statistics_are_correct(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001/build-data-object"
        )
        stats = response.json()["data_object"]["statistics"]
        assert stats["total_packets"] == 6
        assert stats["total_sources"] >= 6
        assert stats["verified_packets"] >= 3  # Some may be verified by earlier tests
        assert stats["verified_sources"] >= 5

    def test_build_data_object_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge-hub/projects/fake-proj/build-data-object"
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Full E2E Workflow — Sources → Pipelines → Packets → Project → Agent
# ═══════════════════════════════════════════════════════════════════


class TestFullWorkflow:
    """End-to-end workflow: create source → pipeline → packet → project → verify → attach to agent."""

    def test_full_create_verify_attach_workflow(
        self, client: TestClient
    ) -> None:
        """Complete 15-step E2E workflow from source to agent attachment."""
        # Step 1: Create a source config
        src_resp = client.post(
            "/api/v1/knowledge-hub/sources",
            json={
                "id": "e2e-source-001",
                "source_type_id": "arxiv_api",
                "name": "E2E Test Source",
                "config": {"categories": ["cs.AI"], "max_results": 50},
            },
        )
        assert src_resp.status_code == 201

        # Step 2: Execute the source
        assert client.post(
            "/api/v1/knowledge-hub/sources/e2e-source-001/execute"
        ).status_code == 200

        # Step 3: Verify the source
        assert client.post(
            "/api/v1/knowledge-hub/sources/e2e-source-001/verify"
        ).json()["data"]["status"] == "verified"

        # Step 4: Create a pipeline
        pipe_resp = client.post(
            "/api/v1/knowledge-hub/pipelines",
            json={
                "name": "E2E Test Pipeline",
                "source_config_id": "e2e-source-001",
                "pipeline_definition": {
                    "version": "1.0",
                    "type": "extract_transform",
                    "steps": [{"name": "fetch", "operation": "api_query", "config": {}}],
                    "output": {"format": "structured_records"},
                },
            },
        )
        assert pipe_resp.status_code == 201
        pipe_id = pipe_resp.json()["data"]["id"]

        # Step 5-6: Execute and verify the pipeline
        assert client.post(
            f"/api/v1/knowledge-hub/pipelines/{pipe_id}/execute"
        ).json()["success"] is True
        assert client.post(
            f"/api/v1/knowledge-hub/pipelines/{pipe_id}/verify"
        ).json()["data"]["status"] == "verified"

        # Step 7: Create a packet with the source and pipeline
        pkt_resp = client.post(
            "/api/v1/knowledge-hub/packets",
            json={
                "name": "E2E Test Packet",
                "source_config_ids": ["e2e-source-001"],
                "pipeline_ids": [pipe_id],
            },
        )
        assert pkt_resp.status_code == 201
        pkt_id = pkt_resp.json()["data"]["id"]

        # Step 8-9: Test-all and verify the packet
        assert client.post(
            f"/api/v1/knowledge-hub/packets/{pkt_id}/test-all"
        ).json()["all_passed"] is True
        assert client.post(
            f"/api/v1/knowledge-hub/packets/{pkt_id}/verify"
        ).json()["data"]["status"] == "verified"

        # Step 10-12: Create project, test-all, verify
        proj_resp = client.post(
            "/api/v1/knowledge-hub/projects",
            json={"name": "E2E Test Project", "packet_ids": [pkt_id]},
        )
        assert proj_resp.status_code == 201
        proj_id = proj_resp.json()["data"]["id"]

        assert client.post(
            f"/api/v1/knowledge-hub/projects/{proj_id}/test-all"
        ).json()["all_passed"] is True
        assert client.post(
            f"/api/v1/knowledge-hub/projects/{proj_id}/verify"
        ).json()["data"]["status"] == "verified"

        # Step 13: Build the data object
        assert client.post(
            f"/api/v1/knowledge-hub/projects/{proj_id}/build-data-object"
        ).status_code == 200

        # Step 14: Attach to agent
        assert client.post(
            f"/api/v1/knowledge-hub/projects/{proj_id}/attach",
            json={"agent_id": "e2e-agent-001"},
        ).json()["data"]["attached_agent_id"] == "e2e-agent-001"

        # Step 15: Detach from agent
        assert client.post(
            f"/api/v1/knowledge-hub/projects/{proj_id}/detach"
        ).json()["data"]["attached_agent_id"] is None

        # Cleanup
        client.delete(f"/api/v1/knowledge-hub/projects/{proj_id}")
        client.delete(f"/api/v1/knowledge-hub/packets/{pkt_id}")
        client.delete(f"/api/v1/knowledge-hub/pipelines/{pipe_id}")
        client.delete("/api/v1/knowledge-hub/sources/e2e-source-001")


# ═══════════════════════════════════════════════════════════════════
# AIImpactDataObject Unit Tests — Agent-facing interface
# ═══════════════════════════════════════════════════════════════════


class TestAIImpactDataObject:
    """Tests for the AIImpactDataObject agent-facing interface."""

    def test_instantiate_data_object(self, db_session: Session) -> None:
        """AIImpactDataObject loads the AI Impact Research project."""
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        assert data_obj._project is not None
        assert data_obj._project.name == "AI Impact Research"

    def test_get_project_summary(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        summary = data_obj.get_project_summary()
        assert "project" in summary
        assert "packets_available" in summary
        assert len(summary["packets_available"]) > 0
        assert "available_methods" in summary

    def test_search_sources(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        results = data_obj.search_sources(query="AI")
        assert isinstance(results, list)

    def test_get_packet_by_name(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        packet = data_obj.get_packet("Academic Research")
        assert packet is not None
        assert packet["name"] == "Academic Research"
        assert packet["verified"] is True

    def test_get_packet_not_found(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        assert data_obj.get_packet("NonExistent Packet") is None

    def test_get_verified_sources(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        sources = data_obj.get_verified_sources()
        assert len(sources) > 0
        assert all(s["status"] == "verified" for s in sources)

    def test_query_academic_papers(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        papers = data_obj.query_academic_papers(limit=5)
        assert isinstance(papers, list)

    def test_query_news(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        articles = data_obj.query_news(limit=5)
        assert isinstance(articles, list)

    def test_test_connection(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        result = data_obj.test_connection("src-arxiv-001")
        assert result["success"] is True
        assert result["source_config_id"] == "src-arxiv-001"
        assert "sample_data" in result

    def test_get_methods_schema(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        schema = data_obj.get_methods_schema()
        assert "search_sources" in schema
        assert "get_packet" in schema
        assert "test_connection" in schema

    def test_to_dict(self, db_session: Session) -> None:
        from common_lib.modules.knowledge_hub.agent_data_object import (
            AIImpactDataObject,
        )

        data_obj = AIImpactDataObject(db_session)
        serialized = data_obj.to_dict()
        assert serialized["project"]["id"] == "proj-ai-impact-001"
        assert "packets" in serialized
        assert "methods" in serialized


# ═══════════════════════════════════════════════════════════════════
# Routing Integrity
# ═══════════════════════════════════════════════════════════════════


class TestRoutingIntegrity:
    """Verify all routes are mounted at expected paths."""

    def test_all_knowledge_hub_routes_registered(
        self, client: TestClient
    ) -> None:
        """OpenAPI schema includes all knowledge-hub endpoints."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        hub_paths = {path for path in paths if "knowledge-hub" in path}

        expected_suffixes = [
            "/source-types",
            "/sources/",
            "/pipelines/",
            "/packets/",
            "/projects/",
        ]
        for suffix in expected_suffixes:
            matches = [p for p in hub_paths if suffix in p]
            assert matches, f"No route found containing '{suffix}'"

        assert len(hub_paths) >= 26, (
            f"Expected at least 26 knowledge-hub paths, got {len(hub_paths)}"
        )
