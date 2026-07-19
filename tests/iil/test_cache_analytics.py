"""IIL Cache & Analytics — Integration Tests.

Tests the POST /cache/clear, GET/PUT /analytics/config, POST /analytics/reset,
GET /debug/tables, and GET /debug/tables/{table_name} endpoints.

Usage:
    cd "Backend Monorepo/Backend"
    uv run pytest tests/iil/test_cache_analytics.py -v
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# =============================================================================
# POST /cache/clear Endpoint Tests
# =============================================================================


class TestCacheClearEndpoint:
    """Tests for POST /api/v1/iil/cache/clear"""

    def test_clear_all_cache(self, client):
        svc = MagicMock()
        svc.clear_cache.return_value = 42
        with patch("app.modules.iil.routes._get_service", return_value=svc), \
             patch("app.modules.iil.routes._get_analytics", return_value=MagicMock()):
            resp = client.post("/api/v1/iil/cache/clear", json={"clear_all": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries_cleared"] == 42
        assert data["success"] is True

    def test_clear_cache_older_than(self, client):
        svc = MagicMock()
        svc.clear_cache.return_value = 10
        with patch("app.modules.iil.routes._get_service", return_value=svc), \
             patch("app.modules.iil.routes._get_analytics", return_value=MagicMock()):
            resp = client.post("/api/v1/iil/cache/clear", json={"older_than_hours": 24})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_clear_cache_no_action(self, client):
        svc = MagicMock()
        svc.clear_cache.return_value = 0
        with patch("app.modules.iil.routes._get_service", return_value=svc), \
             patch("app.modules.iil.routes._get_analytics", return_value=MagicMock()):
            resp = client.post("/api/v1/iil/cache/clear", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries_cleared"] == 0
        assert "No action taken" in data["message"]


# =============================================================================
# GET /analytics/config Endpoint Tests
# =============================================================================


class TestAnalyticsConfigEndpoint:
    def test_get_analytics_config(self, client):
        analytics = MagicMock()
        analytics.get_retention_days.return_value = 30
        with patch("app.modules.iil.routes._get_analytics", return_value=analytics):
            resp = client.get("/api/v1/iil/analytics/config")
        assert resp.status_code == 200
        assert resp.json()["retention_days"] == 30


# =============================================================================
# PUT /analytics/config Endpoint Tests
# =============================================================================


class TestUpdateAnalyticsConfigEndpoint:
    def test_update_analytics_config(self, client):
        analytics = MagicMock()
        analytics.get_retention_days.return_value = 60
        with patch("app.modules.iil.routes._get_analytics", return_value=analytics):
            resp = client.put("/api/v1/iil/analytics/config", json={"retention_days": 60})
        assert resp.status_code == 200
        assert resp.json()["retention_days"] == 60
        analytics.set_retention_days.assert_called_once_with(60)

    def test_update_analytics_config_invalid_value(self, client):
        with patch("app.modules.iil.routes._get_analytics", return_value=MagicMock()):
            resp = client.put("/api/v1/iil/analytics/config", json={"retention_days": 0})
        assert resp.status_code == 400

    def test_update_analytics_config_too_high(self, client):
        with patch("app.modules.iil.routes._get_analytics", return_value=MagicMock()):
            resp = client.put("/api/v1/iil/analytics/config", json={"retention_days": 400})
        assert resp.status_code == 400

    def test_update_analytics_config_missing_field(self, client):
        with patch("app.modules.iil.routes._get_analytics", return_value=MagicMock()):
            resp = client.put("/api/v1/iil/analytics/config", json={})
        assert resp.status_code == 400


# =============================================================================
# POST /analytics/reset Endpoint Tests
# =============================================================================


class TestAnalyticsResetEndpoint:
    def test_reset_analytics(self, client):
        analytics = MagicMock()
        with patch("app.modules.iil.routes._get_analytics", return_value=analytics):
            resp = client.post("/api/v1/iil/analytics/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        analytics.reset.assert_called_once()


# =============================================================================
# GET /debug/tables Endpoint Tests
# =============================================================================


class TestDebugTablesEndpoint:
    def test_list_debug_tables(self, client):
        resp = client.get("/api/v1/iil/debug/tables")
        assert resp.status_code == 200
        data = resp.json()
        assert "tables" in data
        assert len(data["tables"]) >= 4
        table_names = [t["name"] for t in data["tables"]]
        assert "iil_artifacts" in table_names

    def test_debug_tables_have_columns(self, client):
        resp = client.get("/api/v1/iil/debug/tables")
        data = resp.json()
        for table in data["tables"]:
            assert "name" in table
            assert "columns" in table
            assert len(table["columns"]) > 0


# =============================================================================
# GET /debug/tables/{table_name} Endpoint Tests
# =============================================================================


class TestDebugTableQueryEndpoint:
    def test_query_debug_table(self, client):
        svc = MagicMock()
        svc._query_table = AsyncMock(return_value=([{"id": 1}], 1))
        with patch("app.modules.iil.routes._get_service", return_value=svc):
            resp = client.get("/api/v1/iil/debug/tables/iil_artifacts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["table"] == "iil_artifacts"
        assert "rows" in data
        assert "total" in data

    def test_query_debug_table_with_pagination(self, client):
        svc = MagicMock()
        svc._query_table = AsyncMock(return_value=([], 0))
        with patch("app.modules.iil.routes._get_service", return_value=svc):
            resp = client.get("/api/v1/iil/debug/tables/iil_artifacts?limit=50&offset=10")
        assert resp.status_code == 200
        call_kwargs = svc._query_table.call_args[1]
        assert call_kwargs["limit"] == 50
        assert call_kwargs["offset"] == 10

    def test_query_debug_table_with_sort(self, client):
        svc = MagicMock()
        svc._query_table = AsyncMock(return_value=([], 0))
        with patch("app.modules.iil.routes._get_service", return_value=svc):
            resp = client.get("/api/v1/iil/debug/tables/iil_artifacts?order_by=created_at&direction=desc")
        assert resp.status_code == 200
        call_kwargs = svc._query_table.call_args[1]
        assert call_kwargs["order_by"] == "created_at"
        assert call_kwargs["direction"] == "desc"

    def test_query_unknown_table(self, client):
        svc = MagicMock()
        with patch("app.modules.iil.routes._get_service", return_value=svc):
            resp = client.get("/api/v1/iil/debug/tables/unknown_table")
        assert resp.status_code == 404

    def test_query_debug_table_with_date_filter(self, client):
        svc = MagicMock()
        svc._query_table = AsyncMock(return_value=([], 0))
        with patch("app.modules.iil.routes._get_service", return_value=svc):
            resp = client.get("/api/v1/iil/debug/tables/iil_artifacts?date_range_hours=24&date_column=created_at")
        assert resp.status_code == 200
