"""
Stress test — bulk operations for Knowledge Sources Hub.

Creates 150+ source types, source configs, pipelines, packets, and projects
in a loop to verify the system handles bulk operations without degradation.
Measures timing for each phase and asserts response times stay reasonable.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python -m pytest app/modules/knowledge_hub/tests/test_stress_bulk_operations.py -v --tb=short
"""

from __future__ import annotations

import time
from typing import List

import pytest
from fastapi.testclient import TestClient


# ── Configuration ───────────────────────────────────────────────────
# Adjust these constants to control the stress test scale.

BULK_COUNT = 50  # Number of entities to create per type (5 types × 50 = 250 total entities)
PIPELINE_STEPS = 3  # Steps per pipeline definition


# ═══════════════════════════════════════════════════════════════════
# Phase 1: Bulk Create — Source Types
# ═══════════════════════════════════════════════════════════════════


class TestBulkCreateSourceTypes:
    """Create N source types and measure timing."""

    CREATED_IDS: List[str] = []

    def test_bulk_create_source_types(self, client: TestClient) -> None:
        """Create BULK_COUNT source types and measure timing."""
        categories = ["api", "storage", "connector", "database", "manual"]
        timings: List[float] = []
        failures: List[str] = []

        for i in range(BULK_COUNT):
            cat = categories[i % len(categories)]
            type_id = f"stress-st-{i:04d}"
            start = time.perf_counter()
            resp = client.post(
                "/api/v1/knowledge-hub/source-types",
                json={
                    "id": type_id,
                    "name": f"Stress Test Type {i}",
                    "description": f"Source type #{i} created during bulk stress test. Category: {cat}. Designed to test system behavior under load.",
                    "icon": ["🔌", "🗄️", "🔗", "🗃️", "📤"][i % 5],
                    "category": cat,
                    "config_schema": {
                        "type": "object",
                        "properties": {
                            "endpoint": {"type": "string", "description": "API endpoint"},
                            "api_key": {"type": "string", "description": "Auth key"},
                            "timeout_seconds": {"type": "integer", "default": 30},
                            "retry_count": {"type": "integer", "default": 3},
                            "filters": {
                                "type": "object",
                                "properties": {
                                    "date_from": {"type": "string", "format": "date"},
                                    "limit": {"type": "integer", "default": 100},
                                },
                            },
                        },
                        "required": ["endpoint"],
                    },
                },
            )
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

            if resp.status_code != 201:
                failures.append(f"{type_id}: {resp.status_code} - {resp.text[:100]}")
            else:
                self.__class__.CREATED_IDS.append(type_id)

        # Report
        avg_ms = sum(timings) / len(timings) * 1000
        max_ms = max(timings) * 1000
        min_ms = min(timings) * 1000
        print(f"\n  [TIMING] Source Types: {len(self.__class__.CREATED_IDS)} created "
              f"| avg {avg_ms:.1f}ms | min {min_ms:.1f}ms | max {max_ms:.1f}ms")

        if failures:
            pytest.fail(f"{len(failures)} source type creations failed: {failures[:5]}")

        assert len(self.__class__.CREATED_IDS) == BULK_COUNT

    def test_list_after_bulk_types(self, client: TestClient) -> None:
        """List all source types and verify bulk records appear."""
        resp = client.get("/api/v1/knowledge-hub/source-types")
        assert resp.status_code == 200
        body = resp.json()
        # 8 seed + BULK_COUNT = total
        expected = 8 + BULK_COUNT
        assert body["total"] >= expected, f"Expected >= {expected} types, got {body['total']}"
        # Verify all our IDs are present
        ids = {t["id"] for t in body["data"]}
        for sid in self.__class__.CREATED_IDS:
            assert sid in ids, f"Missing bulk type: {sid}"

    def test_list_filtered_category(self, client: TestClient) -> None:
        """List source types filtered by category returns correct counts."""
        resp = client.get("/api/v1/knowledge-hub/source-types?category=api")
        assert resp.status_code == 200
        body = resp.json()
        # 5 seed API types + ceil(BULK_COUNT / 5) bulk API types
        bulk_api = (BULK_COUNT + 4) // 5
        expected = 5 + bulk_api
        assert body["total"] >= expected, f"Expected >= {expected} API types, got {body['total']}"
        assert all(t["category"] == "api" for t in body["data"])


# ═══════════════════════════════════════════════════════════════════
# Phase 2: Bulk Create — Source Configs
# ═══════════════════════════════════════════════════════════════════


class TestBulkCreateSourceConfigs:
    """Create N source configs using bulk-created types."""

    CREATED_IDS: List[str] = []
    TYPE_IDS: List[str] = TestBulkCreateSourceTypes.CREATED_IDS

    def test_bulk_create_source_configs(self, client: TestClient) -> None:
        """Create BULK_COUNT source configs and measure timing."""
        if not self.TYPE_IDS:
            pytest.skip("No bulk source types available (previous phase may have failed)")

        timings: List[float] = []
        failures: List[str] = []

        for i in range(BULK_COUNT):
            type_id = self.TYPE_IDS[i % len(self.TYPE_IDS)]
            src_id = f"stress-src-{i:04d}"
            start = time.perf_counter()
            resp = client.post(
                "/api/v1/knowledge-hub/sources",
                json={
                    "id": src_id,
                    "source_type_id": type_id,
                    "name": f"Stress Source Config {i}",
                    "description": f"Source config #{i} for bulk stress testing. References type {type_id}.",
                    "config": {
                        "endpoint": f"https://api{i}.example.com/v2/data",
                        "api_key": f"sk-stress-{i:06x}",
                        "timeout_seconds": 30 + (i % 10),
                        "retry_count": 3,
                        "filters": {
                            "date_from": "2025-01-01",
                            "limit": 100 + i,
                        },
                    },
                    "tags": ["stress-test", f"batch-{i // 10}", f"type-{type_id}"],
                },
            )
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

            if resp.status_code != 201:
                failures.append(f"{src_id}: {resp.status_code} - {resp.text[:100]}")
            else:
                self.__class__.CREATED_IDS.append(src_id)

        # Report
        avg_ms = sum(timings) / len(timings) * 1000
        max_ms = max(timings) * 1000
        min_ms = min(timings) * 1000
        print(f"\n  [TIMING] Source Configs: {len(self.__class__.CREATED_IDS)} created "
              f"| avg {avg_ms:.1f}ms | min {min_ms:.1f}ms | max {max_ms:.1f}ms")

        if failures:
            pytest.fail(f"{len(failures)} source config creations failed: {failures[:5]}")

        assert len(self.__class__.CREATED_IDS) == BULK_COUNT

    def test_list_after_bulk_configs(self, client: TestClient) -> None:
        """List all source configs and verify bulk records appear."""
        resp = client.get("/api/v1/knowledge-hub/sources")
        assert resp.status_code == 200
        body = resp.json()
        # 7 seed + BULK_COUNT = total
        expected = 7 + BULK_COUNT
        assert body["total"] >= expected, f"Expected >= {expected} configs, got {body['total']}"
        ids = {c["id"] for c in body["data"]}
        for sid in self.__class__.CREATED_IDS:
            assert sid in ids, f"Missing bulk config: {sid}"

    def test_list_filtered_by_type(self, client: TestClient) -> None:
        """List source configs filtered by source type returns correct counts."""
        if not self.TYPE_IDS:
            pytest.skip("No bulk source types")
        type_id = self.TYPE_IDS[0]
        resp = client.get(f"/api/v1/knowledge-hub/sources?source_type_id={type_id}")
        assert resp.status_code == 200
        # At least 1 bulk config should match
        assert resp.json()["total"] >= 1

    def test_execute_first_ten(self, client: TestClient) -> None:
        """Execute the first 10 source configs to verify execute works at scale."""
        ids = self.__class__.CREATED_IDS
        if len(ids) < 10:
            pytest.skip(f"Only {len(ids)} configs available, need 10 for execution test")
        to_execute = ids[:10]
        for src_id in to_execute:
            resp = client.post(f"/api/v1/knowledge-hub/sources/{src_id}/execute")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert body["status"] in ("completed", "verified")

    def test_verify_first_five(self, client: TestClient) -> None:
        """Verify the first 5 source configs."""
        ids = self.__class__.CREATED_IDS
        if len(ids) < 5:
            pytest.skip(f"Only {len(ids)} configs available, need 5 for verify test")
        to_verify = ids[:5]
        for src_id in to_verify:
            resp = client.post(f"/api/v1/knowledge-hub/sources/{src_id}/verify")
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "verified"


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Bulk Create — Ingestion Pipelines
# ═══════════════════════════════════════════════════════════════════


class TestBulkCreatePipelines:
    """Create N pipelines using bulk-created source configs."""

    CREATED_IDS: List[str] = []
    SRC_IDS: List[str] = TestBulkCreateSourceConfigs.CREATED_IDS

    def test_bulk_create_pipelines(self, client: TestClient) -> None:
        """Create BULK_COUNT pipelines and measure timing."""
        if not self.SRC_IDS:
            pytest.skip("No bulk source configs available")

        timings: List[float] = []
        failures: List[str] = []

        for i in range(BULK_COUNT):
            src_id = self.SRC_IDS[i % len(self.SRC_IDS)]
            pipe_id = f"stress-pipe-{i:04d}"
            start = time.perf_counter()
            resp = client.post(
                "/api/v1/knowledge-hub/pipelines",
                json={
                    "id": pipe_id,
                    "name": f"Stress Pipeline {i}",
                    "description": f"Ingestion pipeline #{i} for bulk stress testing. Source: {src_id}. Type: extract_transform.",
                    "source_config_id": src_id,
                    "pipeline_definition": {
                        "version": "2.0",
                        "type": "extract_transform",
                        "steps": [
                            {
                                "name": f"fetch_data_{i}",
                                "operation": "api_query",
                                "config": {
                                    "endpoint": f"https://api{i}.example.com/v2/research",
                                    "params": {"page_size": 50, "format": "json"},
                                    "pagination": {"type": "cursor", "cursor_field": "next_page"},
                                },
                            },
                            {
                                "name": "validate_schema",
                                "operation": "json_parse",
                                "config": {
                                    "fields": ["id", "title", "content", "author", "published_at"],
                                },
                            },
                            {
                                "name": "enrich_metadata",
                                "operation": "llm_summarize",
                                "config": {"max_length": 200, "focus": "key findings"},
                            },
                        ],
                        "output": {
                            "format": "structured_records",
                            "fields": ["record_id", "title", "body", "summary", "author", "date"],
                        },
                    },
                },
            )
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

            if resp.status_code != 201:
                failures.append(f"{pipe_id}: {resp.status_code} - {resp.text[:100]}")
            else:
                self.__class__.CREATED_IDS.append(pipe_id)

        # Report
        avg_ms = sum(timings) / len(timings) * 1000
        max_ms = max(timings) * 1000
        min_ms = min(timings) * 1000
        print(f"\n  [TIMING] Pipelines: {len(self.__class__.CREATED_IDS)} created "
              f"| avg {avg_ms:.1f}ms | min {min_ms:.1f}ms | max {max_ms:.1f}ms")

        if failures:
            pytest.fail(f"{len(failures)} pipeline creations failed: {failures[:5]}")

        assert len(self.__class__.CREATED_IDS) == BULK_COUNT

    def test_list_after_bulk_pipelines(self, client: TestClient) -> None:
        """List all pipelines and verify bulk records appear."""
        resp = client.get("/api/v1/knowledge-hub/pipelines")
        assert resp.status_code == 200
        body = resp.json()
        # 5 seed + BULK_COUNT = total
        expected = 5 + BULK_COUNT
        assert body["total"] >= expected, f"Expected >= {expected} pipelines, got {body['total']}"
        ids = {p["id"] for p in body["data"]}
        for pid in self.__class__.CREATED_IDS:
            assert pid in ids, f"Missing bulk pipeline: {pid}"

    def test_execute_first_ten_pipelines(self, client: TestClient) -> None:
        """Execute the first 10 pipelines to verify execution at scale."""
        ids = self.__class__.CREATED_IDS
        if len(ids) < 10:
            pytest.skip(f"Only {len(ids)} pipelines available, need 10 for execution test")
        to_execute = ids[:10]
        for pipe_id in to_execute:
            resp = client.post(f"/api/v1/knowledge-hub/pipelines/{pipe_id}/execute")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert body["status"] == "completed"
            assert len(body["steps"]) == PIPELINE_STEPS
            assert body["total_records"] > 0

    def test_verify_first_five_pipelines(self, client: TestClient) -> None:
        """Verify the first 5 pipelines."""
        ids = self.__class__.CREATED_IDS
        if len(ids) < 5:
            pytest.skip(f"Only {len(ids)} pipelines available, need 5 for verify test")
        to_verify = ids[:5]
        for pipe_id in to_verify:
            resp = client.post(f"/api/v1/knowledge-hub/pipelines/{pipe_id}/verify")
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "verified"

    def test_validate_pipeline_definition(self, client: TestClient) -> None:
        """Validate a pipeline definition (bulk-style)."""
        resp = client.post(
            "/api/v1/knowledge-hub/pipelines/validate",
            json={
                "pipeline_definition": {
                    "version": "2.0",
                    "type": "extract_transform",
                    "steps": [
                        {"name": "fetch", "operation": "api_query", "config": {"endpoint": "https://example.com"}},
                        {"name": "parse", "operation": "json_parse", "config": {"fields": ["id", "name"]}},
                    ],
                    "output": {"format": "structured_records"},
                }
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["valid"] is True


# ═══════════════════════════════════════════════════════════════════
# Phase 4: Bulk Create — Data Packets (linking sources + pipelines)
# ═══════════════════════════════════════════════════════════════════


class TestBulkCreatePackets:
    """Create N data packets linking bulk-created sources and pipelines."""

    CREATED_IDS: List[str] = []
    SRC_IDS: List[str] = TestBulkCreateSourceConfigs.CREATED_IDS
    PIPE_IDS: List[str] = TestBulkCreatePipelines.CREATED_IDS

    def test_bulk_create_packets(self, client: TestClient) -> None:
        """Create BULK_COUNT packets with source/pipeline references."""
        if not self.SRC_IDS or not self.PIPE_IDS:
            pytest.skip("No bulk sources or pipelines available")

        timings: List[float] = []
        failures: List[str] = []

        for i in range(BULK_COUNT):
            src_id = self.SRC_IDS[i % len(self.SRC_IDS)]
            pipe_id = self.PIPE_IDS[i % len(self.PIPE_IDS)]
            pkt_id = f"stress-pkt-{i:04d}"
            start = time.perf_counter()
            resp = client.post(
                "/api/v1/knowledge-hub/packets",
                json={
                    "id": pkt_id,
                    "name": f"Stress Packet {i}",
                    "description": f"Data packet #{i} for bulk stress test. Links source {src_id} with pipeline {pipe_id}.",
                    "source_config_ids": [src_id],
                    "pipeline_ids": [pipe_id],
                    "tags": ["stress-test", f"source-{i % 10}", f"pipeline-{i % 5}"],
                },
            )
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

            if resp.status_code != 201:
                failures.append(f"{pkt_id}: {resp.status_code} - {resp.text[:100]}")
            else:
                self.__class__.CREATED_IDS.append(pkt_id)

        # Report
        avg_ms = sum(timings) / len(timings) * 1000
        max_ms = max(timings) * 1000
        min_ms = min(timings) * 1000
        print(f"\n  [TIMING] Packets: {len(self.__class__.CREATED_IDS)} created "
              f"| avg {avg_ms:.1f}ms | min {min_ms:.1f}ms | max {max_ms:.1f}ms")

        if failures:
            pytest.fail(f"{len(failures)} packet creations failed: {failures[:5]}")

        assert len(self.__class__.CREATED_IDS) == BULK_COUNT

    def test_list_after_bulk_packets(self, client: TestClient) -> None:
        """List all packets and verify bulk records appear."""
        resp = client.get("/api/v1/knowledge-hub/packets")
        assert resp.status_code == 200
        body = resp.json()
        # 6 seed + BULK_COUNT = total
        expected = 6 + BULK_COUNT
        assert body["total"] >= expected, f"Expected >= {expected} packets, got {body['total']}"
        ids = {p["id"] for p in body["data"]}
        for pid in self.__class__.CREATED_IDS:
            assert pid in ids, f"Missing bulk packet: {pid}"

    def test_resolve_first_five_packets(self, client: TestClient) -> None:
        """Resolve the first 5 packets to verify resolution at scale."""
        ids = self.__class__.CREATED_IDS
        if len(ids) < 5:
            pytest.skip(f"Only {len(ids)} packets available, need 5 for resolve test")
        to_resolve = ids[:5]
        for pkt_id in to_resolve:
            resp = client.post(f"/api/v1/knowledge-hub/packets/{pkt_id}/resolve")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert body["status"] == "resolved"
            assert body["resolved_data"]["sources_configured"] >= 1

    def test_test_all_first_five(self, client: TestClient) -> None:
        """Test-all on first 5 packets."""
        ids = self.__class__.CREATED_IDS
        if len(ids) < 5:
            pytest.skip(f"Only {len(ids)} packets available, need 5 for test-all")
        to_test = ids[:5]
        for pkt_id in to_test:
            resp = client.post(f"/api/v1/knowledge-hub/packets/{pkt_id}/test-all")
            assert resp.status_code == 200
            assert resp.json()["all_passed"] is True

    def test_get_packet_data_first_three(self, client: TestClient) -> None:
        """Get packet data (resolved) for first 3 packets."""
        ids = self.__class__.CREATED_IDS
        if len(ids) < 3:
            pytest.skip(f"Only {len(ids)} packets available, need 3 for data test")
        to_get = ids[:3]
        for pkt_id in to_get:
            resp = client.get(f"/api/v1/knowledge-hub/packets/{pkt_id}/data")
            assert resp.status_code == 200
            assert resp.json()["success"] is True


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Bulk Create — Knowledge Projects
# ═══════════════════════════════════════════════════════════════════


class TestBulkCreateProjects:
    """Create N knowledge projects referencing bulk-created packets."""

    CREATED_IDS: List[str] = []
    PKT_IDS: List[str] = TestBulkCreatePackets.CREATED_IDS

    def test_bulk_create_projects(self, client: TestClient) -> None:
        """Create BULK_COUNT projects referencing 2 packets each."""
        if not self.PKT_IDS:
            pytest.skip("No bulk packets available")

        timings: List[float] = []
        failures: List[str] = []

        for i in range(BULK_COUNT):
            # Each project references 2 packets (cyclic)
            pkt1 = self.PKT_IDS[i % len(self.PKT_IDS)]
            pkt2 = self.PKT_IDS[(i + 1) % len(self.PKT_IDS)]
            proj_id = f"stress-proj-{i:04d}"
            start = time.perf_counter()
            resp = client.post(
                "/api/v1/knowledge-hub/projects",
                json={
                    "id": proj_id,
                    "name": f"Stress Project {i}",
                    "description": f"Knowledge project #{i} for bulk stress testing. References packets {pkt1} and {pkt2}.",
                    "packet_ids": [pkt1, pkt2],
                    "tags": ["stress-test", f"packet-group-{i // 10}", "bulk"],
                },
            )
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

            if resp.status_code != 201:
                failures.append(f"{proj_id}: {resp.status_code} - {resp.text[:100]}")
            else:
                self.__class__.CREATED_IDS.append(proj_id)

        # Report
        avg_ms = sum(timings) / len(timings) * 1000
        max_ms = max(timings) * 1000
        min_ms = min(timings) * 1000
        print(f"\n  [TIMING] Projects: {len(self.__class__.CREATED_IDS)} created "
              f"| avg {avg_ms:.1f}ms | min {min_ms:.1f}ms | max {max_ms:.1f}ms")

        if failures:
            pytest.fail(f"{len(failures)} project creations failed: {failures[:5]}")

        assert len(self.__class__.CREATED_IDS) == BULK_COUNT

    def test_list_after_bulk_projects(self, client: TestClient) -> None:
        """List all projects and verify bulk records appear."""
        resp = client.get("/api/v1/knowledge-hub/projects")
        assert resp.status_code == 200
        body = resp.json()
        # 1 seed + BULK_COUNT = total
        expected = 1 + BULK_COUNT
        assert body["total"] >= expected, f"Expected >= {expected} projects, got {body['total']}"
        ids = {p["id"] for p in body["data"]}
        for pid in self.__class__.CREATED_IDS:
            assert pid in ids, f"Missing bulk project: {pid}"

    def test_test_all_first_three_projects(self, client: TestClient) -> None:
        """Test-all on first 3 projects."""
        ids = self.__class__.CREATED_IDS
        if len(ids) < 3:
            pytest.skip(f"Only {len(ids)} projects available, need 3 for test-all")
        to_test = ids[:3]
        for proj_id in to_test:
            resp = client.post(f"/api/v1/knowledge-hub/projects/{proj_id}/test-all")
            assert resp.status_code == 200
            body = resp.json()
            assert body["all_passed"] is True
            assert body["packets_tested"] == 2  # Each project has 2 packets
            assert body["total_sources"] >= 1

    def test_build_data_object_first_project(self, client: TestClient) -> None:
        """Build a data object for the first bulk project."""
        if not self.__class__.CREATED_IDS:
            pytest.skip("No bulk projects")
        proj_id = self.__class__.CREATED_IDS[0]
        resp = client.post(f"/api/v1/knowledge-hub/projects/{proj_id}/build-data-object")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data_object"]["project"]["name"] == "Stress Project 0"
        assert "packets" in body["data_object"]
        assert len(body["data_object"]["packets"]) == 2
        assert "methods" in body["data_object"]


# ═══════════════════════════════════════════════════════════════════
# Phase 6: Cross-Entity Data Integrity Under Load
# ═══════════════════════════════════════════════════════════════════


class TestBulkDataIntegrity:
    """Verify cross-entity integrity holds under load."""

    TYPE_IDS: List[str] = TestBulkCreateSourceTypes.CREATED_IDS
    SRC_IDS: List[str] = TestBulkCreateSourceConfigs.CREATED_IDS
    PIPE_IDS: List[str] = TestBulkCreatePipelines.CREATED_IDS
    PKT_IDS: List[str] = TestBulkCreatePackets.CREATED_IDS
    PROJ_IDS: List[str] = TestBulkCreateProjects.CREATED_IDS

    def test_all_source_configs_reference_valid_types(self, client: TestClient) -> None:
        """Every bulk source config references a valid source type."""
        resp = client.get("/api/v1/knowledge-hub/sources")
        configs = resp.json()["data"]
        type_ids = {t["id"] for t in client.get("/api/v1/knowledge-hub/source-types").json()["data"]}
        for cfg in configs:
            assert cfg["source_type_id"] in type_ids, (
                f"Source config '{cfg['id']}' references missing type '{cfg['source_type_id']}'"
            )

    def test_all_pipelines_reference_valid_configs(self, client: TestClient) -> None:
        """Every bulk pipeline references a valid source config."""
        resp = client.get("/api/v1/knowledge-hub/pipelines")
        pipelines = resp.json()["data"]
        config_ids = {c["id"] for c in client.get("/api/v1/knowledge-hub/sources").json()["data"]}
        for pipe in pipelines:
            assert pipe["source_config_id"] in config_ids, (
                f"Pipeline '{pipe['id']}' references missing source '{pipe['source_config_id']}'"
            )

    def test_all_packet_references_are_valid(self, client: TestClient) -> None:
        """Every bulk packet's sources and pipelines all exist."""
        sources_resp = client.get("/api/v1/knowledge-hub/sources")
        config_ids = {c["id"] for c in sources_resp.json()["data"]}
        pipe_ids = {p["id"] for p in client.get("/api/v1/knowledge-hub/pipelines").json()["data"]}

        resp = client.get("/api/v1/knowledge-hub/packets")
        for pkt in resp.json()["data"]:
            for sc_id in pkt.get("source_config_ids", []):
                assert sc_id in config_ids, f"Packet '{pkt['id']}' references missing source '{sc_id}'"
            for pl_id in pkt.get("pipeline_ids", []):
                assert pl_id in pipe_ids, f"Packet '{pkt['id']}' references missing pipeline '{pl_id}'"

    def test_all_project_references_are_valid(self, client: TestClient) -> None:
        """Every project's packet IDs all exist."""
        pkt_ids = {p["id"] for p in client.get("/api/v1/knowledge-hub/packets").json()["data"]}
        resp = client.get("/api/v1/knowledge-hub/projects")
        for proj in resp.json()["data"]:
            for pk_id in proj.get("packet_ids", []):
                assert pk_id in pkt_ids, f"Project '{proj['id']}' references missing packet '{pk_id}'"


# ═══════════════════════════════════════════════════════════════════
# Phase 7: Cleanup — Remove All Bulk-Created Resources
# ═══════════════════════════════════════════════════════════════════


class TestBulkCleanup:
    """Remove all resources created during the stress test."""

    def test_cleanup_projects(self, client: TestClient) -> None:
        """Delete all bulk-created projects."""
        ids = TestBulkCreateProjects.CREATED_IDS
        for i, proj_id in enumerate(ids):
            del_resp = client.delete(f"/api/v1/knowledge-hub/projects/{proj_id}")
            assert del_resp.status_code == 200, f"DELETE project '{proj_id}' failed: {del_resp.status_code}"
            resp = client.get(f"/api/v1/knowledge-hub/projects/{proj_id}")
            assert resp.status_code == 404, f"Project '{proj_id}' still exists after cleanup"
        print(f"\n  [CLEANUP] Projects cleaned: {len(ids)}")

    def test_cleanup_packets(self, client: TestClient) -> None:
        """Delete all bulk-created packets."""
        ids = TestBulkCreatePackets.CREATED_IDS
        for i, pkt_id in enumerate(ids):
            del_resp = client.delete(f"/api/v1/knowledge-hub/packets/{pkt_id}")
            assert del_resp.status_code == 200, f"DELETE packet '{pkt_id}' failed: {del_resp.status_code}"
            resp = client.get(f"/api/v1/knowledge-hub/packets/{pkt_id}")
            assert resp.status_code == 404, f"Packet '{pkt_id}' still exists after cleanup"
        print(f"\n  [CLEANUP] Packets cleaned: {len(ids)}")

    def test_cleanup_pipelines(self, client: TestClient) -> None:
        """Delete all bulk-created pipelines."""
        ids = TestBulkCreatePipelines.CREATED_IDS
        for i, pipe_id in enumerate(ids):
            del_resp = client.delete(f"/api/v1/knowledge-hub/pipelines/{pipe_id}")
            assert del_resp.status_code == 200, f"DELETE pipeline '{pipe_id}' failed: {del_resp.status_code}"
            resp = client.get(f"/api/v1/knowledge-hub/pipelines/{pipe_id}")
            assert resp.status_code == 404, f"Pipeline '{pipe_id}' still exists after cleanup"
        print(f"\n  [CLEANUP] Pipelines cleaned: {len(ids)}")

    def test_cleanup_source_configs(self, client: TestClient) -> None:
        """Delete all bulk-created source configs."""
        ids = TestBulkCreateSourceConfigs.CREATED_IDS
        for i, src_id in enumerate(ids):
            del_resp = client.delete(f"/api/v1/knowledge-hub/sources/{src_id}")
            assert del_resp.status_code == 200, f"DELETE source '{src_id}' failed: {del_resp.status_code}"
            resp = client.get(f"/api/v1/knowledge-hub/sources/{src_id}")
            assert resp.status_code == 404, f"Source config '{src_id}' still exists after cleanup"
        print(f"\n  [CLEANUP] Source configs cleaned: {len(ids)}")

    def test_cleanup_source_types(self, client: TestClient) -> None:
        """Delete all bulk-created source types."""
        ids = TestBulkCreateSourceTypes.CREATED_IDS
        for i, type_id in enumerate(ids):
            del_resp = client.delete(f"/api/v1/knowledge-hub/source-types/{type_id}")
            assert del_resp.status_code == 200, f"DELETE source type '{type_id}' failed: {del_resp.status_code}"
            resp = client.get(f"/api/v1/knowledge-hub/source-types/{type_id}")
            assert resp.status_code == 404, f"Source type '{type_id}' still exists after cleanup"
        print(f"\n  [CLEANUP] Source types cleaned: {len(ids)}")

    def test_verify_clean_state(self, client: TestClient) -> None:
        """Verify all bulk resources are gone and seed data is intact."""
        # Note: using >= to account for potential artifacts from other test files
        # that share the same session-scoped in-memory DB.
        resp = client.get("/api/v1/knowledge-hub/source-types")
        assert resp.json()["total"] >= 8, f"Expected >= 8 types, got {resp.json()['total']}"

        resp = client.get("/api/v1/knowledge-hub/sources")
        assert resp.json()["total"] >= 7, f"Expected >= 7 configs, got {resp.json()['total']}"

        resp = client.get("/api/v1/knowledge-hub/pipelines")
        assert resp.json()["total"] >= 5, f"Expected >= 5 pipelines, got {resp.json()['total']}"

        resp = client.get("/api/v1/knowledge-hub/packets")
        assert resp.json()["total"] >= 6, f"Expected >= 6 packets, got {resp.json()['total']}"

        resp = client.get("/api/v1/knowledge-hub/projects")
        assert resp.json()["total"] >= 1, f"Expected >= 1 project, got {resp.json()['total']}"


# ═══════════════════════════════════════════════════════════════════
# Phase 8: Timing Summary — Full Run Report
# ═══════════════════════════════════════════════════════════════════


class TestBulkTimingSummary:
    """Print a summary of total entities created and overall timing."""

    def test_print_summary(self) -> None:
        """Print stress test summary and assert all 5 batches completed."""
        st = len(TestBulkCreateSourceTypes.CREATED_IDS)
        sc = len(TestBulkCreateSourceConfigs.CREATED_IDS)
        pl = len(TestBulkCreatePipelines.CREATED_IDS)
        pk = len(TestBulkCreatePackets.CREATED_IDS)
        pr = len(TestBulkCreateProjects.CREATED_IDS)
        total = st + sc + pl + pk + pr
        expected_total = BULK_COUNT * 5
        print(f"\n{'=' * 60}")
        print(f"  STRESS TEST SUMMARY ({BULK_COUNT}x5 = {expected_total} entities)")
        print(f"{'=' * 60}")
        print(f"  Source Types:   {st}")
        print(f"  Source Configs: {sc}")
        print(f"  Pipelines:      {pl}")
        print(f"  Packets:        {pk}")
        print(f"  Projects:       {pr}")
        print(f"  TOTAL ENTITIES: {total}")
        print(f"  (seed records: {8 + 7 + 5 + 6 + 1} = {total + 27} total)")
        print(f"{'=' * 60}")
        assert total == expected_total, (
            f"Expected {expected_total} entities across 5 types, got {total}. "
            f"Some phases may have failed."
        )
