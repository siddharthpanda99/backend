"""
API-level tests for Knowledge Engine Security (PII) endpoints.

Tests all 7 security/PII endpoints by mocking:
- _get_pii_redactor() for PII detection/redaction endpoints
- get_pii_scan_history / get_pii_scan_stats / PIIScanHistoryService for scan history
"""

from __future__ import annotations

from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

# ── In-memory engine ───────────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)


def get_test_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


# ── Mock data ──────────────────────────────────────────────────────

SAMPLE_REDACT_RESULT: dict[str, Any] = {
    "redacted_text": "Contact [REDACTED] for more information.",
    "entity_count": 1,
    "entities": [
        {
            "type": "EMAIL_ADDRESS",
            "text": "john@example.com",
            "start": 11,
            "end": 26,
            "confidence": 0.99,
        }
    ],
    "strategy": "redact",
}

SAMPLE_DETECT_RESULT: dict[str, Any] = {
    "entity_count": 1,
    "entities": [
        {
            "type": "EMAIL_ADDRESS",
            "text": "john@example.com",
            "start": 11,
            "end": 26,
            "confidence": 0.99,
        }
    ],
}

SAMPLE_BATCH_RESULT: list[dict[str, Any]] = [
    SAMPLE_REDACT_RESULT,
    {
        "redacted_text": "Call [REDACTED] for support.",
        "entity_count": 1,
        "entities": [
            {
                "type": "PHONE_NUMBER",
                "text": "+1-555-123-4567",
                "start": 5,
                "end": 19,
                "confidence": 0.95,
            }
        ],
        "strategy": "redact",
    },
]

# Source module for scan history functions (routes use function-level imports)
SCAN_HISTORY_MODULE = "common_lib.modules.knowledge_engine.security.pii_scan_history"

SAMPLE_SCAN_RECORDS = [
    MagicMock(
        scan_id="scan-001",
        text_length=100,
        mode="detect",
        strategy=None,
        has_pii=True,
        entity_count=1,
        entity_type_counts={"EMAIL_ADDRESS": 1},
        batch_id=None,
        batch_line=None,
        source_filename=None,
        created_at=None,
    ),
    MagicMock(
        scan_id="scan-002",
        text_length=200,
        mode="redact",
        strategy="redact",
        has_pii=False,
        entity_count=0,
        entity_type_counts={},
        batch_id=None,
        batch_line=None,
        source_filename=None,
        created_at=None,
    ),
]

SAMPLE_SCAN_STATS: dict[str, Any] = {
    "total_scans": 10,
    "scans_with_pii": 3,
    "total_entities_detected": 5,
    "mode_breakdown": {"detect": 6, "redact": 4},
    "entity_type_breakdown": {
        "EMAIL_ADDRESS": 2,
        "PHONE_NUMBER": 2,
        "SSN": 1,
    },
}

ROUTES_MODULE = "app.modules.knowledge.routes"


# ── App fixture ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from app.modules.knowledge.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    from common_lib.modules.data_storage.database.connection import get_session
    app.dependency_overrides[get_session] = get_test_session
    return app


@pytest.fixture(scope="module")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _make_mock_redactor() -> MagicMock:
    """Create a mock KnowledgePIIRedactor."""
    mock = MagicMock()
    mock.redact.return_value = SAMPLE_REDACT_RESULT
    mock.detect.return_value = SAMPLE_DETECT_RESULT
    mock.batch_redact.return_value = SAMPLE_BATCH_RESULT
    return mock


# ═══════════════════════════════════════════════════════════════════
# PII Detection
# ═══════════════════════════════════════════════════════════════════


class TestDetectPII:
    """POST /security/pii/detect"""

    DETECT_PAYLOAD = {"text": "Contact john@example.com for more information."}

    def test_detect_pii(self, client: TestClient) -> None:
        mock_redactor = _make_mock_redactor()
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", return_value=mock_redactor):
            response = client.post("/api/v1/knowledge/security/pii/detect", json=self.DETECT_PAYLOAD)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["entity_count"] == 1
        assert len(body["data"]["entities"]) == 1
        assert "EMAIL_ADDRESS" in str(body["data"]["entities"])

    def test_detect_pii_no_pii(self, client: TestClient) -> None:
        mock_redactor = _make_mock_redactor()
        mock_redactor.detect.return_value = {"entity_count": 0, "entities": []}
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", return_value=mock_redactor):
            response = client.post("/api/v1/knowledge/security/pii/detect", json={"text": "Hello world, this is clean text."})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["entity_count"] == 0

    def test_detect_pii_missing_text(self, client: TestClient) -> None:
        response = client.post("/api/v1/knowledge/security/pii/detect", json={})
        assert response.status_code == 422

    def test_detect_pii_500_error(self, client: TestClient) -> None:
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", side_effect=Exception("Redactor init failed")):
            response = client.post("/api/v1/knowledge/security/pii/detect", json=self.DETECT_PAYLOAD)
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# PII Redaction
# ═══════════════════════════════════════════════════════════════════


class TestRedactPII:
    """POST /security/pii/redact"""

    REDACT_PAYLOAD = {"text": "Contact john@example.com for more information."}

    def test_redact_pii(self, client: TestClient) -> None:
        mock_redactor = _make_mock_redactor()
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", return_value=mock_redactor):
            response = client.post("/api/v1/knowledge/security/pii/redact", json=self.REDACT_PAYLOAD)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["entity_count"] == 1
        assert "[REDACTED]" in body["data"]["redacted_text"]

    def test_redact_pii_with_strategy(self, client: TestClient) -> None:
        mock_redactor = _make_mock_redactor()
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", return_value=mock_redactor):
            response = client.post(
                "/api/v1/knowledge/security/pii/redact",
                json={**self.REDACT_PAYLOAD, "strategy": "mask"},
            )
        assert response.status_code == 200
        mock_redactor.redact.assert_called_with(text=self.REDACT_PAYLOAD["text"], strategy="mask")

    def test_redact_pii_missing_text(self, client: TestClient) -> None:
        response = client.post("/api/v1/knowledge/security/pii/redact", json={})
        assert response.status_code == 422

    def test_redact_pii_500_error(self, client: TestClient) -> None:
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", side_effect=Exception("Redactor failed")):
            response = client.post("/api/v1/knowledge/security/pii/redact", json=self.REDACT_PAYLOAD)
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# Batch PII Redaction
# ═══════════════════════════════════════════════════════════════════


class TestBatchRedactPII:
    """POST /security/pii/redact/batch"""

    BATCH_PAYLOAD = {
        "texts": [
            "Contact john@example.com for more information.",
            "Call +1-555-123-4567 for support.",
        ],
    }

    def test_batch_redact_pii(self, client: TestClient) -> None:
        mock_redactor = _make_mock_redactor()
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", return_value=mock_redactor):
            response = client.post("/api/v1/knowledge/security/pii/redact/batch", json=self.BATCH_PAYLOAD)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["count"] == 2
        assert body["data"]["total_entities"] == 2

    def test_batch_redact_pii_empty_texts(self, client: TestClient) -> None:
        response = client.post("/api/v1/knowledge/security/pii/redact/batch", json={"texts": []})
        assert response.status_code == 422

    def test_batch_redact_pii_missing_texts(self, client: TestClient) -> None:
        response = client.post("/api/v1/knowledge/security/pii/redact/batch", json={})
        assert response.status_code == 422

    def test_batch_redact_pii_500_error(self, client: TestClient) -> None:
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", side_effect=Exception("Batch failed")):
            response = client.post("/api/v1/knowledge/security/pii/redact/batch", json=self.BATCH_PAYLOAD)
        assert response.status_code == 500

    def test_batch_redact_pii_delegation(self, client: TestClient) -> None:
        mock_redactor = _make_mock_redactor()
        with patch(f"{ROUTES_MODULE}._get_pii_redactor", return_value=mock_redactor):
            client.post(
                "/api/v1/knowledge/security/pii/redact/batch",
                json={**self.BATCH_PAYLOAD, "strategy": "mask"},
            )
        mock_redactor.batch_redact.assert_called_once()
        _, kwargs = mock_redactor.batch_redact.call_args
        assert len(kwargs.get("texts", [])) == 2
        assert kwargs.get("strategy") == "mask"


# ═══════════════════════════════════════════════════════════════════
# List PII Scans
# ═══════════════════════════════════════════════════════════════════


class TestListPIIScans:
    """GET /security/pii/scans"""

    def test_list_pii_scans(self, client: TestClient) -> None:
        with patch(f"{SCAN_HISTORY_MODULE}.get_pii_scan_history", return_value=(SAMPLE_SCAN_RECORDS, 2)):
            response = client.get("/api/v1/knowledge/security/pii/scans")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total"] == 2
        assert len(body["data"]["scans"]) == 2

    def test_list_pii_scans_empty(self, client: TestClient) -> None:
        with patch(f"{SCAN_HISTORY_MODULE}.get_pii_scan_history", return_value=([], 0)):
            response = client.get("/api/v1/knowledge/security/pii/scans")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] == 0
        assert len(body["data"]["scans"]) == 0

    def test_list_pii_scans_filtered(self, client: TestClient) -> None:
        with patch(f"{SCAN_HISTORY_MODULE}.get_pii_scan_history", return_value=(SAMPLE_SCAN_RECORDS, 2)) as mock_method:
            response = client.get("/api/v1/knowledge/security/pii/scans?mode=detect&has_pii=true")
        assert response.status_code == 200
        mock_method.assert_called_once()
        _, kwargs = mock_method.call_args
        assert kwargs.get("mode") == "detect"
        assert kwargs.get("has_pii") is True

    def test_list_pii_scans_500_error(self, client: TestClient) -> None:
        with patch(f"{SCAN_HISTORY_MODULE}.get_pii_scan_history", side_effect=Exception("DB error")):
            response = client.get("/api/v1/knowledge/security/pii/scans")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# Get PII Scan Stats
# ═══════════════════════════════════════════════════════════════════


class TestGetPIIScanStats:
    """GET /security/pii/scans/stats"""

    def test_get_pii_scan_stats(self, client: TestClient) -> None:
        with patch(f"{SCAN_HISTORY_MODULE}.get_pii_scan_stats", return_value=SAMPLE_SCAN_STATS):
            response = client.get("/api/v1/knowledge/security/pii/scans/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total_scans"] == 10
        assert body["data"]["scans_with_pii"] == 3

    def test_get_pii_scan_stats_500_error(self, client: TestClient) -> None:
        with patch(f"{SCAN_HISTORY_MODULE}.get_pii_scan_stats", side_effect=Exception("Stats failed")):
            response = client.get("/api/v1/knowledge/security/pii/scans/stats")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# Delete PII Scan
# ═══════════════════════════════════════════════════════════════════


class TestDeletePIIScan:
    """DELETE /security/pii/scans/{scan_id}"""

    def test_delete_pii_scan(self, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.delete_scan.return_value = True
        with patch(f"{SCAN_HISTORY_MODULE}.PIIScanHistoryService", return_value=mock_service):
            response = client.delete("/api/v1/knowledge/security/pii/scans/scan-001")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["scan_id"] == "scan-001"

    def test_delete_pii_scan_not_found(self, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.delete_scan.return_value = False
        with patch(f"{SCAN_HISTORY_MODULE}.PIIScanHistoryService", return_value=mock_service):
            response = client.delete("/api/v1/knowledge/security/pii/scans/scan-nonexistent")
        assert response.status_code == 404

    def test_delete_pii_scan_500_error(self, client: TestClient) -> None:
        with patch(f"{SCAN_HISTORY_MODULE}.PIIScanHistoryService", side_effect=Exception("Service error")):
            response = client.delete("/api/v1/knowledge/security/pii/scans/scan-001")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# Clear PII Scan History
# ═══════════════════════════════════════════════════════════════════


class TestClearPIIScanHistory:
    """DELETE /security/pii/scans"""

    def test_clear_pii_scan_history(self, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.clear_history.return_value = 5
        with patch(f"{SCAN_HISTORY_MODULE}.PIIScanHistoryService", return_value=mock_service):
            response = client.delete("/api/v1/knowledge/security/pii/scans")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["deleted"] == 5

    def test_clear_pii_scan_history_empty(self, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.clear_history.return_value = 0
        with patch(f"{SCAN_HISTORY_MODULE}.PIIScanHistoryService", return_value=mock_service):
            response = client.delete("/api/v1/knowledge/security/pii/scans")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["deleted"] == 0

    def test_clear_pii_scan_history_500_error(self, client: TestClient) -> None:
        with patch(f"{SCAN_HISTORY_MODULE}.PIIScanHistoryService", side_effect=Exception("Clear failed")):
            response = client.delete("/api/v1/knowledge/security/pii/scans")
        assert response.status_code == 500


# ═══════════════════════════════════════════════════════════════════
# Routing Integrity
# ═══════════════════════════════════════════════════════════════════


class TestSecurityRoutingIntegrity:
    """Verify all security/PII routes are mounted at expected paths."""

    def test_security_routes_in_openapi(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        security_paths = {path for path in paths if "/security/" in path}
        # 5 unique path patterns: /security/pii/detect, /security/pii/redact,
        # /security/pii/redact/batch, /security/pii/scans, /security/pii/scans/stats,
        # /security/pii/scans/{scan_id}
        assert len(security_paths) >= 5

    def test_security_methods(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        paths = response.json().get("paths", {})
        all_security_paths = [p for p in paths if "/security/" in p]

        # Check specific endpoints exist
        detect_paths = [p for p in all_security_paths if "/detect" in p]
        redact_paths = [p for p in all_security_paths if "/redact" in p and "/batch" not in p]
        batch_paths = [p for p in all_security_paths if "/batch" in p]
        scans_list_paths = [p for p in all_security_paths if p.endswith("/scans")]
        stats_paths = [p for p in all_security_paths if "/stats" in p]
        assert detect_paths
        assert redact_paths
        assert batch_paths
        assert scans_list_paths
        assert stats_paths
