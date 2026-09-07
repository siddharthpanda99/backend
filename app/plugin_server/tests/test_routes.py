"""Tests for the Plugin Server routes.

Uses TestClient with a mock app.state so we don't need a real
plugin manager.
"""

import pytest
from fastapi.testclient import TestClient


class FakePluginInstance:
    """Minimal BaseToolPlugin stand-in for testing."""

    id = "fake"

    def __init__(self):
        self.metadata = type(
            "M",
            (),
            {
                "name": "Fake",
                "description": "test",
                "category": "test",
                "version": "1.0.0",
            },
        )()
        self.disposed = False

    def check_health(self):
        class H:
            status = type("S", (), {"value": "healthy"})()
            message = "ok"

        return H()

    def get_nodes(self):
        return [{"name": "fake.do_thing", "entity_type": "tool", "description": "..."}]

    def safe_invoke(self, tool_id, **kwargs):
        return {"echo": kwargs}

    @property
    def total_tools(self):
        return 1

    @property
    def total_nodes(self):
        return 1


class FakeEngine:
    def __init__(self, plugins):
        self.plugins = {p.id: p for p in plugins}

    def list_plugins(self):
        return list(self.plugins.values())


class FakeReloadResult:
    """Stand-in for PluginSlot.last_reload_id — must be JSON-serializable."""

    def __init__(self):
        self.last_reload_id = "abc123"


class FakeManager:
    def __init__(self):
        self.engine = FakeEngine([FakePluginInstance()])

    def reload(self):
        return len(self.engine.plugins)

    def safe_reload_plugin(self, plugin_id):
        if plugin_id not in self.engine.plugins:
            raise KeyError(plugin_id)
        # Return a plain dict so FastAPI can JSON-serialize it
        return {"last_reload_id": "abc123"}


class FakeComponents(dict):
    """Like a dict but supports attribute access for app.state."""

    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(name)


@pytest.fixture
def app_with_fakes():
    """Build the plugin server app with a mock plugin manager."""
    from app.plugin_server.main import app

    fake_components = FakeComponents()
    fake_components["tool_manager"] = FakeManager()

    # The lifespan would normally populate this; bypass it.
    app.state.components = fake_components
    app.state.ready = True
    app.state.started_at = 0.0

    return app


@pytest.fixture
def client(app_with_fakes):
    return TestClient(app_with_fakes)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "uptime_sec" in data


def test_version(client):
    r = client.get("/health/version")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "plugin-server"
    assert "pid" in data
    assert data["pid"] > 0


def test_list_plugins(client):
    r = client.get("/plugins")
    assert r.status_code == 200
    data = r.json()
    assert "plugins" in data
    assert len(data["plugins"]) == 1
    assert data["plugins"][0]["id"] == "fake"


def test_get_plugin(client):
    r = client.get("/plugins/fake")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "fake"


def test_get_plugin_not_found(client):
    r = client.get("/plugins/nonexistent")
    assert r.status_code == 404


def test_safe_reload_plugin(client):
    r = client.post("/plugins/fake/safe-reload")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    # The route returns reload_id as a nested dict from FakeManager
    assert data["reload_id"] == {"last_reload_id": "abc123"}


def test_safe_reload_plugin_not_found(client):
    r = client.post("/plugins/nonexistent/safe-reload")
    assert r.status_code == 404


def test_reload_all(client):
    r = client.post("/plugins/reload")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True


def test_execute_tool_success(client):
    r = client.post(
        "/tools/execute",
        json={
            "plugin_id": "fake",
            "tool_name": "do_thing",
            "params": {"x": 1},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["result"]["echo"] == {"x": 1}


def test_execute_tool_missing_plugin(client):
    r = client.post(
        "/tools/execute",
        json={
            "plugin_id": "nonexistent",
            "tool_name": "do_thing",
            "params": {},
        },
    )
    assert r.status_code == 404


def test_execute_tool_missing_fields(client):
    r = client.post("/tools/execute", json={"plugin_id": "fake"})
    assert r.status_code == 400
