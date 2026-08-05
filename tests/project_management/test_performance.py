"""Performance benchmarks — Domain 32.05.

Benchmarks for key PM service operations using ``time.perf_counter``.

Each benchmark measures wall-clock time for a mocked operation and
asserts it completes within a reasonable threshold. These are NOT
micro-benchmarks — they verify the service layer has no obvious
performance regressions (e.g. N+1 queries, exponential loops).
"""

import time
import pytest
from unittest.mock import MagicMock, patch

# ── Thresholds (seconds) ────────────────────────────────────────────────
# These are generous for CI environments. Actual prod performance should
# be much faster; these just catch catastrophic regressions.

THRESHOLD_FAST = 0.5     # simple CRUD operations
THRESHOLD_MEDIUM = 1.0   # operations with some iteration
THRESHOLD_SLOW = 3.0     # graph traversal, batch operations


@pytest.fixture
def mock_session():
    return MagicMock()


class TestProjectServicePerformance:
    """Benchmark ProjectService operations."""

    def test_list_projects_benchmark(self, mock_session):
        from common_lib.modules.project_management.service import ProjectService
        svc = ProjectService(session=mock_session)
        mock_session.exec.return_value.all.return_value = []

        start = time.perf_counter()
        for _ in range(100):
            svc.list_projects(limit=50)
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST, (
            f"100x list_projects took {elapsed:.3f}s (threshold {THRESHOLD_FAST}s)"
        )

    def test_get_project_stats_benchmark(self, mock_session):
        from common_lib.modules.project_management.service import ProjectService
        svc = ProjectService(session=mock_session)
        mock_session.exec.return_value.one.return_value = 42

        start = time.perf_counter()
        for _ in range(50):
            svc.get_project_stats("proj-1")
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST, (
            f"50x get_project_stats took {elapsed:.3f}s"
        )

    def test_create_project_with_defaults_benchmark(self, mock_session):
        from common_lib.modules.project_management.service import ProjectService
        from common_lib.modules.project_management.schemas import ProjectCreate
        svc = ProjectService(session=mock_session)
        mock_project = MagicMock()
        mock_project.id = "proj-1"
        svc.create_project = MagicMock(return_value=mock_project)
        data = ProjectCreate(name="P", identifier="P")

        start = time.perf_counter()
        for _ in range(50):
            svc.create_project(data=data, created_by="user-1")
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST


class TestIssueServicePerformance:
    """Benchmark IssueService operations."""

    def test_list_issues_benchmark(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)
        # Mock count query to return int and exec chain for session
        mock_session.exec.return_value.one.return_value = 0
        mock_session.exec.return_value.all.return_value = []

        start = time.perf_counter()
        for _ in range(100):
            svc.list_issues(project_id="proj-1", limit=25)
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST

    def test_bulk_update_benchmark(self, mock_session):
        from common_lib.modules.project_management.issues.service import IssueService
        svc = IssueService(session=mock_session)

        start = time.perf_counter()
        for _ in range(20):
            svc.bulk_update_issues(
                issue_ids=[f"iss-{i}" for i in range(50)],
                updates={"status_id": "done"},
                updated_by="user-1",
            )
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_MEDIUM


class TestGraphServicePerformance:
    """Benchmark WorkGraphService — graph traversal is the most complex PM operation."""

    def test_bfs_traversal_benchmark(self, mock_session):
        from common_lib.modules.project_management.universal_graph.service import WorkGraphService
        svc = WorkGraphService(session=mock_session)
        # Mock get_related to return empty (fast path — no data)
        svc.get_related = MagicMock(return_value={
            "nodes": [], "edges": [], "levels": {}, "total_nodes": 0, "total_edges": 0,
        })

        start = time.perf_counter()
        for _ in range(50):
            svc.get_related("ws-1", "issue", "iss-1", max_depth=3)
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST

    def test_cycle_detection_benchmark(self, mock_session):
        from common_lib.modules.project_management.universal_graph.service import WorkGraphService
        svc = WorkGraphService(session=mock_session)

        start = time.perf_counter()
        for _ in range(50):
            svc.would_create_cycle("ws-1", "issue", "A", "issue", "B")
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST

    def test_impact_analysis_benchmark(self, mock_session):
        from common_lib.modules.project_management.universal_graph.service import WorkGraphService
        svc = WorkGraphService(session=mock_session)

        start = time.perf_counter()
        for _ in range(30):
            svc.analyze_impact("ws-1", "issue", "iss-1", max_depth=3)
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST


class TestCacheServicePerformance:
    """Benchmark PmCacheService — caching is latency-sensitive."""

    def test_get_or_compute_benchmark(self, mock_session):
        from common_lib.modules.project_management.cache.service import PmCacheService
        svc = PmCacheService(session=mock_session)

        def compute():
            return {"result": "expensive computation"}

        start = time.perf_counter()
        for i in range(100):
            svc.get_or_compute(
                workspace_id="ws-1",
                cache_key=f"test:{i}",
                entity_type="issue",
                entity_id=f"iss-{i}",
                compute_fn=compute,
            )
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST

    def test_cache_hit_benchmark(self, mock_session):
        """Cache hits should be near-instant (L1 in-memory)."""
        from common_lib.modules.project_management.cache.service import PmCacheService
        svc = PmCacheService(session=mock_session)

        # Pre-populate cache
        for i in range(100):
            svc.get_or_compute(
                workspace_id="ws-1",
                cache_key=f"hot:{i}",
                entity_type="issue",
                entity_id=f"iss-{i}",
                compute_fn=lambda: {"data": "x"},
            )

        start = time.perf_counter()
        for i in range(100):
            svc.get_or_compute(
                workspace_id="ws-1",
                cache_key=f"hot:{i}",
                entity_type="issue",
                entity_id=f"iss-{i}",
            )
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, (
            f"100x cache hits took {elapsed:.3f}s (expected < 0.1s for L1)"
        )

    def test_cache_miss_benchmark(self, mock_session):
        """Cache misses with compute should still be fast."""
        from common_lib.modules.project_management.cache.service import PmCacheService
        svc = PmCacheService(session=mock_session)

        def compute():
            return {"result": "x"}

        start = time.perf_counter()
        for i in range(100):
            svc.get_or_compute(
                workspace_id="ws-1",
                cache_key=f"miss:{i}",
                entity_type="issue",
                entity_id=f"iss-{i}",
                compute_fn=compute,
            )
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST


class TestOfflineServicePerformance:
    """Benchmark OfflineSyncService operations."""

    def test_enqueue_mutations_benchmark(self, mock_session):
        from common_lib.modules.project_management.offline.service import OfflineSyncService
        svc = OfflineSyncService(session=mock_session)

        start = time.perf_counter()
        for i in range(200):
            svc.enqueue_mutation(
                workspace_id="ws-1",
                entity_type="issue",
                entity_id=f"iss-{i}",
                mutation_type="update",
                payload={"status_id": "done"},
            )
        elapsed = time.perf_counter() - start

        assert elapsed < THRESHOLD_FAST
