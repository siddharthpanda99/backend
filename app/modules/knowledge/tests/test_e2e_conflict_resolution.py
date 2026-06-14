"""
E2E tests for the full conflict resolution flow.

Tests conflict scanning, listing, filtering, getting, resolving,
dismissing, propagating, and stats using real in-memory SQLite
with seeded conflict records.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python -m pytest app/modules/knowledge/tests/test_e2e_conflict_resolution.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

PREFIX = "/api/v1/knowledge"


# ═══════════════════════════════════════════════════════════════════
# Phase 1: List & Filter Conflicts
# ═══════════════════════════════════════════════════════════════════


class TestListConflicts:
    """List conflicts with filters."""

    def test_01_list_all_conflicts(self, client: TestClient) -> None:
        """List all conflicts — returns seed data."""
        resp = client.get(f"{PREFIX}/conflicts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 3

    def test_02_list_conflict_fields(self, client: TestClient) -> None:
        """Each conflict has all required fields."""
        resp = client.get(f"{PREFIX}/conflicts")
        conflict = resp.json()["data"]["conflicts"][0]
        assert "id" in conflict
        assert "chunk_a_id" in conflict
        assert "chunk_b_id" in conflict
        assert "conflict_type" in conflict
        assert "severity" in conflict
        assert "domain" in conflict
        assert "status" in conflict
        assert "chunk_a_content_preview" in conflict
        assert "chunk_b_content_preview" in conflict
        assert "chunk_a_confidence" in conflict
        assert "chunk_b_confidence" in conflict
        assert "similarity_score" in conflict
        assert "detected_at" in conflict
        assert "updated_at" in conflict

    def test_03_filter_by_status_open(self, client: TestClient) -> None:
        """Filter conflicts by status=open."""
        resp = client.get(f"{PREFIX}/conflicts?status=open")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert all(c["status"] == "open" for c in data["conflicts"])

    def test_04_filter_by_status_resolved(self, client: TestClient) -> None:
        """Filter conflicts by status=resolved."""
        resp = client.get(f"{PREFIX}/conflicts?status=resolved")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert all(c["status"] == "resolved" for c in data["conflicts"])

    def test_05_filter_by_severity_high(self, client: TestClient) -> None:
        """Filter conflicts by severity=high."""
        resp = client.get(f"{PREFIX}/conflicts?severity=high")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert all(c["severity"] == "high" for c in data["conflicts"])

    def test_06_filter_by_domain_news(self, client: TestClient) -> None:
        """Filter conflicts by domain=news."""
        resp = client.get(f"{PREFIX}/conflicts?domain=news")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_07_filter_by_source_id(self, client: TestClient) -> None:
        """Filter conflicts by source_id."""
        resp = client.get(f"{PREFIX}/conflicts?source_id=src-finance-001")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_08_filter_no_results(self, client: TestClient) -> None:
        """Filter with no matching results returns empty list."""
        resp = client.get(f"{PREFIX}/conflicts?status=escalated")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["conflicts"] == []

    def test_09_pagination(self, client: TestClient) -> None:
        """List conflicts with pagination."""
        resp = client.get(f"{PREFIX}/conflicts?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["conflicts"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_10_multiple_filters(self, client: TestClient) -> None:
        """Combine status and severity filters."""
        resp = client.get(f"{PREFIX}/conflicts?status=open&severity=high")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        c = data["conflicts"][0]
        assert c["status"] == "open"
        assert c["severity"] == "high"
        assert c["id"] == "e2e-conf-open-001"


# ═══════════════════════════════════════════════════════════════════
# Phase 2: Get Single Conflict
# ═══════════════════════════════════════════════════════════════════


class TestGetConflict:
    """Get single conflict details."""

    def test_11_get_open_conflict(self, client: TestClient) -> None:
        """Get an open conflict with full details."""
        resp = client.get(f"{PREFIX}/conflicts/e2e-conf-open-001")
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["id"] == "e2e-conf-open-001"
        assert d["status"] == "open"
        assert d["conflict_type"] == "direct_contradiction"
        assert d["severity"] == "high"
        assert d["domain"] == "financial"
        assert "Revenue grew" in d["chunk_a_content_preview"]
        assert "Revenue declined" in d["chunk_b_content_preview"]
        assert d["chunk_a_confidence"] == 0.95
        assert d["chunk_b_confidence"] == 0.88
        assert d["similarity_score"] == 0.85
        # Resolved-only fields should be None for open conflicts
        assert d["winner_chunk_id"] is None
        assert d["rationale"] is None
        assert d["resolution_strategy"] is None

    def test_12_get_resolved_conflict(self, client: TestClient) -> None:
        """Get a resolved conflict with resolution metadata."""
        resp = client.get(f"{PREFIX}/conflicts/e2e-conf-resolved-002")
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["id"] == "e2e-conf-resolved-002"
        assert d["status"] == "resolved"
        assert d["winner_chunk_id"] == "chunk-a-002"
        assert d["rationale"] == "Monday is the correct date"
        assert d["resolution_strategy"] == "human_arbitration"
        assert d["resolved_by"] == "admin"

    def test_13_get_dismissed_conflict(self, client: TestClient) -> None:
        """Get a dismissed conflict."""
        resp = client.get(f"{PREFIX}/conflicts/e2e-conf-dismissed-003")
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["id"] == "e2e-conf-dismissed-003"
        assert d["status"] == "dismissed"

    def test_14_get_non_existent_conflict(self, client: TestClient) -> None:
        """Get a non-existent conflict returns 404."""
        resp = client.get(f"{PREFIX}/conflicts/nonexistent-conflict-id")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Resolve Conflict
# ═══════════════════════════════════════════════════════════════════


class TestResolveConflict:
    """Resolve a conflict via the service-delegated endpoint.

    These tests use the real conflict service and in-memory DB
    for true end-to-end coverage.
    """

    def test_15_get_conflict_stats_before(self, client: TestClient) -> None:
        """Record baseline stats before resolving."""
        resp = client.get(f"{PREFIX}/conflicts/stats")
        assert resp.status_code == 200
        stats = resp.json()["data"]
        assert stats["by_status"]["open"] >= 1
        # Store for comparison

    def test_16_resolve_open_conflict(self, client: TestClient) -> None:
        """Resolve the open conflict with winner and rationale."""
        resp = client.post(
            f"{PREFIX}/conflicts/e2e-conf-open-001/resolve",
            json={
                "winner_chunk_id": "chunk-a-001",
                "rationale": "Higher confidence score (0.95 vs 0.88)",
                "resolved_by": "e2e-test",
                "strategy": "confidence",
                "force": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        d = body["data"]
        assert d["status"] == "resolved"
        assert d["winner_chunk_id"] == "chunk-a-001"
        assert "Higher confidence" in d["rationale"]
        assert d["resolution_strategy"] == "confidence"
        assert "resolved" in body["message"]

    def test_17_verify_resolution_persisted(self, client: TestClient) -> None:
        """Verify the resolution was persisted via GET."""
        resp = client.get(f"{PREFIX}/conflicts/e2e-conf-open-001")
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["status"] == "resolved"
        assert d["winner_chunk_id"] == "chunk-a-001"
        assert d["resolution_strategy"] == "confidence"

    def test_18_resolve_already_resolved(self, client: TestClient) -> None:
        """Resolving an already-resolved conflict returns an error."""
        resp = client.post(
            f"{PREFIX}/conflicts/e2e-conf-open-001/resolve",
            json={
                "winner_chunk_id": "chunk-a-001",
                "rationale": "Duplicate resolution",
                "resolved_by": "test",
                "strategy": "confidence",
            },
        )
        # Should return an error status since it's already resolved
        assert resp.status_code >= 400

    def test_19_resolve_missing_winner(self, client: TestClient) -> None:
        """Resolving without winner_chunk_id returns 422."""
        resp = client.post(
            f"{PREFIX}/conflicts/e2e-conf-resolved-002/resolve",
            json={"rationale": "Missing winner"},
        )
        assert resp.status_code == 422

    def test_20_resolve_non_existent(self, client: TestClient) -> None:
        """Resolving a non-existent conflict returns an error (500 from service layer)."""
        resp = client.post(
            f"{PREFIX}/conflicts/nonexistent-conflict/resolve",
            json={
                "winner_chunk_id": "chunk-a-001",
                "rationale": "Test",
                "resolved_by": "test",
                "strategy": "confidence",
            },
        )
        # Note: The service layer raises KBConflictError which the route
        # catches and returns 500. A 400-level response would be ideal but
        # this is the current backend behavior.
        assert resp.status_code >= 400, f"Expected error status, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════
# Phase 4: Dismiss Conflict
# ═══════════════════════════════════════════════════════════════════


class TestDismissConflict:
    """Dismiss a conflict."""

    # Create a new open conflict for dismissal testing
    # (the original open conflict was resolved in Phase 3)

    def test_21_create_conflict_for_dismiss(self, client: TestClient, db_session) -> None:
        """Add a new conflict to the DB for dismissal testing."""
        from datetime import datetime, timezone
        from common_lib.modules.knowledge_hub.models import ConflictRecord

        rec = ConflictRecord(
            id="e2e-conf-to-dismiss-004",
            chunk_a_id="chunk-a-004",
            chunk_b_id="chunk-b-004",
            conflict_type="cross_source",
            severity="low",
            domain="general",
            status="open",
            chunk_a_content_preview="Data point A",
            chunk_b_content_preview="Data point B",
            chunk_a_source="src-gen-003",
            chunk_b_source="src-gen-004",
            chunk_a_confidence=0.60,
            chunk_b_confidence=0.55,
            similarity_score=0.30,
            detected_at=datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(rec)
        db_session.commit()

    def test_22_dismiss_open_conflict(self, client: TestClient) -> None:
        """Dismiss an open conflict."""
        resp = client.post(
            f"{PREFIX}/conflicts/e2e-conf-to-dismiss-004/dismiss",
            json={"reason": "False positive — data points are unrelated", "dismissed_by": "e2e-test"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "dismissed"
        assert "dismissed" in body["message"]

    def test_23_verify_dismissal_persisted(self, client: TestClient) -> None:
        """Verify the dismissal was persisted."""
        resp = client.get(f"{PREFIX}/conflicts/e2e-conf-to-dismiss-004")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "dismissed"

    def test_24_dismiss_non_existent(self, client: TestClient) -> None:
        """Dismissing a non-existent conflict returns an error."""
        resp = client.post(
            f"{PREFIX}/conflicts/nonexistent-conflict/dismiss",
            json={"reason": "N/A"},
        )
        assert resp.status_code >= 400


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Propagate Resolution
# ═══════════════════════════════════════════════════════════════════


class TestPropagateConflict:
    """Propagate a conflict resolution."""

    def test_25_propagate_resolved_conflict(self, client: TestClient) -> None:
        """Propagate a resolved conflict's resolution to related chunks."""
        resp = client.post(
            f"{PREFIX}/conflicts/e2e-conf-open-001/propagate",
            json={},  # Let the service determine propagation targets
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "propagated" in body["message"]
        # The resolved conflict should have propagation targets
        assert "propagated_to" in body["data"]

    def test_26_propagate_with_target_ids(self, client: TestClient) -> None:
        """Propagate with explicit target chunk IDs."""
        resp = client.post(
            f"{PREFIX}/conflicts/e2e-conf-resolved-002/propagate",
            json={"target_chunk_ids": ["chunk-c-001", "chunk-c-002"]},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_27_propagate_non_existent(self, client: TestClient) -> None:
        """Propagating a non-existent conflict returns an error."""
        resp = client.post(
            f"{PREFIX}/conflicts/nonexistent-conflict/propagate",
            json={},
        )
        assert resp.status_code >= 400


# ═══════════════════════════════════════════════════════════════════
# Phase 6: Conflict Scan
# ═══════════════════════════════════════════════════════════════════


class TestConflictScan:
    """Run full conflict scan."""

    def test_28_scan_all(self, client: TestClient) -> None:
        """Run a full conflict scan."""
        resp = client.post(f"{PREFIX}/conflicts/scan", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "new_conflicts" in body["data"]
        assert body["data"]["count"] >= 0
        assert "Scanned" in body["message"]

    def test_29_scan_with_source_filter(self, client: TestClient) -> None:
        """Run conflict scan filtered by source."""
        resp = client.post(
            f"{PREFIX}/conflicts/scan?source_id=src-finance-001&limit=50",
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ═══════════════════════════════════════════════════════════════════
# Phase 7: Conflict Stats
# ═══════════════════════════════════════════════════════════════════


class TestConflictStats:
    """Conflict statistics."""

    def test_30_get_stats(self, client: TestClient) -> None:
        """Get conflict statistics after all operations."""
        resp = client.get(f"{PREFIX}/conflicts/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        stats = body["data"]
        assert "total" in stats
        assert "by_status" in stats
        assert "by_severity" in stats
        # After our operations:
        # - 1 resolved (e2e-conf-resolved-002)
        # - 1 dismissed (e2e-conf-dismissed-003)
        # - 1 resolved-then-re-resolved (e2e-conf-open-001)
        # - 1 dismissed (e2e-conf-to-dismiss-004)
        # Total should be at least 4
        assert stats["total"] >= 4
        assert stats["by_status"]["resolved"] >= 2
        assert stats["by_status"]["dismissed"] >= 2

    def test_31_stats_have_all_severities(self, client: TestClient) -> None:
        """Stats include counts for all severity levels."""
        resp = client.get(f"{PREFIX}/conflicts/stats")
        stats = resp.json()["data"]["by_severity"]
        assert "high" in stats
        assert "medium" in stats
        assert "low" in stats


# ═══════════════════════════════════════════════════════════════════
# Phase 8: Routing Integrity
# ═══════════════════════════════════════════════════════════════════


class TestRoutingIntegrity:
    """Verify all conflict routes are registered at expected paths."""

    def test_32_all_conflict_routes_in_openapi(self, client: TestClient) -> None:
        """OpenAPI schema includes all expected conflict endpoints."""
        paths = client.get("/openapi.json").json().get("paths", {})

        assert f"{PREFIX}/conflicts" in paths
        assert f"{PREFIX}/conflicts/stats" in paths
        assert f"{PREFIX}/conflicts/{{conflict_id}}" in paths
        assert f"{PREFIX}/conflicts/{{conflict_id}}/resolve" in paths
        assert f"{PREFIX}/conflicts/{{conflict_id}}/dismiss" in paths
        assert f"{PREFIX}/conflicts/{{conflict_id}}/propagate" in paths
        assert f"{PREFIX}/conflicts/scan" in paths

    def test_33_route_methods_correct(self, client: TestClient) -> None:
        """All routes have correct HTTP methods."""
        paths = client.get("/openapi.json").json().get("paths", {})

        assert "get" in paths[f"{PREFIX}/conflicts"]
        assert "get" in paths[f"{PREFIX}/conflicts/{{conflict_id}}"]
        assert "post" in paths[f"{PREFIX}/conflicts/{{conflict_id}}/resolve"]
        assert "post" in paths[f"{PREFIX}/conflicts/{{conflict_id}}/dismiss"]
        assert "post" in paths[f"{PREFIX}/conflicts/{{conflict_id}}/propagate"]
        assert "post" in paths[f"{PREFIX}/conflicts/scan"]
