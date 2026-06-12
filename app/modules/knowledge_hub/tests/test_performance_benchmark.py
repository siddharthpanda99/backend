"""
Performance benchmark — times the full Create -> Verify -> Attach pipeline
and asserts upper bounds on individual response times.

Measures end-to-end latency for the Knowledge Hub pipeline across multiple
iterations to detect performance regressions.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python -m pytest app/modules/knowledge_hub/tests/test_performance_benchmark.py -v --tb=short -s
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient


# ── Performance thresholds (milliseconds) ──────────────────────────
# These are conservative upper bounds for mock/data operations on
# SQLite. Adjust based on your hardware/environment.

THRESHOLD_CREATE_MS = 200       # POST create for any entity type
THRESHOLD_EXECUTE_MS = 300      # POST execute source/pipeline
THRESHOLD_VERIFY_MS = 200       # POST verify any entity
THRESHOLD_RESOLVE_MS = 300      # POST resolve packet
THRESHOLD_TEST_ALL_MS = 500     # POST test-all packet/project
THRESHOLD_BUILD_DO_MS = 500     # POST build data object
THRESHOLD_ATTACH_MS = 200       # POST attach/detach
THRESHOLD_LIST_MS = 100         # GET list endpoints
THRESHOLD_GET_MS = 100          # GET single resource
THRESHOLD_BULK_10_MS = 500      # 10 sequential operations

# How many iterations to run for stable timing
ITERATIONS = 3


# ═══════════════════════════════════════════════════════════════════
# Timing Helpers
# ═══════════════════════════════════════════════════════════════════


class Timer:
    """Simple timer for measuring API response times."""

    def __init__(self) -> None:
        self.times: List[float] = []

    def measure(self, label: str, elapsed_ms: float) -> None:
        self.times.append(elapsed_ms)
        print(f"    {label}: {elapsed_ms:.1f}ms")

    @property
    def avg(self) -> float:
        return sum(self.times) / len(self.times) if self.times else 0.0

    @property
    def max(self) -> float:
        return max(self.times) if self.times else 0.0

    @property
    def min(self) -> float:
        return min(self.times) if self.times else 0.0

    def summary(self, name: str) -> str:
        return f"  {name}: avg={self.avg:.1f}ms max={self.max:.1f}ms min={self.min:.1f}ms ({len(self.times)} samples)"


def time_request(client: TestClient, method: str, url: str, **kwargs: Any) -> tuple[float, Any]:
    """Execute an HTTP request and return (elapsed_ms, response)."""
    start = time.perf_counter()
    if method == "get":
        resp = client.get(url, **kwargs)
    elif method == "post":
        resp = client.post(url, **kwargs)
    elif method == "put":
        resp = client.put(url, **kwargs)
    elif method == "delete":
        resp = client.delete(url, **kwargs)
    else:
        raise ValueError(f"Unknown method: {method}")
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed, resp


# ═══════════════════════════════════════════════════════════════════
# Benchmark: Single Pipeline Throughput
# ═══════════════════════════════════════════════════════════════════


class TestSinglePipelineBenchmark:
    """Benchmark a single Create->Execute->Verify->Pipeline->Packet->Project->Attach cycle."""

    CREATED_IDS: Dict[str, str] = {}
    ITERATION_TIMES: List[float] = []

    RESOURCE_IDS: Dict[str, str] = {
        "agent_id": "perf-agent-001",
    }

    def test_benchmark(self, client: TestClient) -> None:
        """Run the full pipeline ITERATIONS times and measure all steps."""
        timer = Timer()
        all_iterations_detail: List[str] = []

        for iteration in range(1, ITERATIONS + 1):
            print(f"\n  --- Iteration {iteration}/{ITERATIONS} ---")

            # Use unique per-iteration IDs so iterations don't depend on cleanup
            iter_ids = {
                "type_id": f"perf-st-{iteration:03d}",
                "src_id": f"perf-src-{iteration:03d}",
                "pipe_id": f"perf-pipe-{iteration:03d}",
                "pkt_id": f"perf-pkt-{iteration:03d}",
                "proj_id": f"perf-proj-{iteration:03d}",
            }
            ops_before = len(timer.times)

            # ── 1. Create Source Type ──────────────────────────
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/source-types",
                json={
                    "id": iter_ids["type_id"],
                    "name": f"Perf Test Type {iteration}",
                    "description": "Performance benchmark source type",
                    "icon": "\u26a1",
                    "category": "api",
                    "config_schema": {
                        "type": "object",
                        "properties": {
                            "endpoint": {"type": "string"},
                            "api_key": {"type": "string"},
                        },
                    },
                },
            )
            timer.measure("Create Source Type", elapsed)
            assert resp.status_code == 201, f"Create source type failed: {resp.text[:200]}"
            assert elapsed < THRESHOLD_CREATE_MS, (
                f"Create source type took {elapsed:.1f}ms (threshold: {THRESHOLD_CREATE_MS}ms)"
            )

            # ── 2. Create Source Config ────────────────────────
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/sources",
                json={
                    "id": iter_ids["src_id"],
                    "source_type_id": iter_ids["type_id"],
                    "name": f"Perf Source {iteration}",
                    "description": "Performance benchmark source config",
                    "config": {"endpoint": "https://perf.example.com/api", "api_key": "sk-perf-001"},
                    "tags": ["perf-test", "benchmark"],
                },
            )
            timer.measure("Create Source Config", elapsed)
            assert resp.status_code == 201, f"Create source config failed: {resp.text[:200]}"
            assert elapsed < THRESHOLD_CREATE_MS

            # ── 3. Execute Source ──────────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/sources/{iter_ids['src_id']}/execute"
            )
            timer.measure("Execute Source", elapsed)
            assert resp.status_code == 200, f"Execute source failed: {resp.text[:200]}"
            assert resp.json()["success"] is True
            assert elapsed < THRESHOLD_EXECUTE_MS

            # ── 4. Verify Source ───────────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/sources/{iter_ids['src_id']}/verify"
            )
            timer.measure("Verify Source", elapsed)
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "verified"
            assert elapsed < THRESHOLD_VERIFY_MS

            # ── 5. Create Pipeline ─────────────────────────────
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/pipelines",
                json={
                    "id": iter_ids["pipe_id"],
                    "name": f"Perf Pipeline {iteration}",
                    "description": "Performance benchmark pipeline",
                    "source_config_id": iter_ids["src_id"],
                    "pipeline_definition": {
                        "version": "2.0",
                        "type": "extract_transform",
                        "steps": [
                            {"name": "fetch", "operation": "api_query", "config": {"endpoint": "https://perf.example.com"}},
                            {"name": "parse", "operation": "json_parse", "config": {"fields": ["id", "name", "data"]}},
                            {"name": "summarize", "operation": "llm_summarize", "config": {"max_length": 100}},
                        ],
                        "output": {"format": "structured_records", "fields": ["id", "name"]},
                    },
                },
            )
            timer.measure("Create Pipeline", elapsed)
            assert resp.status_code == 201
            assert elapsed < THRESHOLD_CREATE_MS

            # ── 6. Execute Pipeline ────────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/pipelines/{iter_ids['pipe_id']}/execute"
            )
            timer.measure("Execute Pipeline", elapsed)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert resp.json()["status"] == "completed"
            assert len(resp.json()["steps"]) == 3
            assert elapsed < THRESHOLD_EXECUTE_MS

            # ── 7. Verify Pipeline ─────────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/pipelines/{iter_ids['pipe_id']}/verify"
            )
            timer.measure("Verify Pipeline", elapsed)
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "verified"
            assert elapsed < THRESHOLD_VERIFY_MS

            # ── 8. Create Packet ───────────────────────────────
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/packets",
                json={
                    "id": iter_ids["pkt_id"],
                    "name": f"Perf Packet {iteration}",
                    "description": "Performance benchmark packet",
                    "source_config_ids": [iter_ids["src_id"]],
                    "pipeline_ids": [iter_ids["pipe_id"]],
                    "tags": ["perf-test"],
                },
            )
            timer.measure("Create Packet", elapsed)
            assert resp.status_code == 201
            assert elapsed < THRESHOLD_CREATE_MS

            # ── 9. Resolve Packet ──────────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/packets/{iter_ids['pkt_id']}/resolve"
            )
            timer.measure("Resolve Packet", elapsed)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert resp.json()["status"] == "resolved"
            assert elapsed < THRESHOLD_RESOLVE_MS

            # ── 10. Test-All Packet ────────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/packets/{iter_ids['pkt_id']}/test-all"
            )
            timer.measure("Test-All Packet", elapsed)
            assert resp.status_code == 200
            assert resp.json()["all_passed"] is True
            assert elapsed < THRESHOLD_TEST_ALL_MS

            # ── 11. Verify Packet ──────────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/packets/{iter_ids['pkt_id']}/verify"
            )
            timer.measure("Verify Packet", elapsed)
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "verified"
            assert elapsed < THRESHOLD_VERIFY_MS

            # ── 12. Get Packet Data ────────────────────────────
            elapsed, resp = time_request(
                client, "get", f"/api/v1/knowledge-hub/packets/{iter_ids['pkt_id']}/data"
            )
            timer.measure("Get Packet Data", elapsed)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert elapsed < THRESHOLD_GET_MS

            # ── 13. Create Project ─────────────────────────────
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/projects",
                json={
                    "id": iter_ids["proj_id"],
                    "name": f"Perf Project {iteration}",
                    "description": "Performance benchmark project",
                    "packet_ids": [iter_ids["pkt_id"]],
                    "tags": ["perf-test"],
                },
            )
            timer.measure("Create Project", elapsed)
            assert resp.status_code == 201
            assert elapsed < THRESHOLD_CREATE_MS

            # ── 14. Test-All Project ───────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/projects/{iter_ids['proj_id']}/test-all"
            )
            timer.measure("Test-All Project", elapsed)
            assert resp.status_code == 200
            assert resp.json()["all_passed"] is True
            assert elapsed < THRESHOLD_TEST_ALL_MS

            # ── 15. Verify Project ─────────────────────────────
            elapsed, resp = time_request(
                client, "post", f"/api/v1/knowledge-hub/projects/{iter_ids['proj_id']}/verify"
            )
            timer.measure("Verify Project", elapsed)
            assert resp.status_code == 200
            assert resp.json()["data"]["status"] == "verified"
            assert elapsed < THRESHOLD_VERIFY_MS

            # ── 16. Build Data Object ──────────────────────────
            elapsed, resp = time_request(
                client, "post",
                f"/api/v1/knowledge-hub/projects/{iter_ids['proj_id']}/build-data-object"
            )
            timer.measure("Build Data Object", elapsed)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            data_obj = resp.json()["data_object"]
            assert data_obj["project"]["name"] == f"Perf Project {iteration}"
            assert len(data_obj["packets"]) >= 1
            assert "methods" in data_obj
            assert "search_sources" in data_obj["methods"]
            assert elapsed < THRESHOLD_BUILD_DO_MS

            # ── 17. Get Data Object ────────────────────────────
            elapsed, resp = time_request(
                client, "get",
                f"/api/v1/knowledge-hub/projects/{iter_ids['proj_id']}/data-object"
            )
            timer.measure("Get Data Object", elapsed)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert "data_object_schema" in resp.json()
            assert elapsed < THRESHOLD_GET_MS

            # ── 18. Attach to Agent ────────────────────────────
            elapsed, resp = time_request(
                client, "post",
                f"/api/v1/knowledge-hub/projects/{iter_ids['proj_id']}/attach",
                json={"agent_id": self.RESOURCE_IDS["agent_id"]},
            )
            timer.measure("Attach to Agent", elapsed)
            assert resp.status_code == 200
            assert resp.json()["data"]["attached_agent_id"] == self.RESOURCE_IDS["agent_id"]
            assert elapsed < THRESHOLD_ATTACH_MS

            # ── 19. Detach from Agent ──────────────────────────
            elapsed, resp = time_request(
                client, "post",
                f"/api/v1/knowledge-hub/projects/{iter_ids['proj_id']}/detach"
            )
            timer.measure("Detach from Agent", elapsed)
            assert resp.status_code == 200
            assert resp.json()["data"]["attached_agent_id"] is None
            assert elapsed < THRESHOLD_ATTACH_MS

            # ── 20. List Verification ──────────────────────────
            for endpoint, label in [
                ("/api/v1/knowledge-hub/source-types", "List Source Types"),
                ("/api/v1/knowledge-hub/sources", "List Sources"),
                ("/api/v1/knowledge-hub/pipelines", "List Pipelines"),
                ("/api/v1/knowledge-hub/packets", "List Packets"),
                ("/api/v1/knowledge-hub/projects", "List Projects"),
            ]:
                elapsed, resp = time_request(client, "get", endpoint)
                timer.measure(label, elapsed)
                assert resp.status_code == 200
                assert resp.json()["success"] is True
                assert elapsed < THRESHOLD_LIST_MS

            # ── Store iteration total ──────────────────────────
            iteration_total = sum(timer.times[ops_before:])
            self.__class__.ITERATION_TIMES.append(iteration_total)

            # ── Cleanup this iteration's resources ─────────────
            self._cleanup_iteration(client, iter_ids)
            print(f"  --- Iteration {iteration} total: {iteration_total:.1f}ms ---")

        # ── Final Report ─────────────────────────────────────
        self._print_report(timer)

    def _cleanup_iteration(self, client: TestClient, iter_ids: dict[str, str]) -> None:
        """Delete all resources created in this iteration."""
        for endpoint, rid_key in [
            ("projects", "proj_id"),
            ("packets", "pkt_id"),
            ("pipelines", "pipe_id"),
            ("sources", "src_id"),
            ("source-types", "type_id"),
        ]:
            rid = iter_ids.get(rid_key)
            if rid:
                resp = client.delete(f"/api/v1/knowledge-hub/{endpoint}/{rid}")
                # Accept 404 if resource was never created (partial iteration failure)
                assert resp.status_code in (200, 404), (
                    f"Cleanup DELETE {endpoint}/{rid}: {resp.status_code} {resp.text[:100]}"
                )

    def _print_report(self, timer: Timer) -> None:
        """Print a formatted performance report."""
        total_ops = len(timer.times)
        print(f"\n{'=' * 65}")
        print(f"  PERFORMANCE BENCHMARK REPORT")
        print(f"{'=' * 65}")
        print(f"  Iterations:     {ITERATIONS}")
        print(f"  Total ops:      {total_ops}")
        print(f"  Overall avg:    {timer.avg:.1f}ms")
        print(f"  Overall max:    {timer.max:.1f}ms")
        print(f"  Overall min:    {timer.min:.1f}ms")
        print(f"  Iteration avg:  {sum(self.ITERATION_TIMES) / len(self.ITERATION_TIMES):.1f}ms")
        print(f"  Best iteration: {min(self.ITERATION_TIMES):.1f}ms")
        print(f"  Worst iteration:{max(self.ITERATION_TIMES):.1f}ms")
        print(f"{'=' * 65}")

        # Assert overall max response time is below threshold
        assert timer.max < 1000, (
            f"Max response time {timer.max:.1f}ms exceeded 1000ms threshold"
        )


# ═══════════════════════════════════════════════════════════════════
# Benchmark: Bulk Sequential Operations
# ═══════════════════════════════════════════════════════════════════


class TestBulkSequentialBenchmark:
    """Measure time to create 10 resources of each type sequentially."""

    BULK_N = 10

    def test_bulk_sequential_creations(self, client: TestClient) -> None:
        """Create N source types, N configs, N pipelines sequentially and measure."""
        timer = Timer()

        # ── Bulk create source types ──────────────────────────
        type_ids: list[str] = []
        for i in range(self.BULK_N):
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/source-types",
                json={
                    "id": f"perf-bulk-st-{i:03d}",
                    "name": f"Perf Bulk Type {i}",
                    "category": "api",
                },
            )
            timer.measure(f"Create Type {i}", elapsed)
            assert resp.status_code == 201
            assert elapsed < THRESHOLD_CREATE_MS
            type_ids.append(f"perf-bulk-st-{i:03d}")

        avg_type = timer.times[-self.BULK_N:]
        bulk_10_avg = sum(avg_type) / len(avg_type)
        assert bulk_10_avg < 100, f"Avg bulk type creation: {bulk_10_avg:.1f}ms (threshold: 100ms)"

        # ── Bulk create source configs ─────────────────────────
        src_ids: list[str] = []
        for i in range(self.BULK_N):
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/sources",
                json={
                    "id": f"perf-bulk-src-{i:03d}",
                    "source_type_id": type_ids[i],
                    "name": f"Perf Bulk Source {i}",
                    "config": {"endpoint": f"https://bulk{i}.example.com"},
                },
            )
            timer.measure(f"Create Source {i}", elapsed)
            assert resp.status_code == 201
            assert elapsed < THRESHOLD_CREATE_MS
            src_ids.append(f"perf-bulk-src-{i:03d}")

        # ── Bulk create pipelines ──────────────────────────────
        pipe_ids: list[str] = []
        for i in range(self.BULK_N):
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/pipelines",
                json={
                    "id": f"perf-bulk-pipe-{i:03d}",
                    "name": f"Perf Bulk Pipeline {i}",
                    "source_config_id": src_ids[i],
                    "pipeline_definition": {
                        "version": "1.0",
                        "type": "extract",
                        "steps": [{"name": "fetch", "operation": "api_query", "config": {}}],
                        "output": {"format": "structured_records"},
                    },
                },
            )
            timer.measure(f"Create Pipeline {i}", elapsed)
            assert resp.status_code == 201
            assert elapsed < THRESHOLD_CREATE_MS
            pipe_ids.append(f"perf-bulk-pipe-{i:03d}")

        # ── Bulk create packets ───────────────────────────────
        pkt_ids: list[str] = []
        for i in range(self.BULK_N):
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/packets",
                json={
                    "id": f"perf-bulk-pkt-{i:03d}",
                    "name": f"Perf Bulk Packet {i}",
                    "source_config_ids": [src_ids[i]],
                    "pipeline_ids": [pipe_ids[i]],
                },
            )
            timer.measure(f"Create Packet {i}", elapsed)
            assert resp.status_code == 201
            assert elapsed < THRESHOLD_CREATE_MS
            pkt_ids.append(f"perf-bulk-pkt-{i:03d}")

        # ── Bulk create projects ──────────────────────────────
        proj_ids: list[str] = []
        for i in range(self.BULK_N):
            elapsed, resp = time_request(
                client, "post", "/api/v1/knowledge-hub/projects",
                json={
                    "id": f"perf-bulk-proj-{i:03d}",
                    "name": f"Perf Bulk Project {i}",
                    "packet_ids": [pkt_ids[i]],
                },
            )
            timer.measure(f"Create Project {i}", elapsed)
            assert resp.status_code == 201
            assert elapsed < THRESHOLD_CREATE_MS
            proj_ids.append(f"perf-bulk-proj-{i:03d}")

        # ── Report ────────────────────────────────────────────
        total_ops = len(timer.times)
        print(f"\n{'=' * 65}")
        print(f"  BULK SEQUENTIAL BENCHMARK ({self.BULK_N}x5 = {self.BULK_N * 5} entities)")
        print(f"{'=' * 65}")
        print(f"  Total ops:      {total_ops}")
        print(f"  Overall avg:    {timer.avg:.1f}ms")
        print(f"  Overall max:    {timer.max:.1f}ms")
        print(f"  Overall min:    {timer.min:.1f}ms")
        print(f"{'=' * 65}")

        # Assert max is below a generous ceiling
        assert timer.max < 2000, f"Max response time {timer.max:.1f}ms exceeded 2000ms threshold"

        # ── Cleanup ───────────────────────────────────────────
        for proj_id in proj_ids:
            client.delete(f"/api/v1/knowledge-hub/projects/{proj_id}")
        for pkt_id in pkt_ids:
            client.delete(f"/api/v1/knowledge-hub/packets/{pkt_id}")
        for pid in pipe_ids:
            client.delete(f"/api/v1/knowledge-hub/pipelines/{pid}")
        for sid in src_ids:
            client.delete(f"/api/v1/knowledge-hub/sources/{sid}")
        for tid in type_ids:
            client.delete(f"/api/v1/knowledge-hub/source-types/{tid}")

        # Verify cleanup
        for endpoint, expected_min in [
            ("/api/v1/knowledge-hub/source-types", 8),
            ("/api/v1/knowledge-hub/sources", 7),
            ("/api/v1/knowledge-hub/pipelines", 5),
            ("/api/v1/knowledge-hub/packets", 6),
            ("/api/v1/knowledge-hub/projects", 1),
        ]:
            resp = client.get(endpoint)
            assert resp.json()["total"] >= expected_min


# ═══════════════════════════════════════════════════════════════════
# Benchmark: Read-Only Performance
# ═══════════════════════════════════════════════════════════════════


class TestReadOnlyBenchmark:
    """Benchmark GET endpoints for response time consistency."""

    def test_list_endpoints_under_100ms(self, client: TestClient) -> None:
        """All list endpoints respond in under 100ms."""
        endpoints = [
            "/api/v1/knowledge-hub/source-types",
            "/api/v1/knowledge-hub/sources",
            "/api/v1/knowledge-hub/pipelines",
            "/api/v1/knowledge-hub/packets",
            "/api/v1/knowledge-hub/projects",
        ]
        timer = Timer()
        for endpoint in endpoints:
            elapsed, resp = time_request(client, "get", endpoint)
            timer.measure(endpoint.split("/")[-1], elapsed)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert elapsed < THRESHOLD_LIST_MS, (
                f"GET {endpoint} took {elapsed:.1f}ms (threshold: {THRESHOLD_LIST_MS}ms)"
            )
        print(f"\n  Read avg: {timer.avg:.1f}ms | max: {timer.max:.1f}ms")

    def test_get_single_endpoints_under_100ms(self, client: TestClient) -> None:
        """Single-resource GET endpoints respond in under 100ms."""
        endpoints = [
            "/api/v1/knowledge-hub/source-types/arxiv_api",
            "/api/v1/knowledge-hub/sources/src-arxiv-001",
            "/api/v1/knowledge-hub/pipelines/pipe-arxiv-001",
            "/api/v1/knowledge-hub/packets/pkt-academic-001",
            "/api/v1/knowledge-hub/projects/proj-ai-impact-001",
        ]
        timer = Timer()
        for endpoint in endpoints:
            elapsed, resp = time_request(client, "get", endpoint)
            timer.measure(endpoint.split("/")[-1], elapsed)
            assert resp.status_code == 200
            assert elapsed < THRESHOLD_GET_MS
        print(f"\n  Get avg: {timer.avg:.1f}ms | max: {timer.max:.1f}ms")

    def test_filtered_list_endpoints(self, client: TestClient) -> None:
        """Filtered list endpoints respond in under 100ms."""
        filters = [
            ("/api/v1/knowledge-hub/sources?status=verified", "sources?verified"),
            ("/api/v1/knowledge-hub/source-types?category=api", "types?api"),
            ("/api/v1/knowledge-hub/pipelines?status=verified", "pipes?verified"),
            ("/api/v1/knowledge-hub/packets?status=verified", "packets?verified"),
        ]
        timer = Timer()
        for url, label in filters:
            elapsed, resp = time_request(client, "get", url)
            timer.measure(label, elapsed)
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert elapsed < THRESHOLD_LIST_MS
        print(f"\n  Filtered avg: {timer.avg:.1f}ms | max: {timer.max:.1f}ms")
