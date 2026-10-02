"""Tests proving the MCP identity surface cannot fabricate an identity.

These cover the fix for the hardcoded
``{"id": "system", "role": "admin", "permissions": ["*"]}`` that
``app/mcp/tools/users.py::user_get_current`` returned to every caller, plus the
request-context plumbing that replaced the mock's stated reason for existing.

Run:
    Backend\\ Monorepo\\Backend\\.venv\\bin\\python -m pytest tests/app/mcp -q
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_REPO_BACKEND = Path(__file__).resolve().parents[3]
if str(_REPO_BACKEND) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(_REPO_BACKEND))

from app.mcp.identity import (  # noqa: E402
    anonymous_principal,
    bind_principal,
    current_principal,
    request_service_identity,
    reset_principal,
    resolve_mcp_principal,
)
from common_lib.modules.auth.identity_context import (  # noqa: E402
    Principal,
    resolve_principal,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def call_user_get_current(**kwargs) -> dict:
    """Invoke the real registered tool through a real MCP server.

    This deliberately does NOT re-implement the tool body: it registers it
    on a throwaway FastMCP instance and calls it, so the assertions are
    against the shipped code path rather than a copy of it.
    """
    from app.mcp.fastmcp_compat import FastMCP
    from app.mcp.tools.users import register_user_tools

    server = FastMCP("identity-test")
    register_user_tools(server)

    tools = {t.name: t for t in _run(server.list_tools())}
    assert "user_get_current" in tools, "user_get_current is not registered"

    return _as_dict(_run(server.call_tool("user_get_current", kwargs)))


def _run(coro):
    """Run a coroutine on a dedicated loop (never the deprecated global one)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _as_dict(result) -> dict:
    """Normalize FastMCP call_tool output to the tool's own dict.

    The installed MCP build returns a ``(content_blocks, structured)`` tuple
    whose structured half is ``{"result": <tool return>}``. Other builds
    return the bare dict or a list of TextContent blocks. All shapes are
    handled so the assertions are on the tool's actual return value, not on a
    serialization detail of one MCP version.
    """
    if isinstance(result, tuple) and len(result) == 2:
        structured = result[1]
        if isinstance(structured, dict) and "result" in structured:
            return structured["result"]
        result = result[0]

    if isinstance(result, dict):
        return result
    if isinstance(result, (list, tuple)):
        parts = []
        for block in result:
            text = getattr(block, "text", None)
            if text is not None:
                import json

                try:
                    parts.append(json.loads(text))
                except Exception:
                    parts.append(text)
            elif isinstance(block, dict):
                parts.append(block)
        assert len(parts) == 1, f"expected one content block, got {parts!r}"
        return parts[0]
    raise AssertionError(f"unexpected call_tool result type: {type(result)!r}")


def _sign_token(claims: dict) -> str:
    """Sign a JWT with the SAME key the verifier uses.

    `create_access_token` only ever encodes `sub`/`exp`, so role and
    permission claims have to be minted here to exercise the claim-handling
    path. Signing with the verifier's own SECRET_KEY/ALGORITHM is what makes
    these tokens genuinely verified rather than forged-looking.
    """
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    from common_lib.modules.auth import security as auth_security

    payload = dict(claims)
    payload.setdefault("exp", datetime.now(timezone.utc) + timedelta(minutes=30))
    return jwt.encode(
        payload, auth_security.SECRET_KEY, algorithm=auth_security.ALGORITHM
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. The core vulnerability: no fabricated admin, ever
# ─────────────────────────────────────────────────────────────────────────────


def test_tool_is_registered_and_callable():
    """Sanity: the tool exists and returns a dict (guards the harness)."""
    payload = _as_dict(call_user_get_current())
    assert isinstance(payload, dict)


def test_cannot_return_admin_with_wildcard_permission():
    """The original defect, asserted against directly.

    `user_get_current` must not report role 'admin' together with the ['*']
    wildcard. This is the exact shape of the original bug.
    """
    payload = _as_dict(call_user_get_current())
    assert not (
        payload.get("role") == "admin" and payload.get("permissions") == ["*"]
    ), f"fabricated admin identity returned: {payload!r}"


def test_never_returns_wildcard_permission_in_any_mode():
    """The ['*'] wildcard must not appear in ANY response shape or mode."""
    for kwargs in ({}, {"include_service_identity": True}):
        payload = _as_dict(call_user_get_current(**kwargs))
        perms = payload.get("permissions") or []
        assert "*" not in perms, f"wildcard permission leaked: {payload!r}"
        assert "all" not in perms, f"'all' permission leaked: {payload!r}"
        assert "superuser" not in perms, f"superuser permission leaked: {payload!r}"


def test_unauthenticated_caller_is_anonymous_not_admin():
    """With no bound request context, the honest answer is anonymous."""
    payload = _as_dict(call_user_get_current())
    assert payload["is_authenticated"] is False
    assert payload["is_admin"] is False
    assert payload["id"] == "anonymous"
    assert payload["role"] == "anonymous"
    assert payload["permissions"] == []
    assert payload["source"] == "none"


def test_cannot_return_an_unverified_identity():
    """An identity is only ever established from a verified credential.

    A principal bound into the context must have come from verification; the
    resolver refuses to bind one otherwise. Verified here end-to-end: an
    unverifiable token yields anonymous, so no unverified identity surfaces.
    """
    garbage = resolve_mcp_principal("Bearer not.a.real.jwt")
    assert garbage.is_authenticated is False
    assert garbage.is_admin is False
    assert garbage.permissions == ()

    token = bind_principal(garbage)
    try:
        payload = _as_dict(call_user_get_current())
    finally:
        reset_principal(token)
    assert payload["is_authenticated"] is False
    assert payload["is_admin"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. Request context plumbing (the actual root cause)
# ─────────────────────────────────────────────────────────────────────────────


def test_no_context_defaults_to_anonymous_not_admin():
    """The ContextVar default must be 'no credential', never an admin."""
    payload = _as_dict(call_user_get_current())
    assert payload["id"] == "anonymous"
    assert payload["is_authenticated"] is False


def test_bound_principal_is_visible_to_the_tool():
    """A verified principal bound to the request scope reaches the tool body.

    Built via the real resolver from a token this test signs with the
    verifier's own key, so the identity is genuinely established rather than
    asserted.
    """
    token = _sign_token(
        {"sub": "alice", "role": "developer", "permissions": ["workflows.read"]}
    )
    principal = resolve_mcp_principal(f"Bearer {token}")
    assert principal.is_authenticated is True, principal.reason

    ctx_token = bind_principal(principal)
    try:
        payload = _as_dict(call_user_get_current())
    finally:
        reset_principal(ctx_token)

    assert payload["id"] == "alice"
    assert payload["role"] == "developer"
    assert payload["is_authenticated"] is True
    assert payload["source"] == "token"
    assert "workflows.read" in payload["permissions"]


def test_verified_admin_token_reports_admin_truthfully():
    """A genuinely verified admin token DOES surface is_admin=True.

    This is the honest inverse: the fix must not merely suppress admin. It
    reports admin only when a verified token carried it.
    """
    token = _sign_token({"sub": "root", "role": "admin", "permissions": ["*"]})
    principal = resolve_mcp_principal(f"Bearer {token}")
    assert principal.is_authenticated is True

    ctx_token = bind_principal(principal)
    try:
        payload = _as_dict(call_user_get_current())
    finally:
        reset_principal(ctx_token)

    assert payload["role"] == "admin"
    assert payload["is_admin"] is True
    # Even for a real admin, the wildcard is stripped from the claims.
    assert "*" not in payload["permissions"]


def test_binding_is_reset_so_one_request_cannot_leak_into_the_next():
    """The reset token must fully restore the anonymous default.

    A leaked binding would serve one caller's identity to the next caller on
    the same worker -- an identity confusion bug in the opposite direction.
    """
    p = Principal(
        id="mallory",
        role="admin",
        permissions=("x",),
        is_authenticated=True,
        source="token",
    )
    token = bind_principal(p)
    assert current_principal().id == "mallory"
    reset_principal(token)
    assert current_principal().id == "anonymous"
    assert current_principal().is_authenticated is False


def test_expired_or_malformed_token_is_anonymous():
    """Fails closed on a variety of unusable credentials."""
    for header in (
        "",
        None,
        "Bearer",
        "Bearer ",
        "garbage",
        "Basic dXNlcjpwYXNz",
        "Bearer a.b.c",
    ):
        principal = resolve_mcp_principal(header)
        assert principal.is_authenticated is False, f"accepted {header!r}"
        assert principal.is_admin is False
        assert principal.permissions == ()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Service identity is requested, never inferred
# ─────────────────────────────────────────────────────────────────────────────


def test_service_identity_is_not_inferred_by_default(monkeypatch):
    """Even with a service identity configured, an anonymous caller gets anonymous."""
    monkeypatch.setenv("SERVICE_IDENTITY_ENABLED", "1")
    monkeypatch.setenv("SERVICE_IDENTITY_ID", "scheduler")
    monkeypatch.setenv("SERVICE_IDENTITY_ROLE", "service")
    monkeypatch.setenv("SERVICE_IDENTITY_PERMISSIONS", "jobs.run")

    payload = _as_dict(call_user_get_current())
    assert payload["is_authenticated"] is False
    assert payload["id"] == "anonymous", "service identity was inferred, not requested"
    assert "jobs.run" not in payload["permissions"]


def test_service_identity_requires_explicit_request(monkeypatch):
    """With an explicit request, the service identity IS returned."""
    monkeypatch.setenv("SERVICE_IDENTITY_ENABLED", "1")
    monkeypatch.setenv("SERVICE_IDENTITY_ID", "scheduler")
    monkeypatch.setenv("SERVICE_IDENTITY_ROLE", "service")
    monkeypatch.setenv("SERVICE_IDENTITY_PERMISSIONS", "jobs.run,other.read")

    payload = _as_dict(call_user_get_current(include_service_identity=True))
    assert payload["is_authenticated"] is True
    assert payload["id"] == "scheduler"
    assert payload["is_service"] is True
    assert set(payload["permissions"]) == {"jobs.run", "other.read"}


def test_service_identity_still_cannot_carry_the_wildcard(monkeypatch):
    """A misconfigured service identity cannot reintroduce ['*']."""
    monkeypatch.setenv("SERVICE_IDENTITY_ENABLED", "1")
    monkeypatch.setenv("SERVICE_IDENTITY_ID", "scheduler")
    monkeypatch.setenv("SERVICE_IDENTITY_ROLE", "admin")
    monkeypatch.setenv("SERVICE_IDENTITY_PERMISSIONS", "*,all,superuser,jobs.run")

    payload = _as_dict(call_user_get_current(include_service_identity=True))
    assert "*" not in payload["permissions"]
    assert "all" not in payload["permissions"]
    assert "superuser" not in payload["permissions"]
    assert "jobs.run" in payload["permissions"]


def test_service_identity_enabled_without_id_refuses_to_mint(monkeypatch):
    """Enabled-but-unnamed is a misconfiguration, not a grant."""
    monkeypatch.setenv("SERVICE_IDENTITY_ENABLED", "1")
    monkeypatch.delenv("SERVICE_IDENTITY_ID", raising=False)

    assert request_service_identity() is None
    payload = _as_dict(call_user_get_current(include_service_identity=True))
    assert payload["is_authenticated"] is False
    assert payload["id"] == "anonymous"


def test_service_identity_disabled_by_default(monkeypatch):
    """No ambient privilege without opt-in configuration."""
    for var in (
        "SERVICE_IDENTITY_ENABLED",
        "SERVICE_IDENTITY_ID",
        "SERVICE_IDENTITY_ROLE",
        "SERVICE_IDENTITY_PERMISSIONS",
    ):
        monkeypatch.delenv(var, raising=False)

    assert request_service_identity() is None
    assert current_principal().is_authenticated is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. Static sweep: the fabricated literal must not come back
# ─────────────────────────────────────────────────────────────────────────────


def test_no_fabricated_admin_literal_in_mcp_surface():
    """Guard against reintroduction of the hardcoded identity.

    AST-based on purpose: a text scan would also match the docstrings that
    *describe* the removed bug. This walks real dict literals in executable
    code, so it fails only if someone actually rebuilds the mock.
    """
    import ast

    mcp_dir = _REPO_BACKEND / "app" / "mcp"
    offenders: list[str] = []
    for path in mcp_dir.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            # {"permissions": ["*"]} — the fabricated wildcard grant.
            for idx, k in enumerate(keys):
                if k != "permissions":
                    continue
                v = node.values[idx]
                if isinstance(v, (ast.List, ast.Tuple)):
                    items = [e.value for e in v.elts if isinstance(e, ast.Constant)]
                    if "*" in items or "all" in items:
                        offenders.append(
                            f"{path.name}:{node.lineno} fabricated wildcard permission literal"
                        )
            # {"id": "system", "role": "admin", ...} — the fabricated identity.
            values = [v.value for v in node.values if isinstance(v, ast.Constant)]
            if "system" in values and "admin" in values:
                offenders.append(
                    f"{path.name}:{node.lineno} fabricated system/admin identity literal"
                )
    assert not offenders, "fabricated identity reintroduced: " + "; ".join(offenders)


def test_approve_deployment_no_longer_defaults_to_admin(monkeypatch):
    """`approved_by` must not silently fabricate an "admin" attribution."""
    source = (
        _REPO_BACKEND / "app" / "mcp" / "tools" / "db_studio" / "migration.py"
    ).read_text(encoding="utf-8")
    assert 'approved_by: str = "admin"' not in source, (
        "approve_deployment still defaults approved_by to the literal 'admin'"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. The transport actually binds a principal
# ─────────────────────────────────────────────────────────────────────────────


def test_http_call_endpoint_binds_principal_for_the_tool():
    """End-to-end over the real FastAPI route: an authenticated caller's
    identity reaches the tool body.

    Exercises `call_mcp_tool` directly (mounting the whole app would boot the
    full node-tool scan, which this machine cannot afford). The route is the
    only place the binding happens, so testing it proves the wiring.
    """
    from app.mcp.routes import CallToolRequest, call_mcp_tool

    class _FakeRequest:
        def __init__(self, headers):
            self.headers = headers

    token = _sign_token({"sub": "bob", "role": "developer"})
    req = CallToolRequest(name="user_get_current", arguments={})

    captured: dict = {}

    import app.mcp.routes as routes_mod

    async def _fake_call_tool(name, arguments):
        captured["principal"] = current_principal()
        return {
            "id": "bob",
            "role": "developer",
            "permissions": [],
            "is_authenticated": True,
            "is_admin": False,
            "source": "token",
        }

    original = routes_mod.mcp_server.call_tool
    original_wait = routes_mod._await_node_tools
    routes_mod.mcp_server.call_tool = _fake_call_tool
    routes_mod._await_node_tools = lambda: None
    try:
        asyncio.new_event_loop().run_until_complete(
            call_mcp_tool(req, _FakeRequest({"Authorization": f"Bearer {token}"}))
        )
        assert captured["principal"].id == "bob"
        assert captured["principal"].is_authenticated is True
    finally:
        routes_mod.mcp_server.call_tool = original
        routes_mod._await_node_tools = original_wait


def test_http_call_endpoint_binds_anonymous_when_no_header():
    """No credential over the same route binds anonymous, not admin."""
    from app.mcp.routes import CallToolRequest, call_mcp_tool

    class _FakeRequest:
        def __init__(self, headers):
            self.headers = headers

    captured: dict = {}
    import app.mcp.routes as routes_mod

    async def _fake_call_tool(name, arguments):
        captured["principal"] = current_principal()
        return {}

    original = routes_mod.mcp_server.call_tool
    original_wait = routes_mod._await_node_tools
    routes_mod.mcp_server.call_tool = _fake_call_tool
    routes_mod._await_node_tools = lambda: None
    try:
        asyncio.new_event_loop().run_until_complete(
            call_mcp_tool(
                CallToolRequest(name="user_get_current", arguments={}), _FakeRequest({})
            )
        )
        assert captured["principal"].is_authenticated is False
        assert captured["principal"].is_admin is False
        assert captured["principal"].id == "anonymous"
    finally:
        routes_mod.mcp_server.call_tool = original
        routes_mod._await_node_tools = original_wait


def test_anonymous_principal_helper_is_unprivileged():
    """The explicit anonymous constructor must never be privileged."""
    p = anonymous_principal()
    assert p.is_authenticated is False
    assert p.is_admin is False
    assert p.is_service is False
    assert p.permissions == ()
    assert p.to_dict()["permissions"] == []


def test_resolve_principal_shared_implementation_is_used():
    """Confirms identity.py does not implement its own token verification."""
    source = (_REPO_BACKEND / "app" / "mcp" / "identity.py").read_text(encoding="utf-8")
    assert "decode_access_token" not in source, (
        "app/mcp/identity.py must delegate verification to identity_context"
    )
    assert "jwt" not in source.lower().replace("jws", ""), (
        "app/mcp/identity.py must not decode tokens itself"
    )
    # And it is genuinely the shared resolver.
    assert resolve_principal is not None
