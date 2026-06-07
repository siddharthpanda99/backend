"""Tests for ConnectorExecutionEngine.

Covers:
- Endpoint coverage (all seeded tools have mappings)
- Base URL resolution per connector
- Auth header construction per scheme
- Path parameter substitution
- Full execute flow with mocked HTTP
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from common_lib.modules.plugins.connectors.models.connection import (
    Connection,
    ConnectionStatus,
)
from app.modules.connectors.execute_engine import (
    TOOL_ENDPOINTS,
    _get_base_url,
    _build_auth_headers,
    _substitute_path_params,
    ConnectorExecutionEngine,
    get_execution_engine,
)
from app.modules.connectors.seed import get_connector_seeds
from app.modules.connectors.providers import get_provider, get_registered_ids


# =============================================================================
# Coverage: all seeded tools have endpoint mappings
# =============================================================================


def _all_seeded_tool_ids():
    ids = []
    for seed in get_connector_seeds():
        for tool in seed.get("tools", []):
            ids.append(tool["id"])
    return ids


class TestEndpointCoverage:
    def test_all_seeded_tools_have_endpoints(self):
        missing = [tid for tid in _all_seeded_tool_ids() if tid not in TOOL_ENDPOINTS]
        assert not missing, (
            f"{len(missing)} seeded tools missing endpoint mappings: {missing}"
        )

    def test_no_extra_endpoints(self):
        seeded = set(_all_seeded_tool_ids())
        mapped = set(TOOL_ENDPOINTS.keys())
        extra = mapped - seeded
        assert not extra, f"Unused endpoint mappings (tools not in seeds): {extra}"

    def test_tool_count_matches(self):
        seeded_count = len(_all_seeded_tool_ids())
        assert len(TOOL_ENDPOINTS) == seeded_count, (
            f"Endpoint count {len(TOOL_ENDPOINTS)} != seeded tools {seeded_count}"
        )


# =============================================================================
# Base URL resolution
# =============================================================================


class TestBaseUrlResolution:
    def test_github_default(self):
        assert _get_base_url("github", {}) == "https://api.github.com"

    def test_jira_from_form_data(self):
        url = _get_base_url("atlassian", {"instance_url": "https://my.atlassian.net"})
        assert url == "https://my.atlassian.net"

    def test_jira_empty_fallback(self):
        assert _get_base_url("atlassian", {}) == ""

    def test_slack_default(self):
        assert _get_base_url("slack", {}) == "https://slack.com/api"

    def test_notion_default(self):
        assert _get_base_url("notion", {}) == "https://api.notion.com/v1"

    def test_stripe_default(self):
        assert _get_base_url("stripe", {}) == "https://api.stripe.com"

    def test_paypal_sandbox(self):
        url = _get_base_url("paypal", {"mode": "sandbox"})
        assert url == "https://api-m.sandbox.paypal.com"

    def test_paypal_live(self):
        url = _get_base_url("paypal", {"mode": "live"})
        assert url == "https://api-m.paypal.com"

    def test_gitlab_self_hosted(self):
        url = _get_base_url("gitlab", {"instance_url": "https://gitlab.example.com"})
        assert url == "https://gitlab.example.com/api/v4"

    def test_gitlab_default(self):
        url = _get_base_url("gitlab", {})
        assert url == "https://gitlab.com/api/v4"

    def test_digitalocean_default(self):
        assert _get_base_url("digitalocean", {}) == "https://api.digitalocean.com"

    def test_linear_default(self):
        assert _get_base_url("linear", {}) == "https://api.linear.app"

    def test_twilio_default(self):
        assert _get_base_url("twilio", {}) == "https://api.twilio.com"

    def test_unknown_connector(self):
        assert _get_base_url("unknown", {}) == ""


# =============================================================================
# Auth header construction
# =============================================================================


class TestAuthHeaders:
    def test_bearer_token(self):
        headers = _build_auth_headers("github", "bearer_token", "tok_123")
        assert headers == {"Authorization": "Bearer tok_123"}

    def test_basic_auth(self):
        headers = _build_auth_headers("atlassian", "basic_auth", "user:pass")
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    @pytest.mark.parametrize("connector", ["github", "atlassian", "notion", "hubspot"])
    def test_api_key_bearer(self, connector):
        headers = _build_auth_headers(connector, "api_key", "key_abc")
        assert headers == {"Authorization": "Bearer key_abc"}

    def test_gitlab_api_key(self):
        headers = _build_auth_headers("gitlab", "api_key", "glpat_abc")
        assert headers == {"PRIVATE-TOKEN": "glpat_abc"}


# =============================================================================
# Path parameter substitution
# =============================================================================


class TestPathSubstitution:
    def test_no_params(self):
        path, remaining = _substitute_path_params("/user/repos", {}, {})
        assert path == "/user/repos"
        assert remaining == {}

    def test_single_param(self):
        path, remaining = _substitute_path_params(
            "/repos/{owner}/{repo}",
            {"owner": "me", "repo": "my-repo", "extra": "val"},
            {},
        )
        assert path == "/repos/me/my-repo"
        assert remaining == {"extra": "val"}

    def test_param_from_form_data(self):
        path, remaining = _substitute_path_params(
            "/projects/{project_id}/issues",
            {"some_other": "val"},
            {"project_id": "123"},
        )
        assert path == "/projects/123/issues"

    def test_missing_param_raises(self):
        from common_lib.modules.plugins.connectors.exceptions import ExecutionError

        with pytest.raises(ExecutionError, match="Missing required path parameter"):
            _substitute_path_params("/{missing}", {}, {})


# =============================================================================
# Full execution flow (mocked httpx)
# =============================================================================


class TestExecuteFlow:
    def _make_connection(self, key_id: int = 1) -> Connection:
        return Connection(
            id="conn-1",
            connector_id="github",
            user_id="user-1",
            auth_scheme="api_key",
            key_id=key_id,
            status=ConnectionStatus.ACTIVE,
            label="test",
            form_data={},
        )

    @patch("httpx.Client.request")
    @patch("app.modules.connectors.execute_engine.get_connector_key_manager")
    def test_execute_success(self, mock_key_mgr, mock_request):
        mock_key_mgr.return_value.resolve.return_value = "ghp_test"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"login": "testuser"}'
        mock_response.json.return_value = {"login": "testuser"}
        mock_request.return_value = mock_response

        engine = ConnectorExecutionEngine(timeout=10)
        result = engine.execute(
            connector_id="github",
            tool_id="github.list_repos",
            params={"per_page": 30},
            connection=self._make_connection(),
            form_data={},
        )
        assert result == {"login": "testuser"}

    @patch("httpx.Client.request")
    @patch("app.modules.connectors.execute_engine.get_connector_key_manager")
    def test_execute_with_path_params(self, mock_key_mgr, mock_request):
        mock_key_mgr.return_value.resolve.return_value = "ghp_test"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": 1}'
        mock_response.json.return_value = {"id": 1}
        mock_request.return_value = mock_response

        engine = ConnectorExecutionEngine(timeout=10)
        result = engine.execute(
            connector_id="github",
            tool_id="github.get_repo",
            params={"owner": "me", "repo": "my-repo"},
            connection=self._make_connection(),
            form_data={},
        )
        assert result == {"id": 1}

    @patch("app.modules.connectors.execute_engine.get_connector_key_manager")
    def test_execute_unknown_tool(self, mock_key_mgr):
        mock_key_mgr.return_value.resolve.return_value = "key"
        engine = ConnectorExecutionEngine(timeout=10)
        with pytest.raises(Exception, match="No endpoint mapping"):
            engine.execute(
                connector_id="github",
                tool_id="nonexistent.tool",
                params={},
                connection=self._make_connection(),
                form_data={},
            )

    @patch("app.modules.connectors.execute_engine.get_connector_key_manager")
    def test_execute_missing_base_url(self, mock_key_mgr):
        mock_key_mgr.return_value.resolve.return_value = "key"
        engine = ConnectorExecutionEngine(timeout=10)
        with pytest.raises(Exception, match="Could not resolve.*base URL"):
            engine.execute(
                connector_id="atlassian",
                tool_id="jira.list_projects",
                params={},
                connection=self._make_connection(),
                form_data={},
            )

    def test_get_execution_engine_singleton(self):
        e1 = get_execution_engine()
        e2 = get_execution_engine()
        assert e1 is e2


# =============================================================================
# Linear GraphQL query building
# =============================================================================


class TestLinearGraphQL:
    def test_build_list_issues_query(self):
        engine = ConnectorExecutionEngine()
        body = engine._build_linear_graphql(
            "linear.list_issues", {"teamId": "team-1", "limit": 10}
        )
        assert "query" in body
        assert "ListIssues" in body["query"]
        assert body["variables"] == {"teamId": "team-1", "limit": 10}

    def test_build_create_issue_query(self):
        engine = ConnectorExecutionEngine()
        body = engine._build_linear_graphql(
            "linear.create_issue",
            {
                "teamId": "team-1",
                "title": "Bug fix",
            },
        )
        assert "mutation" in body["query"]
        assert body["variables"] == {"teamId": "team-1", "title": "Bug fix"}


# =============================================================================
# Atlassian per-product base URL resolution
# =============================================================================


class TestAtlassianBaseUrl:
    def test_jira_base_url(self):
        url = _get_base_url(
            "atlassian",
            {"instance_url": "https://my.atlassian.net"},
            "jira.list_projects",
        )
        assert url == "https://my.atlassian.net"

    def test_confluence_base_url(self):
        url = _get_base_url(
            "atlassian",
            {"instance_url": "https://my.atlassian.net"},
            "confluence.list_spaces",
        )
        assert url == "https://my.atlassian.net"

    def test_bitbucket_base_url(self):
        url = _get_base_url("atlassian", {}, "bitbucket.list_repos")
        assert url == "https://api.bitbucket.org/2.0"

    def test_jira_sm_base_url(self):
        url = _get_base_url(
            "atlassian",
            {"instance_url": "https://my.atlassian.net"},
            "jira_sm.list_requests",
        )
        assert url == "https://my.atlassian.net"

    def test_atlassian_fallback_without_tool_id(self):
        url = _get_base_url("atlassian", {"instance_url": "https://my.atlassian.net"})
        assert url == "https://my.atlassian.net"


# =============================================================================
# Atlassian basic auth with email
# =============================================================================


class TestAtlassianAuth:
    def test_atlassian_basic_auth_with_email(self):
        headers = _build_auth_headers(
            "atlassian",
            "basic_auth",
            "api_token_123",
            tool_id="jira.list_projects",
            form_data={"email": "user@example.com"},
        )
        import base64

        expected = (
            "Basic " + base64.b64encode(b"user@example.com:api_token_123").decode()
        )
        assert headers["Authorization"] == expected

    def test_atlassian_basic_auth_without_email(self):
        headers = _build_auth_headers("atlassian", "basic_auth", "tok")
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_atlassian_bearer_token(self):
        headers = _build_auth_headers("atlassian", "api_key", "bearer_tok")
        assert headers == {"Authorization": "Bearer bearer_tok"}


# =============================================================================
# Provider registry
# =============================================================================


class TestProviderRegistry:
    def test_atlassian_provider_registered(self):
        cls = get_provider("atlassian")
        assert cls is not None
        assert cls.provider_id == "atlassian"

    def test_github_provider_registered(self):
        cls = get_provider("github")
        assert cls is not None

    def test_slack_provider_registered(self):
        cls = get_provider("slack")
        assert cls is not None

    def test_all_connectors_have_providers(self):
        for seed in get_connector_seeds():
            cid = seed["id"]
            cls = get_provider(cid)
            assert cls is not None, f"Connector '{cid}' has no provider in providers/"
            # Verify every seeded tool is handled by the provider
            provider = cls(None)  # key_manager not needed for endpoint check
            if hasattr(provider, "endpoints"):
                for tool in seed.get("tools", []):
                    assert tool["id"] in provider.endpoints, (
                        f"Tool '{tool['id']}' not in {cid} provider endpoints"
                    )
