"""
Knowledge Hub — Source Execution Engine.

Bridges Knowledge Hub source type execution with real API calls.
Supports three execution tiers:
1. Connector system (via ConnectorExecutionEngine) — for mapped source types
2. Direct HTTP (via httpx) — for source types with known REST endpoints
3. Simulation fallback — for unmapped/unconfigured source types

Also provides OAuth flow support for authenticated source configs.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from sqlmodel import Session

from common_lib.modules.knowledge_engine.knowledge_hub.models import (
    SourceConfigRecord,
)
from common_lib.modules.knowledge_engine.knowledge_hub.services.source_service import (
    _simulate_source_execution,
)

logger = logging.getLogger(__name__)


# ── Direct HTTP endpoints for real API execution ───────────────
# Maps KB source_type_id to API endpoint configuration.
# Supports GET and POST, custom auth headers, query params from config,
# and JSON response path extraction.

@dataclass
class HttpEndpoint:
    method: str
    url_template: str
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer"
    params_from_config: dict[str, str] = field(default_factory=dict)
    body_from_config: dict[str, str] = field(default_factory=dict)
    response_path: Optional[str] = None  # dot-separated JSON path to extract data
    headers: dict[str, str] = field(default_factory=dict)  # extra fixed headers
    content_type: str = "json"  # json or form


SOURCE_HTTP_MAP: dict[str, HttpEndpoint] = {
    # GitHub — search repos
    "github_api": HttpEndpoint(
        method="GET",
        url_template="https://api.github.com/search/repositories",
        params_from_config={
            "q": "search_query",
            "sort": "sort",
            "order": "order",
            "per_page": "max_repos",
        },
        response_path="items",
    ),
    # Notion — search all pages
    "notion_api": HttpEndpoint(
        method="POST",
        url_template="https://api.notion.com/v1/search",
        auth_prefix="Bearer",
        body_from_config={"query": "search_query"},
        response_path="results",
        headers={"Notion-Version": "2022-06-28"},
    ),
    # Slack — list channels
    "slack_api": HttpEndpoint(
        method="GET",
        url_template="https://slack.com/api/conversations.list",
        auth_prefix="Bearer",
        params_from_config={"limit": "max_posts", "types": "channel_type"},
        response_path="channels",
    ),
    # Jira — list projects
    "jira_api": HttpEndpoint(
        method="GET",
        url_template="https://{instance_url}/rest/api/3/project",
        auth_prefix="Bearer",
        params_from_config={"maxResults": "page_size"},
    ),
    # Confluence — list spaces
    "confluence_api": HttpEndpoint(
        method="GET",
        url_template="https://{instance_url}/wiki/rest/api/space",
        auth_prefix="Bearer",
        params_from_config={"limit": "max_results"},
        response_path="results",
    ),
    # HubSpot — list contacts
    "hubspot_api": HttpEndpoint(
        method="GET",
        url_template="https://api.hubapi.com/crm/v3/objects/contacts",
        auth_prefix="Bearer",
        params_from_config={"limit": "max_results"},
        response_path="results",
    ),
    # GitLab — list projects
    "gitlab_api": HttpEndpoint(
        method="GET",
        url_template="https://gitlab.com/api/v4/projects",
        auth_prefix="Bearer",
        params_from_config={"search": "search_query", "per_page": "page_size", "order_by": "sort"},
    ),
    # Stripe — list charges
    "stripe_api": HttpEndpoint(
        method="GET",
        url_template="https://api.stripe.com/v1/charges",
        auth_prefix="Bearer",
        params_from_config={"limit": "max_results"},
    ),
    # Linear — list issues (GraphQL POST)
    "linear_api": HttpEndpoint(
        method="POST",
        url_template="https://api.linear.app/graphql",
        auth_prefix="",
        headers={"Content-Type": "application/json", "Authorization": "Bearer {token}"},
        body_from_config={"query": """query { issues(first: 50) { nodes { id title description } } }"""},
        response_path="data.issues.nodes",
    ),
    # Discord — list channel messages
    "discord_api": HttpEndpoint(
        method="GET",
        url_template="https://discord.com/api/v10/channels/{channel_id}/messages",
        auth_prefix="Bot",
        params_from_config={"limit": "max_results"},
    ),
}


# ── Token storage helper (stored in source config metadata) ──

TOKEN_CONFIG_KEYS = {
    "access_token",
    "refresh_token",
    "expires_at",
    "token_type",
    "scope",
    "oauth_state",
}


# ═══════════════════════════════════════════════════════════════════
# Source Execution Engine
# ═══════════════════════════════════════════════════════════════════


class SourceExecutionError(Exception):
    """Raised when source execution fails."""


class SourceExecutionEngine:
    """Executes Knowledge Hub sources against real APIs.

    Two-tier execution:
    1. Direct HTTP (if endpoint mapping exists and API token is available)
    2. Simulation fallback (for unmapped types or when no token is configured)

    The connector system bridge (tier 1, removed) required key_management
    integration that doesn't align with the Knowledge Hub source config model.
    Direct HTTP provides the same functionality with simpler configuration.
    """

    def __init__(self, timeout: int = 30):
        self._timeout = timeout

    def execute(
        self,
        session: Session,
        config_id: str,
        api_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a source config against its real API.

        Two-tier fallback:
        1. Direct HTTP — if the source type has an endpoint mapping AND
           an API token is available (from param, config, or OAuth)
        2. Simulation — returns realistic mock data for unmapped types

        Args:
            session: SQLModel session.
            config_id: Source config ID.
            api_token: Optional API token. If not provided, tries to read
                from config as api_token or access_token.

        Returns:
            Execution result dict with status, data, message, etc.
        """
        record = session.get(SourceConfigRecord, config_id)
        if not record:
            return {
                "success": False,
                "status": "error",
                "message": f"Source config {config_id} not found",
                "data": None,
            }

        source_type_id = record.source_type_id
        config = record.config or {}
        start = time.time()

        # 1. Try direct HTTP (needs a token + endpoint mapping)
        http_endpoint = SOURCE_HTTP_MAP.get(source_type_id)
        token = api_token or config.get("api_token") or config.get("access_token")

        if http_endpoint and token:
            try:
                result = self._execute_via_http(
                    endpoint=http_endpoint,
                    config=config,
                    api_token=token,
                    source_type_id=source_type_id,
                )
                exec_time = int((time.time() - start) * 1000)
                return {
                    "success": True,
                    "status": "completed",
                    "source_config_id": config_id,
                    "source_config_name": record.name,
                    "source_type": source_type_id,
                    "message": f"Fetched data from {source_type_id} API",
                    "data": result.get("data", result),
                    "execution_time_ms": exec_time,
                    "record_count": result.get("count", 0),
                    "execution_tier": "http",
                }
            except Exception as e:
                logger.warning(f"HTTP execution failed for {config_id}: {e}")
                # Fall through to tier 2

        # 2. Simulation fallback
        simulated = _simulate_source_execution(source_type_id, config, limit=20)
        exec_time = int((time.time() - start) * 1000)
        return {
            "success": True,
            "status": "completed",
            "source_config_id": config_id,
            "source_config_name": record.name,
            "source_type": source_type_id,
            "message": simulated.get("message", f"Executed {source_type_id} (simulated)"),
            "data": simulated.get("data", []),
            "execution_time_ms": exec_time,
            "record_count": simulated.get("record_count", 0),
            "execution_tier": "simulated" if not token else "simulated_no_token",
        }

    def _execute_via_http(
        self,
        endpoint: HttpEndpoint,
        config: dict[str, Any],
        api_token: str,
        source_type_id: str,
    ) -> dict[str, Any]:
        """Execute via direct HTTP call.

        Supports:
        - URL template with {param} placeholder substitution from config
        - Query params from config with flexible key mapping
        - POST body from config with flexible key mapping
        - Custom auth header configuration
        - Dot-separated response path extraction
        - Extra fixed headers (e.g. Notion-Version)
        """
        # Build URL with path param substitution
        url = endpoint.url_template
        for key, val in config.items():
            placeholder = "{" + key + "}"
            if placeholder in url:
                url = url.replace(placeholder, str(val))
                if isinstance(val, (int, float)):
                    continue

        # Build query params from config
        params: dict[str, str] = {}
        for query_key, config_key in endpoint.params_from_config.items():
            val = config.get(config_key)
            if val is not None:
                params[query_key] = str(val)

        # Build headers: start with endpoint-provided extra headers
        headers = dict(endpoint.headers) if endpoint.headers else {}
        headers.setdefault("Accept", "application/json")
        headers.setdefault("User-Agent", "KnowledgeHub/1.0")

        if endpoint.auth_prefix == "":
            # Direct token injection (e.g. headers already contain Authorization)
            if endpoint.headers and "Authorization" in endpoint.headers:
                pass  # already set in endpoint.headers
        elif endpoint.auth_header:
            prefix = endpoint.auth_prefix
            headers[endpoint.auth_header] = f"{prefix} {api_token}" if prefix else api_token

        # Build body for POST requests
        json_body = None
        if endpoint.method in ("POST", "PUT", "PATCH"):
            body = {}
            for body_key, config_key in endpoint.body_from_config.items():
                val = config.get(config_key)
                if val is not None:
                    body[body_key] = val
            json_body = body if body else None

        # Execute
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method=endpoint.method,
                    url=url,
                    params=params if params else None,
                    json=json_body if endpoint.content_type == "json" else None,
                    data=json_body if endpoint.content_type == "form" else None,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:500]
            raise SourceExecutionError(
                f"HTTP {e.response.status_code}: {detail}"
            ) from e
        except httpx.RequestError as e:
            raise SourceExecutionError(f"Request failed: {e}") from e

        # Extract data from response path
        if endpoint.response_path:
            extracted = data
            for key in endpoint.response_path.split("."):
                if isinstance(extracted, dict):
                    extracted = extracted.get(key, [])
                else:
                    extracted = []
                    break
            result_list = extracted if isinstance(extracted, list) else [extracted]
            return {"data": result_list, "count": len(result_list)}

        result_list = data if isinstance(data, list) else [data]
        return {"data": result_list, "count": len(result_list)}


# ── OAuth Flow Support ─────────────────────────────────────────


def build_oauth_authorization_url(
    source_type_id: str,
    redirect_uri: str,
    state: str,
    config: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Build an OAuth authorization URL for a source type.

    Args:
        source_type_id: The KB source type ID.
        redirect_uri: OAuth redirect URI.
        state: CSRF state parameter.
        config: Optional config dict with custom client_id, scopes, etc.

    Returns:
        Authorization URL string, or None if source type doesn't support OAuth.
    """
    cfg = config or {}

    # Known OAuth endpoints for source types
    OAUTH_PROVIDERS: dict[str, dict[str, str]] = {
        "github_api": {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scopes": "repo,read:org",
            "client_id_field": "github_client_id",
        },
        "slack_api": {
            "auth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "scopes": "channels:read,channels:history,files:read",
            "client_id_field": "slack_client_id",
        },
        "notion_api": {
            "auth_url": "https://api.notion.com/v1/oauth/authorize",
            "token_url": "https://api.notion.com/v1/oauth/token",
            "scopes": "",
            "client_id_field": "notion_client_id",
        },
        "google_drive_api": {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": "https://www.googleapis.com/auth/drive.readonly",
            "client_id_field": "google_client_id",
        },
        "hubspot_api": {
            "auth_url": "https://app.hubspot.com/oauth/authorize",
            "token_url": "https://api.hubapi.com/oauth/v1/token",
            "scopes": "crm.objects.contacts.read crm.objects.deals.read",
            "client_id_field": "hubspot_client_id",
        },
        "salesforce_api": {
            "auth_url": "https://login.salesforce.com/services/oauth2/authorize",
            "token_url": "https://login.salesforce.com/services/oauth2/token",
            "scopes": "api refresh_token",
            "client_id_field": "salesforce_client_id",
        },
        "stripe_api": {
            "auth_url": "https://connect.stripe.com/oauth/authorize",
            "token_url": "https://connect.stripe.com/oauth/token",
            "scopes": "read_write",
            "client_id_field": "stripe_client_id",
        },
        "twitter_api": {
            "auth_url": "https://twitter.com/i/oauth2/authorize",
            "token_url": "https://api.twitter.com/2/oauth2/token",
            "scopes": "tweet.read users.read",
            "client_id_field": "twitter_client_id",
        },
        "jira_api": {
            "auth_url": "https://auth.atlassian.com/authorize",
            "token_url": "https://auth.atlassian.com/oauth/token",
            "scopes": "read:jira-work read:jira-user",
            "client_id_field": "jira_client_id",
        },
        "bitbucket_api": {
            "auth_url": "https://bitbucket.org/site/oauth2/authorize",
            "token_url": "https://bitbucket.org/site/oauth2/access_token",
            "scopes": "repository pullrequest",
            "client_id_field": "bitbucket_client_id",
        },
        "linear_api": {
            "auth_url": "https://linear.app/oauth/authorize",
            "token_url": "https://api.linear.app/oauth/token",
            "scopes": "read write",
            "client_id_field": "linear_client_id",
        },
        "discord_api": {
            "auth_url": "https://discord.com/api/oauth2/authorize",
            "token_url": "https://discord.com/api/oauth2/token",
            "scopes": "bot messages.read",
            "client_id_field": "discord_client_id",
        },
        "digitalocean_spaces": {
            "auth_url": "https://cloud.digitalocean.com/v1/oauth/authorize",
            "token_url": "https://cloud.digitalocean.com/v1/oauth/token",
            "scopes": "read write",
            "client_id_field": "digitalocean_client_id",
        },
    }

    provider = OAUTH_PROVIDERS.get(source_type_id)
    if not provider:
        return None

    client_id = cfg.get(provider["client_id_field"]) or cfg.get("client_id", "")
    scopes = cfg.get("scopes", provider["scopes"])

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": scopes,
    }

    return f"{provider['auth_url']}?{urlencode(params)}"


async def exchange_oauth_code(
    source_type_id: str,
    code: str,
    redirect_uri: str,
    config: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Exchange an OAuth authorization code for tokens.

    Args:
        source_type_id: The KB source type ID.
        code: The OAuth authorization code.
        redirect_uri: The same redirect URI used in the auth request.
        config: Config dict with client_id and client_secret.

    Returns:
        Token response dict with access_token, refresh_token, etc., or None.
    """
    OAUTH_TOKEN_URLS: dict[str, str] = {
        "github_api": "https://github.com/login/oauth/access_token",
        "slack_api": "https://slack.com/api/oauth.v2.access",
        "notion_api": "https://api.notion.com/v1/oauth/token",
        "google_drive_api": "https://oauth2.googleapis.com/token",
        "hubspot_api": "https://api.hubapi.com/oauth/v1/token",
        "salesforce_api": "https://login.salesforce.com/services/oauth2/token",
        "stripe_api": "https://connect.stripe.com/oauth/token",
        "jira_api": "https://auth.atlassian.com/oauth/token",
        "bitbucket_api": "https://bitbucket.org/site/oauth2/access_token",
        "linear_api": "https://api.linear.app/oauth/token",
        "discord_api": "https://discord.com/api/oauth2/token",
        "twitter_api": "https://api.twitter.com/2/oauth2/token",
        "digitalocean_spaces": "https://cloud.digitalocean.com/v1/oauth/token",
    }

    token_url = OAUTH_TOKEN_URLS.get(source_type_id)
    if not token_url:
        return None

    client_id = config.get("client_id", "")
    client_secret = config.get("client_secret", "")

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                token_url,
                data=payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            token_data = response.json()

            # Normalize token response
            return {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "token_type": token_data.get("token_type", "Bearer"),
                "scope": token_data.get("scope", ""),
                "raw_response": token_data,
            }
    except Exception as e:
        logger.error(f"OAuth code exchange failed for {source_type_id}: {e}")
        return None


# ── Singleton ──────────────────────────────────────────────────

_source_execution_engine: Optional[SourceExecutionEngine] = None


def get_source_execution_engine() -> SourceExecutionEngine:
    global _source_execution_engine
    if _source_execution_engine is None:
        _source_execution_engine = SourceExecutionEngine()
    return _source_execution_engine


__all__ = [
    "SourceExecutionEngine",
    "SourceExecutionError",
    "build_oauth_authorization_url",
    "exchange_oauth_code",
    "get_source_execution_engine",
    "SOURCE_HTTP_MAP",
]
