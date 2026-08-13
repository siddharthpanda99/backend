"""
Tests for Secrets Manager Proxy submodule (SSOT 09).

Tests API key management, client configs, agent configs, proxy routes.
"""

from __future__ import annotations

from common_lib.modules.secrets_manager.proxy.service import ProxyService


class TestProxyService:
    """Test API key, client config, agent config, and proxy route management."""

    def test_create_api_key(self, db):
        svc = ProxyService(session=db)
        result = svc.create_api_key(name="deploy-key", scopes=["read", "write"])
        assert result["name"] == "deploy-key"
        assert "raw_key" in result
        assert result["raw_key"].startswith("sm_")

    def test_list_api_keys(self, db):
        svc = ProxyService(session=db)
        svc.create_api_key(name="key-1")
        svc.create_api_key(name="key-2")
        keys = svc.list_api_keys()
        assert len(keys) >= 2
        names = [k["name"] for k in keys]
        assert "key-1" in names
        assert "key-2" in names

    def test_revoke_api_key(self, db):
        svc = ProxyService(session=db)
        svc.create_api_key(name="revoke-key")
        assert svc.revoke_api_key(name="revoke-key") is True

    def test_revoke_api_key_not_found(self, db):
        svc = ProxyService(session=db)
        assert svc.revoke_api_key(name="nonexistent") is False

    def test_validate_api_key_valid(self, db):
        svc = ProxyService(session=db)
        created = svc.create_api_key(name="valid-key")
        raw_key = created["raw_key"]
        validated = svc.validate_api_key(raw_key=raw_key)
        assert validated is not None
        assert validated["name"] == "valid-key"

    def test_validate_api_key_invalid(self, db):
        svc = ProxyService(session=db)
        assert svc.validate_api_key(raw_key="sm_invalid_key") is None

    def test_create_client_config(self, db):
        svc = ProxyService(session=db)
        result = svc.create_client_config(
            name="my-app", client_type="rest", base_url="https://secrets.example.com"
        )
        assert result["name"] == "my-app"
        assert result["client_type"] == "rest"

    def test_list_client_configs(self, db):
        svc = ProxyService(session=db)
        svc.create_client_config(name="cfg-1")
        svc.create_client_config(name="cfg-2")
        cfgs = svc.list_client_configs()
        assert len(cfgs) >= 2

    def test_create_agent_config(self, db):
        svc = ProxyService(session=db)
        result = svc.create_agent_config(
            name="sidecar-prod", agent_type="sidecar", cache_ttl_seconds=600
        )
        assert result["name"] == "sidecar-prod"
        assert result["agent_type"] == "sidecar"

    def test_list_agent_configs(self, db):
        svc = ProxyService(session=db)
        svc.create_agent_config(name="agent-1")
        svc.create_agent_config(name="agent-2")
        agents = svc.list_agent_configs()
        assert len(agents) >= 2

    def test_create_proxy_route(self, db):
        svc = ProxyService(session=db)
        result = svc.create_proxy_route(
            name="db-route",
            source_path="/secrets/db",
            target_path="DB_PASSWORD",
            route_type="env",
        )
        assert result["name"] == "db-route"
        assert result["route_type"] == "env"

    def test_list_proxy_routes(self, db):
        svc = ProxyService(session=db)
        svc.create_proxy_route(name="route-1", source_path="/a", target_path="A")
        svc.create_proxy_route(name="route-2", source_path="/b", target_path="B")
        routes = svc.list_proxy_routes()
        assert len(routes) >= 2
