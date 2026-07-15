"""MCP tools for RBAC, Teams & Collaboration (UDS Module 19)."""

from typing import Dict, List, Optional

from common_lib.modules.db_studio.collaboration import (
    CollaborationService,
    OrganizationCreate, WorkspaceCreate, TeamCreate,
    RoleCreate, ResourcePermissionGrant,
    CommentCreate, ReviewCreate,
)

svc = CollaborationService()


def register_collaboration_tools(mcp_server):
    """Register all collaboration tools with the MCP server."""

    @mcp_server.tool()
    async def create_organization(name: str, slug: str, description: str = None) -> str:
        """Create an organization."""
        req = OrganizationCreate(name=name, slug=slug, description=description)
        result = svc.create_organization(req)
        return f"Created organization: {result.name} ({result.slug}, id={result.id})"

    @mcp_server.tool()
    async def list_organizations(limit: int = 20) -> str:
        """List organizations."""
        results = svc.list_organizations(limit)
        if not results:
            return "No organizations found."
        lines = [f"**Organizations** ({len(results)}):"]
        for o in results:
            lines.append(f"- {o.name} ({o.slug}, active={o.is_active})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_workspace(org_id: str, name: str, environment: str = "development",
                               description: str = None) -> str:
        """Create a workspace within an organization."""
        req = WorkspaceCreate(org_id=org_id, name=name, environment=environment, description=description)
        result = svc.create_workspace(req)
        return f"Created workspace: {result.name} ({result.environment})"

    @mcp_server.tool()
    async def list_workspaces(org_id: str = None, limit: int = 20) -> str:
        """List workspaces."""
        results = svc.list_workspaces(org_id, limit)
        if not results:
            return "No workspaces found."
        lines = [f"**Workspaces** ({len(results)}):"]
        for w in results:
            lines.append(f"- {w.name} ({w.environment})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_team(org_id: str, name: str, description: str = None) -> str:
        """Create a team."""
        req = TeamCreate(org_id=org_id, name=name, description=description)
        result = svc.create_team(req)
        return f"Created team: {result.name} (id={result.id})"

    @mcp_server.tool()
    async def list_teams(org_id: str = None, limit: int = 20) -> str:
        """List teams."""
        results = svc.list_teams(org_id, limit)
        if not results:
            return "No teams found."
        lines = [f"**Teams** ({len(results)}):"]
        for t in results:
            lines.append(f"- {t.name} (active={t.is_active})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def add_team_member(team_id: str, user_id: str, role: str = "member") -> str:
        """Add a member to a team."""
        result = svc.add_team_member(team_id, user_id, role)
        return f"Added user {result.user_id} to team {result.team_id} as {result.role}"

    @mcp_server.tool()
    async def list_team_members(team_id: str) -> str:
        """List members of a team."""
        results = svc.list_team_members(team_id)
        if not results:
            return "No members found."
        lines = [f"**Team Members** ({len(results)}):"]
        for m in results:
            lines.append(f"- user={m.user_id}, role={m.role}")
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_role(org_id: str, name: str, permissions: List[str] = None) -> str:
        """Create a role with permissions."""
        req = RoleCreate(org_id=org_id, name=name, permissions=permissions)
        result = svc.create_role(req)
        return f"Created role: {result.name} (id={result.id}, scope={result.scope})"

    @mcp_server.tool()
    async def list_permissions(resource_type: str = None, limit: int = 50) -> str:
        """List available system permissions."""
        results = svc.list_permissions(resource_type, limit)
        if not results:
            return "No permissions found."
        lines = [f"**Permissions** ({len(results)}):"]
        for p in results:
            lines.append(f"- {p.name} ({p.resource_type}:{p.action})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def grant_resource_permission(resource_type: str, resource_id: str,
                                         grantee_type: str, grantee_id: str,
                                         permissions: List[str]) -> str:
        """Grant permissions on a resource to a user/team/role."""
        req = ResourcePermissionGrant(
            resource_type=resource_type, resource_id=resource_id,
            grantee_type=grantee_type, grantee_id=grantee_id,
            permissions=permissions,
        )
        result = svc.grant_permission(req)
        return f"Granted {len(permissions)} permissions on {resource_type}:{resource_id} to {grantee_type}:{grantee_id}"

    @mcp_server.tool()
    async def create_comment(resource_type: str, resource_id: str, body: str) -> str:
        """Add a comment to a resource."""
        req = CommentCreate(resource_type=resource_type, resource_id=resource_id, body=body)
        result = svc.create_comment(req)
        return f"Created comment on {resource_type}:{resource_id} (id={result.id})"

    @mcp_server.tool()
    async def list_comments(resource_type: str, resource_id: str, limit: int = 20) -> str:
        """List comments on a resource."""
        results = svc.list_comments(resource_type, resource_id, limit)
        if not results:
            return "No comments found."
        lines = [f"**Comments** on {resource_type}:{resource_id} ({len(results)}):"]
        for c in results:
            lines.append(f"- [{c.author_id}]: {c.body[:80]}")
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_review(resource_type: str, resource_id: str, title: str,
                            description: str = None, reviewers: List[str] = None) -> str:
        """Create a review request."""
        req = ReviewCreate(resource_type=resource_type, resource_id=resource_id,
                           title=title, description=description, reviewers=reviewers)
        result = svc.create_review(req)
        return f"Created review: {result.title} (id={result.id}, status={result.status})"

    @mcp_server.tool()
    async def list_notifications(user_id: str = None, is_read: bool = None, limit: int = 20) -> str:
        """List user notifications."""
        results = svc.list_notifications(user_id, is_read, limit)
        if not results:
            return "No notifications found."
        lines = [f"**Notifications** ({len(results)}):"]
        for n in results:
            lines.append(f"- [{n.notification_type}] {n.title} (read={n.is_read})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def get_activity_feed(org_id: str = None, limit: int = 20) -> str:
        """Get collaboration activity feed."""
        results = svc.list_activity(org_id, limit)
        if not results:
            return "No activity found."
        lines = [f"**Activity Feed** ({len(results)}):"]
        for a in results:
            lines.append(f"- {a.actor_id} {a.action} {a.resource_type} ({a.resource_name or a.resource_id})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def get_collaboration_dashboard() -> str:
        """Get collaboration dashboard summary."""
        dash = svc.get_dashboard()
        return (
            f"**Collaboration Dashboard**\n"
            f"- Organizations: {dash.total_orgs}\n"
            f"- Workspaces: {dash.total_workspaces}\n"
            f"- Teams: {dash.total_teams}\n"
            f"- Members: {dash.total_members}\n"
            f"- Pending Reviews: {dash.pending_reviews}\n"
            f"- Unread Notifications: {dash.unread_notifications}\n"
            f"- Recent Activity: {len(dash.recent_activity)} events"
        )
