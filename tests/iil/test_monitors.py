"""IIL Monitors — Integration Tests.

Tests the full CRUD lifecycle for /monitors endpoints with mocked MonitorService.

Usage:
    cd "Backend Monorepo/Backend"
    uv run pytest tests/iil/test_monitors.py -v
"""

import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# Monitor Service Mock Helper
# =============================================================================

def _mock_monitor_service():
    """Create a mock MonitorService with all methods stubbed."""
    svc = MagicMock()
    svc.list_targets.return_value = {
        "targets": [],
        "total": 0,
    }
    svc.get_target.return_value = {
        "id": "mon_123",
        "name": "Test Monitor",
        "target_type": "url",
        "target_url": "http://example.com",
        "enabled": True,
    }
    svc.create_target.return_value = {
        "id": "mon_456",
        "name": "New Monitor",
        "target_type": "url",
        "target_url": "http://new.com",
        "enabled": True,
    }
    svc.update_target.return_value = {
        "id": "mon_123",
        "name": "Updated Monitor",
        "target_type": "url",
        "target_url": "http://updated.com",
        "enabled": True,
    }
    svc.delete_target.return_value = {"deleted": True, "id": "mon_123"}
    svc.check_target.return_value = {
        "target_id": "mon_123",
        "changed": False,
        "checked_at": "2026-07-19T10:00:00Z",
    }
    svc.check_all_due.return_value = []
    return svc


# =============================================================================
# GET /monitors Endpoint Tests
# =============================================================================


class TestListMonitorsEndpoint:
    """Tests for GET /api/v1/iil/monitors"""

    def test_list_monitors_success(self, client):
        """List monitors returns targets list."""
        svc = _mock_monitor_service()
        svc.list_targets.return_value = {
            "targets": [
                {"id": "mon_1", "name": "Site A", "target_url": "http://a.com"},
                {"id": "mon_2", "name": "Site B", "target_url": "http://b.com"},
            ],
            "total": 2,
        }

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.get("/api/v1/iil/monitors")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data[items]) == 2

    def test_list_monitors_with_search(self, client):
        """List monitors passes search param to service."""
        svc = _mock_monitor_service()

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.get("/api/v1/iil/monitors?search=test&target_type=url&enabled_only=true")

        assert resp.status_code == 200
        svc.list_targets.assert_called_once_with(
            search="test", target_type="url", enabled_only=True, offset=0, limit=50
        )

    def test_list_monitors_empty(self, client):
        """List monitors returns empty list when no targets."""
        svc = _mock_monitor_service()

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.get("/api/v1/iil/monitors")

        assert resp.status_code == 200
        assert resp.json()[items] == []


# =============================================================================
# POST /monitors Endpoint Tests
# =============================================================================


class TestCreateMonitorEndpoint:
    """Tests for POST /api/v1/iil/monitors"""

    def test_create_monitor_success(self, client):
        """Create monitor returns new target."""
        svc = _mock_monitor_service()

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.post(
                "/api/v1/iil/monitors",
                json={
                    "name": "New Monitor",
                    "target_type": "url",
                    "target_url": "http://new.com",
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "mon_456"
        assert data["name"] == "New Monitor"

    def test_create_monitor_with_optional_fields(self, client):
        """Create monitor passes all optional fields."""
        svc = _mock_monitor_service()

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.post(
                "/api/v1/iil/monitors",
                json={
                    "name": "Full Monitor",
                    "target_type": "url",
                    "target_url": "http://full.com",
                    "check_interval_minutes": 30,
                    "trigger_on_any_change": False,
                    "trigger_on_semantic_change": True,
                    "semantic_change_threshold": 0.25,
                    "keyword_triggers": ["price", "update"],
                    "enabled": True,
                },
            )

        assert resp.status_code == 201
        svc.create_target.assert_called_once()

    def test_create_monitor_missing_fields(self, client):
        """Create monitor returns 422 when required fields are missing."""
        resp = client.post(
            "/api/v1/iil/monitors",
            json={"name": "Incomplete"},
        )
        assert resp.status_code == 422


# =============================================================================
# GET /monitors/{target_id} Endpoint Tests
# =============================================================================


class TestGetMonitorEndpoint:
    """Tests for GET /api/v1/iil/monitors/{target_id}"""

    def test_get_monitor_success(self, client):
        """Get monitor returns target by ID."""
        svc = _mock_monitor_service()

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.get("/api/v1/iil/monitors/mon_123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "mon_123"
        assert data["name"] == "Test Monitor"

    def test_get_monitor_not_found(self, client):
        """Get monitor returns 404 when target not found."""
        svc = _mock_monitor_service()
        svc.get_target.side_effect = ValueError("Target not found")

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.get("/api/v1/iil/monitors/nonexistent")

        assert resp.status_code == 404


# =============================================================================
# PUT /monitors/{target_id} Endpoint Tests
# =============================================================================


class TestUpdateMonitorEndpoint:
    """Tests for PUT /api/v1/iil/monitors/{target_id}"""

    def test_update_monitor_success(self, client):
        """Update monitor returns updated target."""
        svc = _mock_monitor_service()

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.put(
                "/api/v1/iil/monitors/mon_123",
                json={"name": "Updated Monitor", "target_url": "http://updated.com"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Monitor"

    def test_update_monitor_not_found(self, client):
        """Update monitor returns 404 when target not found."""
        svc = _mock_monitor_service()
        svc.update_target.side_effect = ValueError("Target not found")

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.put(
                "/api/v1/iil/monitors/nonexistent",
                json={"name": "Updated"},
            )

        assert resp.status_code == 404


# =============================================================================
# DELETE /monitors/{target_id} Endpoint Tests
# =============================================================================


class TestDeleteMonitorEndpoint:
    """Tests for DELETE /api/v1/iil/monitors/{target_id}"""

    def test_delete_monitor_success(self, client):
        """Delete monitor returns success."""
        svc = _mock_monitor_service()

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.delete("/api/v1/iil/monitors/mon_123")

        assert resp.status_code == 200

    def test_delete_monitor_not_found(self, client):
        """Delete monitor returns 404 when target not found."""
        svc = _mock_monitor_service()
        svc.delete_target.side_effect = ValueError("Target not found")

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.delete("/api/v1/iil/monitors/nonexistent")

        assert resp.status_code == 404


# =============================================================================
# POST /monitors/{target_id}/check Endpoint Tests
# =============================================================================


class TestCheckMonitorEndpoint:
    """Tests for POST /api/v1/iil/monitors/{target_id}/check"""

    def test_check_monitor_success(self, client):
        """Check monitor returns check result."""
        svc = _mock_monitor_service()

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.post("/api/v1/iil/monitors/mon_123/check")

        assert resp.status_code == 200
        data = resp.json()
        assert data["target_id"] == "mon_123"
        assert "changed" in data

    def test_check_monitor_error(self, client):
        """Check monitor returns 500 on error."""
        svc = _mock_monitor_service()
        svc.check_target.side_effect = RuntimeError("Check failed")

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.post("/api/v1/iil/monitors/mon_123/check")

        assert resp.status_code == 500


# =============================================================================
# POST /monitors/check-all Endpoint Tests
# =============================================================================


class TestCheckAllMonitorsEndpoint:
    """Tests for POST /api/v1/iil/monitors/check-all"""

    def test_check_all_success(self, client):
        """Check all monitors returns list of results."""
        svc = _mock_monitor_service()
        svc.check_all_due.return_value = [
            {"target_id": "mon_1", "changed": False},
            {"target_id": "mon_2", "changed": True},
        ]

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.post("/api/v1/iil/monitors/check-all")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_check_all_empty(self, client):
        """Check all monitors returns empty list when nothing due."""
        svc = _mock_monitor_service()
        svc.check_all_due.return_value = []

        with patch("app.modules.iil.routes._get_service", return_value=MagicMock()), \
             patch("common_lib.modules.iil.monitoring.monitor.MonitorService", return_value=svc):
            resp = client.post("/api/v1/iil/monitors/check-all")

        assert resp.status_code == 200
        assert resp.json() == []
