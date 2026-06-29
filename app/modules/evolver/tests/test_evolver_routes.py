"""Integration tests for Evolver REST endpoints.

Tests all 14 endpoints under /api/v1/evolver/ using FastAPI TestClient
with fully mocked services. No real DB, no LLM calls.

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/evolver/tests/ -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.evolver.routes.router import router as evolver_router

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_ANALYZE = {
    "patterns_detected": ["repetition_loop", "no_progress"],
    "severity": "high",
    "summary": "Agent is repeating the same action without progress",
    "healing_applied": False,
    "healing_actions": [],
}

SAMPLE_GENE = {
    "id": "g1",
    "gene_id": "gene_retry_on_error",
    "name": "Retry on Error",
    "description": "Retry failed operations up to 3 times",
    "trigger_pattern": ".*error.*",
    "min_repetitions": 1,
    "max_uses": 10,
    "effect_type": "system_prompt_append",
    "effect_content": "If you encounter an error, retry up to 3 times.",
    "is_active": True,
    "applied_count": 0,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

SAMPLE_AUDIT_ENTRY = {
    "id": "a1",
    "session_id": "session_123",
    "level": "info",
    "category": "execution",
    "message": "Tool call completed",
    "details": "",
    "agent_id": "agent_1",
    "tool_name": "search",
    "created_at": datetime.now(timezone.utc).isoformat(),
}

SAMPLE_MAILBOX_MSG = {
    "id": "m1",
    "message_type": "tool_execution",
    "source": "agent_1",
    "target": "tool_search",
    "payload": {"query": "test"},
    "priority": "normal",
    "status": "pending",
    "created_at": datetime.now(timezone.utc).isoformat(),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_failure_analyzer() -> MagicMock:
    """Mock FailureAnalyzer with known return values."""
    fa = MagicMock()
    result = MagicMock()
    result.patterns = [
        SimpleNamespace(name="repetition_loop"),
        SimpleNamespace(name="no_progress"),
    ]
    result.severity = "high"
    result.summary = "Agent is repeating the same action without progress"
    fa.analyze.return_value = result
    return fa


@pytest.fixture
def mock_gene_service() -> MagicMock:
    """Mock GeneRecordService with known return values."""
    svc = MagicMock()
    svc.list_all.return_value = [MagicMock(model_dump=lambda: SAMPLE_GENE)]
    svc.get_by_gene_id.return_value = MagicMock(model_dump=lambda: SAMPLE_GENE, id="g1")
    svc.create.return_value = MagicMock(model_dump=lambda: SAMPLE_GENE)
    svc.update.return_value = MagicMock(
        model_dump=lambda: {**SAMPLE_GENE, "name": "Updated"}
    )
    svc.delete.return_value = True
    return svc


@pytest.fixture
def mock_reflection_service() -> MagicMock:
    """Mock ReflectionResultService with known return values."""
    svc = MagicMock()
    svc.list_by_session.return_value = [
        MagicMock(model_dump=lambda: {"id": "r1", "session_id": "session_123"})
    ]
    return svc


@pytest.fixture
def mock_audit_service() -> MagicMock:
    """Mock AuditEntryService with known return values."""
    svc = MagicMock()
    svc.create.return_value = MagicMock(model_dump=lambda: SAMPLE_AUDIT_ENTRY)
    svc.list_by_session.return_value = [
        MagicMock(model_dump=lambda: SAMPLE_AUDIT_ENTRY)
    ]
    svc.delete_by_session.return_value = 3
    return svc


@pytest.fixture
def mock_mailbox_service() -> MagicMock:
    """Mock MailboxService with known return values."""
    mbox = MagicMock()
    msg = MagicMock()
    msg.id = "m1"
    msg.status = MagicMock()
    msg.status.value = "pending"
    msg.type = "tool_execution"
    msg.payload = {"query": "test"}
    mbox.post.return_value = msg
    mbox.poll.return_value = [msg]
    mbox.get_stats.return_value = {"pending": 1, "total": 5}

    return mbox


@pytest.fixture
def client(
    mock_failure_analyzer: MagicMock,
    mock_gene_service: MagicMock,
    mock_reflection_service: MagicMock,
    mock_audit_service: MagicMock,
    mock_mailbox_service: MagicMock,
) -> TestClient:
    """Create a TestClient with mocked services."""
    app = FastAPI()
    app.include_router(evolver_router, prefix="/api/v1/evolver")

    patchers = [
        patch(
            "common_lib.modules.knowledge_engine.learning.evolver.FailureAnalyzer",
            return_value=mock_failure_analyzer,
        ),
        patch(
            "common_lib.modules.knowledge_engine.learning.evolver.db_service.GeneRecordService",
            return_value=mock_gene_service,
        ),
        patch(
            "common_lib.modules.knowledge_engine.learning.evolver.db_service.ReflectionResultService",
            return_value=mock_reflection_service,
        ),
        patch(
            "common_lib.modules.knowledge_engine.learning.evolver.db_service.AuditEntryService",
            return_value=mock_audit_service,
        ),
        patch(
            "common_lib.modules.knowledge_engine.learning.evolver.get_mailbox_service",
            return_value=mock_mailbox_service,
        ),
    ]

    for p in patchers:
        p.start()

    with TestClient(app) as c:
        yield c

    for p in patchers:
        p.stop()


# ---------------------------------------------------------------------------
# Analyzer Endpoints
# ---------------------------------------------------------------------------


class TestAnalyzerEndpoints:
    """POST /evolver/analyze, GET /evolver/analyze/history/{session_id}"""

    def test_analyze_execution(self, client: TestClient):
        response = client.post(
            "/api/v1/evolver/analyze",
            json={
                "messages": [
                    {"role": "user", "content": "search for cats"},
                    {"role": "assistant", "content": "searching..."},
                ],
                "session_id": "session_123",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert "repetition_loop" in body["data"]["patterns_detected"]
        assert body["data"]["severity"] == "high"

    def test_analyze_missing_messages_returns_422(self, client: TestClient):
        response = client.post("/api/v1/evolver/analyze", json={})
        assert response.status_code == 422

    def test_analyze_history(self, client: TestClient):
        response = client.get("/api/v1/evolver/analyze/history/session_123")
        assert response.status_code == 200
        body = response.json()
        assert body["data"][0]["session_id"] == "session_123"


# ---------------------------------------------------------------------------
# Gene Endpoints
# ---------------------------------------------------------------------------


class TestGeneEndpoints:
    """CRUD for gene definitions."""

    def test_list_genes(self, client: TestClient):
        response = client.get("/api/v1/evolver/genes")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["gene_id"] == "gene_retry_on_error"

    def test_list_genes_with_active_filter(self, client: TestClient):
        response = client.get("/api/v1/evolver/genes?active_only=true")
        assert response.status_code == 200

    def test_get_gene(self, client: TestClient):
        response = client.get("/api/v1/evolver/genes/gene_retry_on_error")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["gene_id"] == "gene_retry_on_error"

    def test_get_gene_not_found(self, client: TestClient):
        # Override the mock to return None
        from unittest.mock import MagicMock

        client.app.dependency_overrides = {}

        with patch(
            "common_lib.modules.knowledge_engine.learning.evolver.db_service.GeneRecordService"
        ) as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_by_gene_id.return_value = None
            mock_svc_cls.return_value = mock_svc
            response = client.get("/api/v1/evolver/genes/nonexistent")
        assert response.status_code == 404

    def test_create_gene(self, client: TestClient):
        response = client.post(
            "/api/v1/evolver/genes",
            json={
                "gene_id": "gene_new",
                "name": "New Gene",
                "description": "A test gene",
                "effect_type": "system_prompt_append",
                "effect_content": "Be careful.",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["gene_id"] == "gene_retry_on_error"

    def test_create_gene_missing_required_returns_422(self, client: TestClient):
        response = client.post(
            "/api/v1/evolver/genes", json={"name": "Missing gene_id"}
        )
        assert response.status_code == 422

    def test_update_gene(self, client: TestClient):
        response = client.put(
            "/api/v1/evolver/genes/gene_retry_on_error",
            json={"name": "Updated"},
        )
        assert response.status_code == 200

    def test_delete_gene(self, client: TestClient):
        response = client.delete("/api/v1/evolver/genes/gene_retry_on_error")
        assert response.status_code == 200
        assert response.json()["message"] == "Gene deleted"


# ---------------------------------------------------------------------------
# Audit Endpoints
# ---------------------------------------------------------------------------


class TestAuditEndpoints:
    """Audit log CRUD."""

    def test_create_audit_entry(self, client: TestClient):
        response = client.post(
            "/api/v1/evolver/audit",
            json={
                "session_id": "session_123",
                "level": "info",
                "category": "execution",
                "message": "Tool call completed",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["session_id"] == "session_123"

    def test_create_audit_missing_required_returns_422(self, client: TestClient):
        response = client.post("/api/v1/evolver/audit", json={"level": "info"})
        assert response.status_code == 422

    def test_get_audit_log(self, client: TestClient):
        response = client.get("/api/v1/evolver/audit/session_123")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["session_id"] == "session_123"

    def test_get_audit_log_with_filters(self, client: TestClient):
        response = client.get(
            "/api/v1/evolver/audit/session_123?level=info&category=execution"
        )
        assert response.status_code == 200

    def test_clear_audit_log(self, client: TestClient):
        response = client.delete("/api/v1/evolver/audit/session_123")
        assert response.status_code == 200
        assert "Deleted" in response.json()["message"]


# ---------------------------------------------------------------------------
# Mailbox Endpoints
# ---------------------------------------------------------------------------


class TestMailboxEndpoints:
    """Proxy mailbox operations."""

    def test_post_message(self, client: TestClient):
        response = client.post(
            "/api/v1/evolver/mailbox",
            json={
                "message_type": "tool_execution",
                "source": "agent_1",
                "target": "tool_search",
                "payload": {"query": "test"},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["message_id"] == "m1"
        assert body["data"]["status"] == "pending"

    def test_post_message_missing_returns_200_with_defaults(self, client: TestClient):
        response = client.post("/api/v1/evolver/mailbox", json={})
        assert response.status_code == 200

    def test_poll_pending(self, client: TestClient):
        response = client.get("/api/v1/evolver/mailbox/pending")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == "m1"

    def test_poll_pending_with_type_filter(self, client: TestClient):
        response = client.get(
            "/api/v1/evolver/mailbox/pending?message_type=tool_execution"
        )
        assert response.status_code == 200

    def test_acknowledge_message(self, client: TestClient):
        response = client.put(
            "/api/v1/evolver/mailbox/m1",
            json={"status": "completed", "result": {"success": True}},
        )
        assert response.status_code == 200
        assert "completed" in response.json()["message"]

    def test_nack_message(self, client: TestClient):
        response = client.put(
            "/api/v1/evolver/mailbox/m1",
            json={"status": "failed", "error": "Timeout"},
        )
        assert response.status_code == 200
        assert "failed" in response.json()["message"]

    def test_invalid_status_returns_400(self, client: TestClient):
        response = client.put(
            "/api/v1/evolver/mailbox/m1",
            json={"status": "invalid_status"},
        )
        assert response.status_code == 400

    def test_get_mailbox_stats(self, client: TestClient):
        response = client.get("/api/v1/evolver/mailbox/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["pending"] == 1
        assert body["data"]["total"] == 5


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify 500 responses when service methods raise exceptions."""

    def test_analyze_error(self, client: TestClient, mock_failure_analyzer: MagicMock):
        mock_failure_analyzer.analyze.side_effect = RuntimeError("Analysis failed")
        response = client.post(
            "/api/v1/evolver/analyze",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert response.status_code == 500
        assert "Analysis failed" in response.json()["detail"]

    def test_gene_list_error(self, client: TestClient):
        with patch(
            "common_lib.modules.knowledge_engine.learning.evolver.db_service.GeneRecordService"
        ) as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_all.side_effect = RuntimeError("DB error")
            mock_svc_cls.return_value = mock_svc
            response = client.get("/api/v1/evolver/genes")
        assert response.status_code == 500
        assert "DB error" in response.json()["detail"]
