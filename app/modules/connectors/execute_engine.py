"""Connector Execution Engine — Phase 3.

Routes tool execution to per-connector providers.
Each connector has its own sub-package under providers/ with a provider.py
that handles endpoint mapping, auth, base URL, and HTTP dispatch.

Fallback: connectors without a dedicated provider use the generic REST logic
defined in this module (TOOL_ENDPOINTS + _get_base_url + _build_auth_headers).

Usage:
    engine = ConnectorExecutionEngine()
    result = engine.execute(connector_id, tool_id, params, connection, form_data)
"""

import base64
import logging
import re
from typing import Any, Dict, Optional, Tuple

import httpx

from common_lib.modules.plugins.connectors.keys import get_connector_key_manager
from common_lib.modules.plugins.connectors.models.connection import Connection
from common_lib.modules.plugins.connectors.exceptions import (
    ExecutionError,
    KeyNotFoundError,
)
from app.modules.connectors.providers import get_provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback endpoint registry (for connectors without dedicated providers)
# ---------------------------------------------------------------------------

TOOL_ENDPOINTS: Dict[str, Tuple[str, str]] = {
    # === GitHub === (has provider, kept here for backward compat)
    "github.list_repos": ("GET", "/user/repos"),
    "github.get_repo": ("GET", "/repos/{owner}/{repo}"),
    "github.list_issues": ("GET", "/repos/{owner}/{repo}/issues"),
    "github.create_issue": ("POST", "/repos/{owner}/{repo}/issues"),
    "github.list_pull_requests": ("GET", "/repos/{owner}/{repo}/pulls"),
    # === Jira === (has provider, kept here for backward compat)
    "jira.list_projects": ("GET", "/rest/api/3/project"),
    "jira.search_issues": ("GET", "/rest/api/3/search/jql"),
    "jira.create_issue": ("POST", "/rest/api/3/issue"),
    # === Confluence ===
    "confluence.list_spaces": ("GET", "/wiki/rest/api/space"),
    "confluence.get_page": ("GET", "/wiki/rest/api/content/{page_id}"),
    "confluence.search": ("GET", "/wiki/rest/api/search"),
    "confluence.create_page": ("POST", "/wiki/rest/api/content"),
    # === Bitbucket ===
    "bitbucket.list_repos": ("GET", "/2.0/repositories/{workspace}"),
    "bitbucket.list_pull_requests": (
        "GET",
        "/2.0/repositories/{workspace}/{repo}/pullrequests",
    ),
    "bitbucket.get_pipeline_status": (
        "GET",
        "/2.0/repositories/{workspace}/{repo}/pipelines/{pipeline_uuid}",
    ),
    "bitbucket.list_branches": (
        "GET",
        "/2.0/repositories/{workspace}/{repo}/refs/branches",
    ),
    # === Jira Service Management ===
    "jira_sm.list_requests": ("GET", "/rest/servicedeskapi/request"),
    "jira_sm.create_request": ("POST", "/rest/servicedeskapi/request"),
    # === Slack ===
    "slack.post_message": ("POST", "/chat.postMessage"),
    "slack.list_channels": ("GET", "/conversations.list"),
    "slack.get_channel_history": ("GET", "/conversations.history"),
    # === Discord ===
    "discord.send_message": ("POST", "/channels/{channel_id}/messages"),
    "discord.get_channel_messages": ("GET", "/channels/{channel_id}/messages"),
    # === Notion ===
    "notion.search": ("POST", "/search"),
    "notion.retrieve_page": ("GET", "/pages/{page_id}"),
    "notion.create_page": ("POST", "/pages"),
    "notion.query_database": ("POST", "/databases/{database_id}/query"),
    # === Google Drive ===
    "google_drive.list_files": ("GET", "/files"),
    "google_drive.get_file": ("GET", "/files/{file_id}"),
    "google_drive.upload_file": ("POST", "/files"),
    # === Dropbox ===
    "dropbox.list_files": ("POST", "/files/list_folder"),
    "dropbox.download_file": ("POST", "/files/download"),
    # === Airtable ===
    "airtable.list_records": ("GET", "/{base_id}/{table_name}"),
    "airtable.create_record": ("POST", "/{base_id}/{table_name}"),
    "airtable.update_record": ("PATCH", "/{base_id}/{table_name}/{record_id}"),
    # === HubSpot ===
    "hubspot.list_contacts": ("GET", "/crm/v3/objects/contacts"),
    "hubspot.create_contact": ("POST", "/crm/v3/objects/contacts"),
    "hubspot.list_deals": ("GET", "/crm/v3/objects/deals"),
    # === Salesforce ===
    "salesforce.soql_query": ("GET", "/services/data/v{api_version}/query"),
    "salesforce.describe_object": (
        "GET",
        "/services/data/v{api_version}/sobjects/{object_name}/describe",
    ),
    "salesforce.create_record": (
        "POST",
        "/services/data/v{api_version}/sobjects/{object_name}",
    ),
    # === Stripe ===
    "stripe.list_charges": ("GET", "/v1/charges"),
    "stripe.list_customers": ("GET", "/v1/customers"),
    "stripe.create_customer": ("POST", "/v1/customers"),
    "stripe.create_payment_intent": ("POST", "/v1/payment_intents"),
    # === PayPal ===
    "paypal.create_order": ("POST", "/v2/checkout/orders"),
    "paypal.capture_order": ("POST", "/v2/checkout/orders/{order_id}/capture"),
    # === Twilio ===
    "twilio.send_sms": (
        "POST",
        "/2010-04-01/Accounts/{account_sid}/Messages.json",
    ),
    # === SendGrid ===
    "sendgrid.send_email": ("POST", "/v3/mail/send"),
    # === AWS ===
    "aws.s3_list_buckets": ("GET", "/"),
    "aws.s3_list_objects": ("GET", "/{bucket}"),
    "aws.ec2_describe_instances": ("POST", "/"),
    # === GCP ===
    "gcp.list_storage_buckets": ("GET", "/storage/v1/b"),
    "gcp.list_compute_instances": (
        "GET",
        "/compute/v1/projects/{project_id}/zones/{zone}/instances",
    ),
    # === Azure ===
    "azure.list_resource_groups": (
        "GET",
        "/subscriptions/{subscription_id}/resourcegroups",
    ),
    "azure.list_vms": (
        "GET",
        "/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines",
    ),
    # === DigitalOcean ===
    "digitalocean.list_droplets": ("GET", "/v2/droplets"),
    "digitalocean.create_droplet": ("POST", "/v2/droplets"),
    "digitalocean.list_kubernetes_clusters": ("GET", "/v2/kubernetes/clusters"),
    # === GitLab ===
    "gitlab.list_projects": ("GET", "/projects"),
    "gitlab.list_issues": ("GET", "/projects/{project_id}/issues"),
    "gitlab.create_issue": ("POST", "/projects/{project_id}/issues"),
    "gitlab.list_pipelines": ("GET", "/projects/{project_id}/pipelines"),
    # === Linear ===
    "linear.list_issues": ("POST", "/graphql"),
    "linear.create_issue": ("POST", "/graphql"),
    "linear.list_teams": ("POST", "/graphql"),
    "linear.get_user": ("POST", "/graphql"),
}


# ---------------------------------------------------------------------------
# Fallback base URL resolvers
# ---------------------------------------------------------------------------


def _get_base_url(
    connector_id: str, form_data: Dict[str, Any], tool_id: str = ""
) -> str:
    defaults: Dict[str, str] = {
        "github": "https://api.github.com",
        "slack": "https://slack.com/api",
        "discord": "https://discord.com/api/v10",
        "notion": "https://api.notion.com/v1",
        "google_drive": "https://www.googleapis.com/drive/v3",
        "dropbox": "https://api.dropboxapi.com",
        "airtable": "https://api.airtable.com/v0",
        "hubspot": "https://api.hubapi.com",
        "stripe": "https://api.stripe.com",
        "twilio": "https://api.twilio.com",
        "sendgrid": "https://api.sendgrid.com",
        "digitalocean": "https://api.digitalocean.com",
        "linear": "https://api.linear.app",
    }

    if connector_id == "atlassian":
        prefix = tool_id.split(".")[0] if tool_id else ""
        if prefix in ("jira", "confluence", "jira_sm"):
            return (form_data.get("atlassian_instance_url") or form_data.get("instance_url") or "").rstrip("/")
        if prefix == "bitbucket":
            return "https://api.bitbucket.org/2.0"
        return (form_data.get("atlassian_instance_url") or form_data.get("instance_url") or "").rstrip("/")
    if connector_id == "salesforce":
        return (form_data.get("instance_url") or "").rstrip("/")
    if connector_id == "gitlab":
        base = form_data.get("instance_url", "https://gitlab.com").rstrip("/")
        return f"{base}/api/v4"
    if connector_id == "paypal":
        mode = form_data.get("mode", "sandbox")
        return (
            "https://api-m.paypal.com"
            if mode == "live"
            else "https://api-m.sandbox.paypal.com"
        )
    if connector_id == "aws":
        return f"https://s3.{form_data.get('region', 'us-east-1')}.amazonaws.com"
    if connector_id == "gcp":
        return "https://www.googleapis.com"
    if connector_id == "azure":
        return "https://management.azure.com"

    return defaults.get(connector_id, "")


# ---------------------------------------------------------------------------
# Fallback auth header builders
# ---------------------------------------------------------------------------


def _build_auth_headers(
    connector_id: str,
    auth_scheme: str,
    key_value: str,
    tool_id: str = "",
    form_data: Dict[str, Any] = None,
) -> Dict[str, str]:
    if form_data is None:
        form_data = {}

    if auth_scheme == "bearer_token":
        return {"Authorization": f"Bearer {key_value}"}
    if auth_scheme == "basic_auth":
        if connector_id == "atlassian":
            email = form_data.get("atlassian_email") or form_data.get("email", "")
            token = base64.b64encode(f"{email}:{key_value}".encode()).decode()
        else:
            token = base64.b64encode(f"{key_value}:".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    if auth_scheme == "api_key":
        if connector_id == "gitlab":
            return {"PRIVATE-TOKEN": key_value}
        if connector_id == "linear":
            return {"Authorization": key_value}
        return {"Authorization": f"Bearer {key_value}"}

    return {"Authorization": f"Bearer {key_value}"}


# ---------------------------------------------------------------------------
# Fallback path parameter substitution
# ---------------------------------------------------------------------------

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")


def _substitute_path_params(
    path: str,
    params: Dict[str, Any],
    form_data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    remaining = dict(params)

    def _replacer(m: re.Match) -> str:
        key = m.group(1)
        val = remaining.pop(key, None) or form_data.get(key)
        if val is None:
            raise ExecutionError(f"Missing required path parameter: '{key}'")
        return str(val)

    resolved = _PATH_PARAM_RE.sub(_replacer, path)
    return resolved, remaining


# ---------------------------------------------------------------------------
# Engine — routes to per-connector providers with fallback
# ---------------------------------------------------------------------------


class ConnectorExecutionEngine:
    """Executes connector tools against real REST APIs.

    Routes to per-connector providers when available; falls back to
    the generic TOOL_ENDPOINTS + _get_base_url + _build_auth_headers logic.
    """

    def __init__(self, timeout: int = 30):
        self._key_manager = get_connector_key_manager()
        self._timeout = timeout

    def execute(
        self,
        connector_id: str,
        tool_id: str,
        params: Dict[str, Any],
        connection: Connection,
        form_data: Dict[str, Any],
    ) -> Any:
        provider_cls = get_provider(connector_id)
        if provider_cls is not None:
            provider = provider_cls(self._key_manager, self._timeout)
            return provider.execute(tool_id, params, connection, form_data)

        return self._fallback_execute(
            connector_id, tool_id, params, connection, form_data
        )

    def _fallback_execute(
        self,
        connector_id: str,
        tool_id: str,
        params: Dict[str, Any],
        connection: Connection,
        form_data: Dict[str, Any],
    ) -> Any:
        endpoint = TOOL_ENDPOINTS.get(tool_id)
        if not endpoint:
            raise ExecutionError(
                f"No endpoint mapping for tool '{tool_id}'. "
                f"Supported tools: {', '.join(sorted(TOOL_ENDPOINTS.keys()))}"
            )

        method, path_template = endpoint
        base_url = _get_base_url(connector_id, form_data, tool_id)
        if not base_url:
            raise ExecutionError(
                f"Could not resolve base URL for connector '{connector_id}'. "
                "Ensure the connection form has the required URL fields."
            )

        path, remaining_params = _substitute_path_params(
            path_template, params, form_data
        )
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

        try:
            key_value = self._key_manager.resolve(connection)
        except KeyNotFoundError as e:
            raise ExecutionError(
                f"API key resolution failed for connection '{connection.id}': {e}"
            ) from e

        headers = _build_auth_headers(
            connector_id, connection.auth_scheme, key_value, tool_id, form_data
        )
        headers.setdefault("Accept", "application/json")

        if connector_id == "notion":
            headers["Notion-Version"] = "2022-06-28"
        if connector_id == "digitalocean":
            headers["Content-Type"] = "application/json"

        is_json_body = method in ("POST", "PUT", "PATCH")
        query_params = None
        json_body = None

        if is_json_body:
            if connector_id == "linear":
                json_body = self._build_linear_graphql(tool_id, remaining_params)
            elif connector_id in ("stripe", "twilio"):
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                json_body = None
                query_params = remaining_params
            else:
                json_body = remaining_params if remaining_params else None
        else:
            query_params = remaining_params if remaining_params else None

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=json_body,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json() if response.content else {"status": "ok"}
                return {
                    "__exec_result__": data,
                    "__http_status__": response.status_code,
                    "__response_headers__": dict(response.headers),
                }
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:500]
            # Even on error, return the HTTP status and headers
            raise ExecutionError(
                f"HTTP {e.response.status_code} on {method} {path}: {detail}"
            ) from e
        except httpx.RequestError as e:
            raise ExecutionError(f"Request failed for {method} {url}: {e}") from e

    def _build_linear_graphql(
        self, tool_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        queries = {
            "linear.list_issues": """
                query ListIssues($teamId: String, $status: String, $assigneeId: String, $limit: Int) {
                    issues(first: $limit, filter: {
                        team: { id: { eq: $teamId } },
                        state: { name: { eq: $status } },
                        assignee: { id: { eq: $assigneeId } }
                    }) { nodes { id title description priority state { name } assignee { id name } } }
                }
            """,
            "linear.create_issue": """
                mutation CreateIssue($teamId: String!, $title: String!, $description: String, $priority: Int, $assigneeId: String) {
                    issueCreate(input: {
                        teamId: $teamId,
                        title: $title,
                        description: $description,
                        priority: $priority,
                        assigneeId: $assigneeId
                    }) { success issue { id title } }
                }
            """,
            "linear.list_teams": """
                query ListTeams {
                    teams { nodes { id name key } }
                }
            """,
            "linear.get_user": """
                query GetUser {
                    viewer { id name email }
                }
            """,
        }
        query = queries.get(tool_id, "")
        variables = {k: v for k, v in params.items() if v is not None}
        return {"query": query, "variables": variables}


engine = ConnectorExecutionEngine()


def get_execution_engine() -> ConnectorExecutionEngine:
    return engine
