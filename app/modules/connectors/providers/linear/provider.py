from typing import Any, Dict, Optional

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "linear"
    display_name = "Linear"
    base_url = "https://api.linear.app"
    endpoints = {
        "linear.list_issues": ("POST", "/graphql"),
        "linear.create_issue": ("POST", "/graphql"),
        "linear.list_teams": ("POST", "/graphql"),
        "linear.get_user": ("POST", "/graphql"),
    }

    def build_auth_headers(self, auth_scheme: str, key_value: str, form_data: Dict[str, Any]) -> Dict[str, str]:
        return {"Authorization": key_value}

    def build_body(self, tool_id: str, method: str, params: Dict[str, Any], form_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
                        teamId: $teamId, title: $title, description: $description,
                        priority: $priority, assigneeId: $assigneeId
                    }) { success issue { id title } }
                }
            """,
            "linear.list_teams": """
                query ListTeams { teams { nodes { id name key } } }
            """,
            "linear.get_user": """
                query GetUser { viewer { id name email } }
            """,
        }
        query = queries.get(tool_id, "")
        variables = {k: v for k, v in params.items() if v is not None}
        return {"query": query, "variables": variables}
