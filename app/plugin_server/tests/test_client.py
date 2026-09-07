"""Tests for the PluginServerClient (the main backend's proxy).

Uses httpx.MockTransport so no real server is needed.
"""

import pytest
import httpx

from app.plugin_server.client import (
    PluginServerClient,
    PluginServerUnreachable,
    PluginServerToolError,
    PluginServerCircuitOpen,
)


def make_client(handler):
    """Create a PluginServerClient wired to a mock transport."""
    client = PluginServerClient(
        base_url="http://mock",
        timeout_sec=5.0,
        health_timeout_sec=1.0,
        cache_ttl_sec=0.0,  # disable cache for tests
        # We can't pass transport to PluginServerClient directly;
        # instead, monkey-patch the _get_client method.
    )
    # Replace the internal client's transport
    mock = httpx.MockTransport(handler)

    def _get():
        c = httpx.Client(base_url="http://mock", transport=mock, timeout=5.0)
        return c

    client._get_client = _get
    return client


def test_health_returns_true_on_200():
    def handler(request):
        return httpx.Response(200, json={"status": "ok"})

    c = make_client(handler)
    assert c.health() is True


def test_health_returns_false_on_500():
    def handler(request):
        return httpx.Response(500, text="boom")

    c = make_client(handler)
    assert c.health() is False


def test_health_returns_false_on_connection_error():
    def handler(request):
        raise httpx.ConnectError("nope")

    c = make_client(handler)
    assert c.health() is False
    # First failure, circuit should not be open yet
    assert c._consecutive_failures == 1


def test_circuit_breaker_opens_after_threshold():
    def handler(request):
        raise httpx.ConnectError("nope")

    c = make_client(handler)  # failure_threshold=3, circuit_cooldown_sec=60
    for _ in range(3):
        c.health()
    # Now the circuit should be open
    assert c._circuit_opened_at is not None
    with pytest.raises(PluginServerCircuitOpen):
        c.health()


def test_list_plugins_parses_response():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "plugins": [
                    {"id": "github", "name": "GitHub", "version": "1.0"},
                    {"id": "slack", "name": "Slack", "version": "2.0"},
                ]
            },
        )

    c = make_client(handler)
    plugins = c.list_plugins()
    assert len(plugins) == 2
    assert plugins[0]["id"] == "github"


def test_list_plugins_raises_unreachable_on_network_error():
    def handler(request):
        raise httpx.ConnectError("nope")

    c = make_client(handler)
    with pytest.raises(PluginServerUnreachable):
        c.list_plugins()


def test_list_plugins_404_raises_error():
    def handler(request):
        return httpx.Response(404, json={"error": "no plugins"})

    c = make_client(handler)
    with pytest.raises(PluginServerUnreachable):
        c.list_plugins()


def test_execute_tool_returns_result_dict():
    def handler(request):
        # Verify request shape
        body = request.read()
        import json as _json

        data = _json.loads(body)
        assert data["plugin_id"] == "github"
        assert data["tool_name"] == "create_issue"
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"issue_id": 42},
                "duration_ms": 100,
            },
        )

    c = make_client(handler)
    result = c.execute_tool("github", "create_issue", {"title": "x"})
    assert result["success"] is True
    assert result["result"]["issue_id"] == 42


def test_execute_tool_503_raises_tool_error():
    def handler(request):
        return httpx.Response(
            503,
            json={
                "success": False,
                "error": "plugin is reloading",
                "retry_after": 5,
            },
        )

    c = make_client(handler)
    with pytest.raises(PluginServerToolError) as exc_info:
        c.execute_tool("github", "create_issue", {})
    assert exc_info.value.status_code == 503
    assert exc_info.value.body["error"] == "plugin is reloading"


def test_execute_tool_500_raises_tool_error():
    def handler(request):
        return httpx.Response(500, json={"success": False, "error": "boom"})

    c = make_client(handler)
    with pytest.raises(PluginServerToolError) as exc_info:
        c.execute_tool("github", "create_issue", {})
    assert exc_info.value.status_code == 500


def test_safe_reload_plugin_succeeds():
    def handler(request):
        if request.method == "POST" and "/safe-reload" in str(request.url):
            return httpx.Response(
                200,
                json={"success": True, "plugin_id": "github", "reload_id": "abc"},
            )
        return httpx.Response(404)

    c = make_client(handler)
    result = c.safe_reload_plugin("github")
    assert result["success"] is True
    assert result["reload_id"] == "abc"


def test_safe_reload_plugin_404_raises_error():
    def handler(request):
        return httpx.Response(404, json={"error": "not found"})

    c = make_client(handler)
    with pytest.raises(
        PluginServerError := __import__(
            "app.plugin_server.client", fromlist=["PluginServerError"]
        ).PluginServerError
    ):
        c.safe_reload_plugin("nonexistent")


def test_reload_all_succeeds():
    def handler(request):
        return httpx.Response(200, json={"success": True, "plugins_loaded": 5})

    c = make_client(handler)
    result = c.reload_all()
    assert result["plugins_loaded"] == 5


def test_list_extensions():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "extensions": [
                    {"id": "my_ext", "status": "active"},
                ]
            },
        )

    c = make_client(handler)
    exts = c.list_extensions()
    assert len(exts) == 1


def test_list_infra_plugins():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "plugins": [
                    {"id": "settings", "class": "SettingsPlugin"},
                ]
            },
        )

    c = make_client(handler)
    plugins = c.list_infra_plugins()
    assert len(plugins) == 1


def test_list_services():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "services": ["settings", "secrets", "database"],
            },
        )

    c = make_client(handler)
    services = c.list_services()
    assert services == ["settings", "secrets", "database"]


# Import for the safe-reload test
from app.plugin_server.client import PluginServerError
