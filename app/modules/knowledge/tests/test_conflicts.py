"""
API-level tests for Knowledge Conflict endpoints.

Tests both DB-dependent queries and service-delegated operations.

DB-dependent endpoints (real in-memory SQLite):
    GET  /knowledge/conflicts                      — List conflicts
    GET  /knowledge/conflicts/stats                — Conflict statistics
    GET  /knowledge/conflicts/{conflict_id}         — Get single conflict

Service-delegated endpoints (mocked KBConflictService):
    POST /knowledge/conflicts/{conflict_id}/resolve  — Resolve conflict
    POST /knowledge/conflicts/{conflict_id}/dismiss  — Dismiss conflict
    POST /knowledge/conflicts/{conflict_id}/propagate — Propagate resolution
    POST /knowledge/conflicts/scan                   — Full conflict scan

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/knowledge/tests/test_conflicts.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.modules.knowledge.routes import router as knowledge_router
from common_lib.modules.knowledge_engine.knowledge_hub.models import ConflictRecord

# ── In-memory SQLite engine ────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SQLModel.metadata.create_all(engine)

# ── Sample data ────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc).replace(tzinfo=None)

SEED_CONFLICT_1 = {
    "id": "conf-001",
    "chunk_a_id": "chunk-a-001",
    "chunk_b_id": "chunk-b-001",
    "conflict_type": "direct_contradiction",
    "severity": "high",
    "domain": "financial",
    "status": "open",
    "chunk_a_content_preview": "Revenue grew 20% in Q1",
    "chunk_b_content_preview": "Revenue declined 5% in Q1",
    "chunk_a_source": "src-finance-001",
    "chunk_b_source": "src-finance-002",
    "chunk_a_confidence": 0.95,
    "chunk_b_confidence": 0.88,
    "similarity_score": 0.85,
    "detected_at": _NOW,
    "updated_at": _NOW,
}

SEED_CONFLICT_2 = {
    "id": "conf-002",
    "chunk_a_id": "chunk-a-002",
    "chunk_b_id": "chunk-b-002",
    "conflict_type": "temporal",
    "severity": "medium",
    "domain": "news",
    "status": "resolved",
    "chunk_a_content_preview": "Event occurred on Monday",
    "chunk_b_content_preview": "Event occurred on Tuesday",
    "chunk_a_source": "src-news-001",
    "chunk_b_source": "src-news-002",
    "chunk_a_confidence": 0.90,
    "chunk_b_confidence": 0.85,
    "similarity_score": 0.75,
    "winner_chunk_id": "chunk-a-002",
    "loser_chunk_id": "chunk-b-002",
    "rationale": "Monday is the correct date",
    "resolution_strategy": "human_arbitration",
    "resolved_by": "admin",
    "detected_at": _NOW,
    "updated_at": _NOW,
}

SEED_CONFLICT_3 = {
    "id": "conf-003",
    "chunk_a_id": "chunk-a-003",
    "chunk_b_id": "chunk-b-003",
    "conflict_type": "cross_source",
    "severity": "low",
    "domain": "general",
    "status": "dismissed",
    "chunk_a_content_preview": "Some content A",
    "chunk_b_content_preview": "Different content B",
    "chunk_a_source": "src-gen-001",
    "chunk_b_source": "src-gen-002",
    "chunk_a_confidence": 0.70,
    "chunk_b_confidence": 0.65,
    "similarity_score": 0.45,
    "detected_at": _NOW,
    "updated_at": _NOW,
}

# ── Seed the test DB ────────────────────────────────────────────────


def seed_test_conflicts(session: Session) -> list[ConflictRecord]:
    """Insert sample conflicts and return them."""
    conflicts = []
    for data in [SEED_CONFLICT_1, SEED_CONFLICT_2, SEED_CONFLICT_3]:
        rec = ConflictRecord(**data)
        session.add(rec)
        conflicts.append(rec)
    session.commit()
    for c in conflicts:
        session.refresh(c)
    return conflicts


with Session(engine) as _session:
    existing = _session.exec(select(ConflictRecord).limit(1)).first()
    if not existing:
        seed_test_conflicts(_session)


def get_test_session() -> Generator[Session, None, None]:
    """Yield a session connected to the in-memory test DB."""
    with Session(engine) as session:
        yield session


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    """Create a sync TestClient with the Knowledge router and overridden session."""
    app = FastAPI()
    app.include_router(knowledge_router, prefix="/api/v1")

    from common_lib.modules.data_storage.database.connection import get_session
    app.dependency_overrides[get_session] = get_test_session

    return TestClient(app)


@pytest.fixture
def mock_conflict_service() -> MagicMock:
    """Return a mock KBConflictService with default returns."""
    svc = MagicMock()

    # resolve returns a ConflictRecord
    svc.resolve = MagicMock(
        return_value=ConflictRecord(**{
            **SEED_CONFLICT_1,
            "status": "resolved",
            "winner_chunk_id": "chunk-a-001",
            "loser_chunk_id": "chunk-b-001",
            "rationale": "Higher confidence",
            "resolution_strategy": "confidence",
            "resolved_by": "system",
            "updated_at": _NOW,
        })
    )

    # dismiss returns a ConflictRecord
    svc.dismiss = MagicMock(
        return_value=ConflictRecord(**{
            **SEED_CONFLICT_1,
            "status": "dismissed",
            "updated_at": _NOW,
        })
    )

    # propagate returns a ConflictRecord with propagated_to
    svc.propagate = MagicMock(
        return_value=ConflictRecord(**{
            **SEED_CONFLICT_1,
            "status": "resolved",
            "propagated_to": ["chunk-c-001", "chunk-c-002"],
            "updated_at": _NOW,
        })
    )

    # scan_all returns a list of ConflictRecords
    svc.scan_all = MagicMock(
        return_value=[
            ConflictRecord(**{
                **SEED_CONFLICT_1,
                "id": "conf-scan-001",
                "chunk_a_id": "new-a",
                "chunk_b_id": "new-b",
                "detected_at": _NOW,
                "updated_at": _NOW,
            })
        ]
    )

    # get_stats returns a dict
    svc.get_stats = MagicMock(
        return_value={
            "total": 3,
            "by_status": {"open": 1, "resolved": 1, "dismissed": 1},
            "by_severity": {"high": 1, "medium": 1, "low": 1},
        }
    )

    return svc


# ═══════════════════════════════════════════════════════════════════════
# GET /knowledge/conflicts — List conflicts
# ═══════════════════════════════════════════════════════════════════════


class TestListConflicts:
    """GET /api/v1/knowledge/conflicts — list knowledge conflicts."""

    def test_list_all_conflicts(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total"] == 3
        assert len(body["data"]["conflicts"]) == 3

    def test_list_conflicts_has_required_fields(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts")
        conflict = response.json()["data"]["conflicts"][0]
        assert "id" in conflict
        assert "chunk_a_id" in conflict
        assert "chunk_b_id" in conflict
        assert "conflict_type" in conflict
        assert "severity" in conflict
        assert "domain" in conflict
        assert "status" in conflict
        assert "detected_at" in conflict

    def test_list_conflicts_filter_by_status(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts?status=open")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 1
        assert all(c["status"] == "open" for c in body["data"]["conflicts"])

    def test_list_conflicts_filter_by_severity(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts?severity=high")
        assert response.status_code == 200
        assert all(c["severity"] == "high" for c in response.json()["data"]["conflicts"])

    def test_list_conflicts_filter_by_domain(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts?domain=news")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 1
        assert body["data"]["conflicts"][0]["domain"] == "news"

    def test_list_conflicts_filter_by_source_id(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts?source_id=src-finance-001")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 1

    def test_list_conflicts_pagination(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts?limit=2&offset=0")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]["conflicts"]) == 2
        assert body["data"]["limit"] == 2
        assert body["data"]["offset"] == 0

    def test_list_conflicts_filter_no_results(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts?status=escalated")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 0
        assert body["data"]["conflicts"] == []


# ═══════════════════════════════════════════════════════════════════════
# GET /knowledge/conflicts/stats — Conflict stats
# ═══════════════════════════════════════════════════════════════════════


class TestConflictStats:
    """GET /api/v1/knowledge/conflicts/stats — conflict statistics."""

    MODULE_PATH = "app.modules.knowledge.routes._get_conflict_service"

    def test_stats_returns_counts(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.get("/api/v1/knowledge/conflicts/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total"] == 3
        assert body["data"]["by_status"]["open"] == 1

    def test_stats_delegates(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service) as mock_getter:
            client.get("/api/v1/knowledge/conflicts/stats")
            mock_getter.assert_called_once()
            mock_conflict_service.get_stats.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# GET /knowledge/conflicts/{conflict_id} — Get single conflict
# ═══════════════════════════════════════════════════════════════════════


class TestGetConflict:
    """GET /api/v1/knowledge/conflicts/{conflict_id} — get a single conflict."""

    def test_get_conflict_returns_conflict(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts/conf-001")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["id"] == "conf-001"
        assert body["data"]["chunk_a_id"] == "chunk-a-001"
        assert body["data"]["chunk_b_id"] == "chunk-b-001"

    def test_get_conflict_includes_preview(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts/conf-001")
        data = response.json()["data"]
        assert "Revenue grew" in data["chunk_a_content_preview"]
        assert "Revenue declined" in data["chunk_b_content_preview"]

    def test_get_conflict_includes_metadata(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts/conf-002")
        data = response.json()["data"]
        assert data["status"] == "resolved"
        assert data["winner_chunk_id"] == "chunk-a-002"
        assert data["rationale"] == "Monday is the correct date"

    def test_get_conflict_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/knowledge/conflicts/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════
# POST /knowledge/conflicts/{conflict_id}/resolve — Resolve conflict
# ═══════════════════════════════════════════════════════════════════════


class TestResolveConflict:
    """POST /api/v1/knowledge/conflicts/{conflict_id}/resolve — resolve a conflict."""

    MODULE_PATH = "app.modules.knowledge.routes._get_conflict_service"

    RESOLVE_PAYLOAD = {
        "winner_chunk_id": "chunk-a-001",
        "rationale": "Higher confidence score",
        "resolved_by": "test",
        "strategy": "confidence",
        "force": False,
    }

    def test_resolve_returns_success(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post(
                "/api/v1/knowledge/conflicts/conf-001/resolve",
                json=self.RESOLVE_PAYLOAD,
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "resolved"
        assert "resolved" in body["message"]

    def test_resolve_delegates(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service) as mock_getter:
            client.post(
                "/api/v1/knowledge/conflicts/conf-001/resolve",
                json=self.RESOLVE_PAYLOAD,
            )
            mock_getter.assert_called_once()
            mock_conflict_service.resolve.assert_called_once()

    def test_resolve_missing_winner_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/knowledge/conflicts/conf-001/resolve",
            json={"rationale": "Missing winner"},
        )
        assert response.status_code == 422

    def test_resolve_returns_500_on_error(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        mock_conflict_service.resolve = MagicMock(
            side_effect=ValueError("Conflict already resolved")
        )
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post(
                "/api/v1/knowledge/conflicts/conf-001/resolve",
                json=self.RESOLVE_PAYLOAD,
            )
        assert response.status_code == 400
        assert "already" in response.json()["detail"]

    def test_resolve_delegates_params(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            client.post(
                "/api/v1/knowledge/conflicts/conf-001/resolve",
                json=self.RESOLVE_PAYLOAD,
            )
        _args, kwargs = mock_conflict_service.resolve.call_args
        assert kwargs.get("winner_chunk_id") == "chunk-a-001"
        assert kwargs.get("rationale") == "Higher confidence score"
        assert kwargs.get("strategy") == "confidence"
        assert kwargs.get("force") is False


# ═══════════════════════════════════════════════════════════════════════
# POST /knowledge/conflicts/{conflict_id}/dismiss — Dismiss conflict
# ═══════════════════════════════════════════════════════════════════════


class TestDismissConflict:
    """POST /api/v1/knowledge/conflicts/{conflict_id}/dismiss — dismiss a conflict."""

    MODULE_PATH = "app.modules.knowledge.routes._get_conflict_service"

    def test_dismiss_returns_success(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post(
                "/api/v1/knowledge/conflicts/conf-001/dismiss",
                json={"reason": "False positive", "dismissed_by": "test"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "dismissed"
        assert "dismissed" in body["message"]

    def test_dismiss_delegates(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service) as mock_getter:
            client.post(
                "/api/v1/knowledge/conflicts/conf-001/dismiss",
                json={"reason": "No issue", "dismissed_by": "test"},
            )
            mock_getter.assert_called_once()
            mock_conflict_service.dismiss.assert_called_once()

    def test_dismiss_delegates_params(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            client.post(
                "/api/v1/knowledge/conflicts/conf-001/dismiss",
                json={"reason": "Duplicate", "dismissed_by": "admin"},
            )
        _args, kwargs = mock_conflict_service.dismiss.call_args
        assert kwargs.get("reason") == "Duplicate"
        assert kwargs.get("dismissed_by") == "admin"

    def test_dismiss_returns_500_on_error(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        mock_conflict_service.dismiss = MagicMock(
            side_effect=ValueError("Conflict already dismissed")
        )
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post(
                "/api/v1/knowledge/conflicts/conf-001/dismiss",
                json={"reason": "N/A"},
            )
        assert response.status_code == 400
        assert "already" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════
# POST /knowledge/conflicts/{conflict_id}/propagate — Propagate resolution
# ═══════════════════════════════════════════════════════════════════════


class TestPropagateConflict:
    """POST /api/v1/knowledge/conflicts/{conflict_id}/propagate — propagate resolution."""

    MODULE_PATH = "app.modules.knowledge.routes._get_conflict_service"

    def test_propagate_returns_success(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post(
                "/api/v1/knowledge/conflicts/conf-001/propagate",
                json={},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "propagated" in body["message"]
        assert len(body["data"]["propagated_to"]) == 2

    def test_propagate_with_target_ids(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post(
                "/api/v1/knowledge/conflicts/conf-001/propagate",
                json={"target_chunk_ids": ["chunk-x-001"]},
            )
        assert response.status_code == 200
        _args, kwargs = mock_conflict_service.propagate.call_args
        assert kwargs.get("target_chunk_ids") == ["chunk-x-001"]

    def test_propagate_delegates(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service) as mock_getter:
            client.post(
                "/api/v1/knowledge/conflicts/conf-001/propagate",
                json={},
            )
            mock_getter.assert_called_once()
            mock_conflict_service.propagate.assert_called_once()

    def test_propagate_returns_500_on_error(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        mock_conflict_service.propagate = MagicMock(
            side_effect=ValueError("Propagation failed")
        )
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post(
                "/api/v1/knowledge/conflicts/conf-001/propagate",
                json={},
            )
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# POST /knowledge/conflicts/scan — Full conflict scan
# ═══════════════════════════════════════════════════════════════════════


class TestConflictScan:
    """POST /api/v1/knowledge/conflicts/scan — run a full conflict scan."""

    MODULE_PATH = "app.modules.knowledge.routes._get_conflict_service"

    def test_scan_returns_new_conflicts(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post("/api/v1/knowledge/conflicts/scan", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]["new_conflicts"]) == 1
        assert body["data"]["count"] == 1
        assert "Scanned" in body["message"]

    def test_scan_with_params(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = client.post(
                "/api/v1/knowledge/conflicts/scan?source_id=src-test&limit=100",
                json={},
            )
        assert response.status_code == 200
        _args, kwargs = mock_conflict_service.scan_all.call_args
        assert kwargs.get("source_id") == "src-test"
        assert kwargs.get("limit") == 100

    def test_scan_returns_500_on_error(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        mock_conflict_service.scan_all = MagicMock(
            side_effect=Exception("Scan failed")
        )
        # Use a TestClient that doesn't re-raise server exceptions
        app = FastAPI()
        from app.modules.knowledge.routes import router as knowledge_router
        app.include_router(knowledge_router, prefix="/api/v1")
        from common_lib.modules.data_storage.database.connection import get_session
        app.dependency_overrides[get_session] = get_test_session
        quiet_client = TestClient(app, raise_server_exceptions=False)
        with patch(self.MODULE_PATH, return_value=mock_conflict_service):
            response = quiet_client.post("/api/v1/knowledge/conflicts/scan", json={})
        assert response.status_code == 500

    def test_scan_without_source_id(self, client: TestClient, mock_conflict_service: MagicMock) -> None:
        with patch(self.MODULE_PATH, return_value=mock_conflict_service) as mock_getter:
            response = client.post("/api/v1/knowledge/conflicts/scan", json={})
        assert response.status_code == 200
        mock_getter.assert_called_once()
        mock_conflict_service.scan_all.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# Routing integrity
# ═══════════════════════════════════════════════════════════════════════


class TestConflictsRoutingIntegrity:
    """Verify all conflict routes are registered at expected paths."""

    def test_all_conflict_routes_in_openapi(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})

        assert "/api/v1/knowledge/conflicts" in paths
        assert "/api/v1/knowledge/conflicts/stats" in paths
        assert "/api/v1/knowledge/conflicts/{conflict_id}" in paths
        assert "/api/v1/knowledge/conflicts/{conflict_id}/resolve" in paths
        assert "/api/v1/knowledge/conflicts/{conflict_id}/dismiss" in paths
        assert "/api/v1/knowledge/conflicts/{conflict_id}/propagate" in paths
        assert "/api/v1/knowledge/conflicts/scan" in paths

    def test_conflict_routes_have_correct_methods(self, client: TestClient) -> None:
        paths = client.get("/openapi.json").json().get("paths", {})

        conflicts_list = paths["/api/v1/knowledge/conflicts"]
        assert "get" in conflicts_list

        conflict_id = paths["/api/v1/knowledge/conflicts/{conflict_id}"]
        assert "get" in conflict_id

        resolve = paths["/api/v1/knowledge/conflicts/{conflict_id}/resolve"]
        assert "post" in resolve

        dismiss = paths["/api/v1/knowledge/conflicts/{conflict_id}/dismiss"]
        assert "post" in dismiss

        propagate = paths["/api/v1/knowledge/conflicts/{conflict_id}/propagate"]
        assert "post" in propagate

        scan = paths["/api/v1/knowledge/conflicts/scan"]
        assert "post" in scan
