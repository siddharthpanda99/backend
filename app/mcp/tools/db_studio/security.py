"""MCP tools for Security, Auth & Secret Management (UDS Module 18)."""

from typing import Dict, List, Optional

from common_lib.modules.db_studio.security import (
    SecurityService,
    LoginRequest, UserCreate, ApiKeyCreate, SecretCreate,
    CertificateCreate, SecurityPolicyCreate,
)

svc = SecurityService()


def register_security_tools(mcp_server):
    """Register all security tools with the MCP server."""

    @mcp_server.tool()
    async def login(username: str, password: str = None, provider: str = "local") -> str:
        """Authenticate a user and create a session."""
        req = LoginRequest(username=username, password=password or "password", provider=provider)
        result = svc.login(req)
        return f"Logged in as {result.username} (user_id={result.user_id}, mfa={result.mfa_required})"

    @mcp_server.tool()
    async def list_sessions(user_id: str = None, is_active: bool = None, limit: int = 10) -> str:
        """List authentication sessions."""
        results = svc.list_sessions(user_id, is_active, limit)
        if not results:
            return "No sessions found."
        lines = [f"**Sessions** ({len(results)}):"]
        for s in results:
            lines.append(f"- user={s.user_id}, active={s.is_active}, expires={s.expires_at}")
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_user(username: str, email: str = None,
                          roles: List[str] = None) -> str:
        """Create a new user account."""
        req = UserCreate(username=username, email=email, roles=roles)
        try:
            result = svc.create_user(req)
            return f"Created user: {result.username} ({result.id}), provider={result.auth_provider}"
        except ValueError as e:
            return f"Error: {e}"

    @mcp_server.tool()
    async def list_users(status: str = None, limit: int = 20) -> str:
        """List user accounts."""
        results = svc.list_users(status, limit)
        if not results:
            return "No users found."
        lines = [f"**Users** ({len(results)}):"]
        for u in results:
            lines.append(f"- {u.username} ({u.status}, provider={u.auth_provider})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def create_api_key(name: str, user_id: str = None,
                             scopes: List[str] = None,
                             expires_in_days: int = 90) -> str:
        """Create a new API key (returns full key once)."""
        req = ApiKeyCreate(name=name, user_id=user_id, scopes=scopes, expires_in_days=expires_in_days)
        result = svc.create_api_key(req)
        return f"Created API key: {result.name}\nKey: {result.full_key}\n(Save this key - it won't be shown again)"

    @mcp_server.tool()
    async def list_api_keys(user_id: str = None, limit: int = 20) -> str:
        """List API keys."""
        results = svc.list_api_keys(user_id, limit)
        if not results:
            return "No API keys found."
        lines = [f"**API Keys** ({len(results)}):"]
        for k in results:
            lines.append(f"- {k.name} ({k.key_prefix}..., active={k.is_active})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def revoke_api_key(key_id: str) -> str:
        """Revoke an API key."""
        result = svc.revoke_api_key(key_id)
        if not result:
            return f"API key {key_id} not found."
        return f"Revoked API key: {result.name}"

    @mcp_server.tool()
    async def create_secret(name: str, value: str, secret_type: str = "password",
                            description: str = None, is_rotatable: bool = False) -> str:
        """Store a secret securely."""
        req = SecretCreate(name=name, value=value, secret_type=secret_type,
                           description=description, is_rotatable=is_rotatable)
        result = svc.create_secret(req)
        return f"Created secret: {result.name} ({result.id}, v{result.version})"

    @mcp_server.tool()
    async def list_secrets(limit: int = 20) -> str:
        """List stored secrets (values hidden)."""
        results = svc.list_secrets(limit=limit)
        if not results:
            return "No secrets found."
        lines = [f"**Secrets** ({len(results)}):"]
        for s in results:
            lines.append(f"- {s.name} (v{s.version}, provider={s.provider})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def list_audit_events(severity: str = None, event_type: str = None,
                                limit: int = 20) -> str:
        """List security audit events."""
        results = svc.list_audit_events(event_type, severity, limit=limit)
        if not results:
            return "No audit events found."
        lines = [f"**Audit Events** ({len(results)}):"]
        for e in results:
            lines.append(f"- [{e.severity}] {e.event_type}: {e.action} on {e.resource_type} ({e.status})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def run_compliance_scan(report_type: str = "soc2") -> str:
        """Run a compliance scan."""
        result = svc.run_compliance_scan(report_type)
        return (
            f"**Compliance Scan Complete** ({report_type.upper()})\n"
            f"- Status: {result.status}\n"
            f"- Pass Rate: {result.pass_percentage}%\n"
            f"- {result.passed_checks}/{result.total_checks} passed\n"
            f"- {result.failed_checks} failed, {result.warnings_count} warnings"
        )

    @mcp_server.tool()
    async def create_security_policy(name: str, policy_type: str,
                                     description: str = None,
                                     severity: str = "medium",
                                     config: Dict[str, object] = None) -> str:
        """Create a security policy."""
        req = SecurityPolicyCreate(name=name, policy_type=policy_type,
                                    description=description, severity=severity,
                                    config=config)
        result = svc.create_policy(req)
        return f"Created policy: {result.name} ({result.id}, type={result.policy_type})"

    @mcp_server.tool()
    async def list_policies(policy_type: str = None, enabled: bool = None,
                            limit: int = 20) -> str:
        """List security policies."""
        results = svc.list_policies(policy_type, enabled, limit)
        if not results:
            return "No policies found."
        lines = [f"**Security Policies** ({len(results)}):"]
        for p in results:
            lines.append(f"- {p.name} ({p.policy_type}, enabled={p.enabled}, severity={p.severity})")
        return "\n".join(lines)

    @mcp_server.tool()
    async def get_security_dashboard() -> str:
        """Get security dashboard summary."""
        dash = svc.get_dashboard()
        return (
            f"**Security Dashboard**\n"
            f"- Users: {dash.total_users}\n"
            f"- Active Sessions: {dash.active_sessions}\n"
            f"- Active API Keys: {dash.active_api_keys}\n"
            f"- Secrets: {dash.total_secrets}\n"
            f"- Active Certificates: {dash.active_certificates}\n"
            f"- Policies Enforced: {dash.policies_enforced}\n"
            f"- Compliance: {dash.compliance_pass_rate or 'N/A'}%\n"
            f"- Recent Audit Events: {len(dash.recent_audit_events)}"
        )
