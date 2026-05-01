"""
Tests for hooks API endpoints
"""

import pytest


class TestHooksAPI:
    """Test hooks API endpoints."""

    def test_list_hooks(self):
        """Test GET /api/v1/hooks - list hooks."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/v1/hooks/")
        assert response.status_code == 200

    def test_create_hook(self):
        """Test POST /api/v1/hooks - create hook."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        payload = {"name": "test_hook", "phase": "post", "config": {}}
        response = client.post("/api/v1/hooks/", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_hook"

    def test_get_hook(self):
        """Test GET /api/v1/hooks/{hook_id}."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/v1/hooks/test_hook")
        assert response.status_code == 200

    def test_delete_hook(self):
        """Test DELETE /api/v1/hooks/{hook_id}."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.delete("/api/v1/hooks/test_hook")
        assert response.status_code == 200

    def test_trigger_hook(self):
        """Test POST /api/v1/hooks/{hook_id}/trigger."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        payload = {"event_type": "test.event", "payload": {"test": "data"}}
        response = client.post("/api/v1/hooks/test_hook/trigger", json=payload)
        assert response.status_code == 200

    def test_enable_hook(self):
        """Test POST /api/v1/hooks/{hook_id}/enable."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/v1/hooks/test_hook/enable")
        assert response.status_code == 200

    def test_disable_hook(self):
        """Test POST /api/v1/hooks/{hook_id}/disable."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/v1/hooks/test_hook/disable")
        assert response.status_code == 200

    def test_get_hook_logs(self):
        """Test GET /api/v1/hooks/{hook_id}/logs."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/v1/hooks/test_hook/logs")
        assert response.status_code == 200

    def test_get_hook_versions(self):
        """Test GET /api/v1/hooks/{hook_id}/versions."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/v1/hooks/test_hook/versions")
        assert response.status_code == 200

    def test_rollback_hook(self):
        """Test POST /api/v1/hooks/{hook_id}/rollback/{version_id}."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/v1/hooks/test_hook/rollback/v1")
        assert response.status_code == 200

    def test_list_templates(self):
        """Test GET /api/v1/hooks/templates/."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/v1/hooks/templates/")
        assert response.status_code == 200

    def test_instantiate_template(self):
        """Test POST /api/v1/hooks/templates/{template_id}/instantiate."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/api/v1/hooks/templates/slack-notify/instantiate",
            json={"channel": "#test"},
        )
        assert response.status_code == 200

    def test_list_schemas(self):
        """Test GET /api/v1/hooks/schemas/."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/v1/hooks/schemas/")
        assert response.status_code == 200

    def test_get_dlq(self):
        """Test GET /api/v1/hooks/dlq/."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/v1/hooks/dlq/")
        assert response.status_code == 200

    def test_replay_dlq(self):
        """Test POST /api/v1/hooks/dlq/{entry_id}/replay."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/v1/hooks/dlq/entry1/replay")
        assert response.status_code == 200


class TestWebhookTrigger:
    """Test webhook trigger endpoint."""

    def test_trigger_webhook(self):
        """Test POST /api/v1/hooks/trigger - trigger by event."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        payload = {"event_type": "user.created", "payload": {"user_id": 1}}
        response = client.post("/api/v1/hooks/trigger", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "hooks" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_hook(self, client):
        """Test POST /api/v1/hooks - create hook."""
        payload = {"name": "test_hook", "phase": "post", "config": {"test": True}}
        response = await client.post("/api/v1/hooks", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_hook"

    @pytest.mark.asyncio
    async def test_get_hook(self, client):
        """Test GET /api/v1/hooks/{hook_id} - get hook."""
        response = await client.get("/api/v1/hooks/test_hook")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    @pytest.mark.asyncio
    async def test_delete_hook(self, client):
        """Test DELETE /api/v1/hooks/{hook_id} - delete hook."""
        response = await client.delete("/api/v1/hooks/test_hook")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_trigger_hook(self, client):
        """Test POST /api/v1/hooks/{hook_id}/trigger - trigger hook."""
        payload = {"event_type": "test.event", "payload": {"test": "data"}}
        response = await client.post("/api/v1/hooks/test_hook/trigger", json=payload)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_enable_hook(self, client):
        """Test POST /api/v1/hooks/{hook_id}/enable - enable hook."""
        response = await client.post("/api/v1/hooks/test_hook/enable")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_disable_hook(self, client):
        """Test POST /api/v1/hooks/{hook_id}/disable - disable hook."""
        response = await client.post("/api/v1/hooks/test_hook/disable")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_hook_logs(self, client):
        """Test GET /api/v1/hooks/{hook_id}/logs - get hook logs."""
        response = await client.get("/api/v1/hooks/test_hook/logs")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_hook_versions(self, client):
        """Test GET /api/v1/hooks/{hook_id}/versions - get versions."""
        response = await client.get("/api/v1/hooks/test_hook/versions")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rollback_hook(self, client):
        """Test POST /api/v1/hooks/{hook_id}/rollback/{version_id}."""
        response = await client.post("/api/v1/hooks/test_hook/rollback/v1")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_templates(self, client):
        """Test GET /api/v1/hooks/templates/ - list templates."""
        response = await client.get("/api/v1/hooks/templates/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_instantiate_template(self, client):
        """Test POST /api/v1/hooks/templates/{template_id}/instantiate."""
        response = await client.post(
            "/api/v1/hooks/templates/slack-notify/instantiate",
            json={"channel": "#test"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_schemas(self, client):
        """Test GET /api/v1/hooks/schemas/ - list schemas."""
        response = await client.get("/api/v1/hooks/schemas/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_dlq(self, client):
        """Test GET /api/v1/hooks/dlq/ - get DLQ."""
        response = await client.get("/api/v1/hooks/dlq/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_replay_dlq(self, client):
        """Test POST /api/v1/hooks/dlq/{entry_id}/replay."""
        response = await client.post("/api/v1/hooks/dlq/entry1/replay")
        assert response.status_code == 200


class TestWebhookTrigger:
    """Test webhook trigger endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_webhook(self, client):
        """Test POST /api/v1/hooks/trigger - trigger by event."""
        payload = {"event_type": "user.created", "payload": {"user_id": 1}}
        response = await client.post("/api/v1/hooks/trigger", json=payload)
        assert response.status_code == 200
