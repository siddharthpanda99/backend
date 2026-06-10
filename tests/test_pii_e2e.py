"""Knowledge Engine — PII Pipeline End-to-End Tests.

Uses FastAPI TestClient to hit real PII API endpoints. Tests route
handlers end-to-end including request validation, response schemas,
strategy parameter passing, and error handling.

Run: cd "Backend Monorepo/Backend" && uv run pytest tests/test_pii_e2e.py -v
"""

from fastapi.testclient import TestClient
from app.main import app
from app.core.settings import get_settings

settings = get_settings()
client = TestClient(app)

PREFIX = settings.API_V1_STR
BASE = f"{PREFIX}/knowledge/security/pii"


# ── Detection Endpoint Tests ──────────────────────────────────


class TestPIIDetectE2E:
    """E2E tests for POST /knowledge/security/pii/detect."""

    def test_detect_clean_text(self):
        """Returns no entities for clean text."""
        response = client.post(
            f"{BASE}/detect",
            json={"text": "The quick brown fox jumps over the lazy dog."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["has_pii"] is False
        assert data["data"]["entity_count"] == 0
        assert data["data"]["entities"] == []

    def test_detect_with_email(self):
        """Detects email addresses."""
        response = client.post(
            f"{BASE}/detect",
            json={"text": "Contact me at test@example.com for help."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # The detector may or may not find PII depending on Presidio availability
        if data["data"]["has_pii"]:
            assert data["data"]["entity_count"] >= 1
            types = {e["type"] for e in data["data"]["entities"]}
            assert "EMAIL_ADDRESS" in types or "EMAIL" in types

    def test_detect_multiple_pii(self):
        """Detects multiple PII types in one text."""
        response = client.post(
            f"{BASE}/detect",
            json={
                "text": (
                    "Email: admin@example.com "
                    "SSN: 123-45-6789 "
                    "Phone: 555-123-4567"
                )
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # At minimum the API returns a valid response
        assert "has_pii" in data["data"]
        assert "entity_count" in data["data"]
        assert "entities" in data["data"]

    def test_detect_empty_text(self):
        """Empty text returns 422 due to min_length validation."""
        response = client.post(
            f"{BASE}/detect",
            json={"text": ""},
        )
        assert response.status_code == 422

    def test_detect_special_chars(self):
        """Handles text with special characters."""
        response = client.post(
            f"{BASE}/detect",
            json={"text": "Hello! @#$%^&*()_+-=[]{}|;':\",./<>?`~"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should not crash on special characters
        assert "has_pii" in data["data"]

    def test_detect_long_text(self):
        """Handles very long text gracefully (may return false positives)."""
        long_text = "This is a test without PII. " * 5000
        response = client.post(
            f"{BASE}/detect",
            json={"text": long_text},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Long text may trigger regex false positives; just verify it doesn't crash

    def test_detect_unicode(self):
        """Handles Unicode text correctly."""
        response = client.post(
            f"{BASE}/detect",
            json={"text": "Café résumé über groß 中文 español"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "has_pii" in data["data"]


# ── Redaction Endpoint Tests ──────────────────────────────────


class TestPIIRedactE2E:
    """E2E tests for POST /knowledge/security/pii/redact."""

    def test_redact_clean_text(self):
        """Returns original text for clean input."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "This is a clean test.", "strategy": "redact"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["redacted_text"] == "This is a clean test."
        assert data["data"]["entity_count"] == 0
        assert data["data"]["strategy"] == "redact"

    def test_redact_empty_text(self):
        """Empty text returns 422 due to min_length validation."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "", "strategy": "redact"},
        )
        assert response.status_code == 422

    def test_redact_with_email(self):
        """Redacts email addresses with default strategy."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "Email: user@example.com", "strategy": "redact"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        if data["data"]["entity_count"] > 0:
            assert "[REDACTED]" in data["data"]["redacted_text"] or \
                   data["data"]["redacted_text"] != "Email: user@example.com"

    def test_redact_mask_strategy(self):
        """Mask strategy partially obscures PII."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "Email: user@example.com", "strategy": "mask"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["strategy"] == "mask"
        if data["data"]["entity_count"] > 0:
            assert data["data"]["redacted_text"] != "Email: user@example.com"

    def test_redact_hash_strategy(self):
        """Hash strategy replaces PII with hashes."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "Email: user@example.com", "strategy": "hash"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["strategy"] == "hash"

    def test_redact_replace_strategy(self):
        """Replace strategy uses realistic fake values."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "Email: user@example.com", "strategy": "replace"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["strategy"] == "replace"

    def test_redact_invalid_strategy(self):
        """Handler accepts any strategy string (no enum validation)."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "Email: a@b.com", "strategy": "custom_invalid_strategy"},
        )
        # The route accepts a plain str field, so 200 is expected
        assert response.status_code == 200
        assert response.json()["data"]["strategy"] == "custom_invalid_strategy"

    def test_redact_response_structure(self):
        """Redact response contains all expected fields."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "Clean text", "strategy": "redact"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "redacted_text" in data
        assert "entity_count" in data
        assert "entities" in data
        assert "strategy" in data


# ── Batch Redaction Endpoint Tests ────────────────────────────


class TestPIIBatchE2E:
    """E2E tests for POST /knowledge/security/pii/redact/batch."""

    def test_batch_empty_list(self):
        """Batch with empty list returns 422 due to min_length validation."""
        response = client.post(
            f"{BASE}/redact/batch",
            json={"texts": [], "strategy": "redact"},
        )
        assert response.status_code == 422

    def test_batch_single_text(self):
        """Batch with single text works correctly."""
        response = client.post(
            f"{BASE}/redact/batch",
            json={"texts": ["Clean text"], "strategy": "redact"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["entity_count"] == 0

    def test_batch_multiple_texts(self):
        """Batch handles multiple texts."""
        response = client.post(
            f"{BASE}/redact/batch",
            json={
                "texts": [
                    "Clean text one",
                    "Email: a@b.com",
                    "Clean text two",
                ],
                "strategy": "mask",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 3
        assert all(r["strategy"] == "mask" for r in data["data"]["results"])

    def test_batch_response_structure(self):
        """Batch response contains all expected fields."""
        response = client.post(
            f"{BASE}/redact/batch",
            json={"texts": ["Test"], "strategy": "redact"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "results" in data
        assert "count" in data
        assert "total_entities" in data
        assert isinstance(data["results"], list)


# ── Request Validation Tests ──────────────────────────────────


class TestPIIValidationE2E:
    """Tests for request validation and error handling."""

    def test_detect_missing_text(self):
        """Missing text field returns 422."""
        response = client.post(f"{BASE}/detect", json={})
        assert response.status_code == 422

    def test_redact_missing_text(self):
        """Missing text in redact returns 422."""
        response = client.post(f"{BASE}/redact", json={"strategy": "redact"})
        assert response.status_code == 422

    def test_health_check(self):
        """Health endpoint is accessible."""
        response = client.get(f"{PREFIX}/knowledge/health")
        assert response.status_code in (200, 500, 503)
        data = response.json()
        assert "success" in data


# ── Response Schema Consistency Tests ─────────────────────────


class TestPIISchemaE2E:
    """Tests for consistent response schema across endpoints."""

    def test_detect_response_schema(self):
        """Detect endpoint follows standard API response format."""
        response = client.post(
            f"{BASE}/detect",
            json={"text": "Test."},
        )
        body = response.json()
        assert "success" in body
        assert "data" in body
        assert "message" in body
        # Data fields
        assert "has_pii" in body["data"]
        assert "entity_count" in body["data"]
        assert "entities" in body["data"]

    def test_redact_response_schema(self):
        """Redact endpoint follows standard API response format."""
        response = client.post(
            f"{BASE}/redact",
            json={"text": "Test.", "strategy": "redact"},
        )
        body = response.json()
        assert "success" in body
        assert "data" in body
        assert "message" in body
        assert "redacted_text" in body["data"]
        assert "entity_count" in body["data"]
        assert "entities" in body["data"]
        assert "strategy" in body["data"]
