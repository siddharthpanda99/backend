import logging
from dataclasses import replace
from typing import Any, Dict, List

from app.mcp.fastmcp_compat import FastMCP
from app.mcp.identity import current_principal, request_service_identity
from app.mcp.mcp_dependencies import resolve_user_service

logger = logging.getLogger("mcp.tools.users")


def register_user_tools(mcp: FastMCP):
    """Register tools for user management and platform identity context."""

    @mcp.tool()
    async def list_users(active_only: bool = True) -> List[Dict[str, Any]]:
        """List platform users and their current status."""
        service = resolve_user_service()
        users = await service.get_users(active_only=active_only)
        return [u.model_dump(exclude={"hashed_password"}) for u in users]

    @mcp.tool()
    async def get_user_profile(user_id: str) -> Dict[str, Any]:
        """Retrieve the full profile of a user by their ID."""
        service = resolve_user_service()
        user = await service.get_user(user_id)
        if not user:
            return {"status": "error", "message": "User not found"}
        return user.model_dump(exclude={"hashed_password"})

    @mcp.tool()
    async def user_get_current(
        include_service_identity: bool = False,
    ) -> Dict[str, Any]:
        """Report WHO is calling, resolved from a verified credential.

        This previously returned a hardcoded
        ``{"id": "system", "role": "admin", "permissions": ["*"]}`` for every
        caller. That was a fabricated identity -- the platform asserting a
        privilege it had never established. It is gone.

        HOW TO READ THE RESULT: branch on ``is_authenticated``.

        * A caller that presented a verifiable bearer token over the
          authenticated HTTP transport (``POST /api/v1/mcp/tools/call``)
          gets its real ``id``, ``role`` and explicit ``permissions``.
        * A caller with no verified credential gets the **anonymous**
          principal: ``is_authenticated=False``, ``id``/``role`` of
          ``"anonymous"``, ``permissions: []``. This is the truthful answer
          for the SSE transport (``/mcp/transport``), which is mounted with
          ``app.mount`` and so never runs an auth dependency, and for the
          local stdio transport. It is a normal result, not an error.
        * ``is_admin`` is True only for an authenticated caller whose verified
          token carried an administrative role. It is never True merely
          because the tool was called.

        THIS TOOL CANNOT RETURN ``role="admin"`` WITH ``permissions=["*"]``.
        The wildcard is stripped from both token claims and service
        configuration in ``common_lib.modules.auth.identity_context``, so no
        input can reintroduce it.

        Set ``include_service_identity=True`` to explicitly REQUEST the
        process's configured service identity (used by internal jobs that
        genuinely have no user token). It is never inferred: with the default
        ``False``, an unauthenticated caller receives anonymous even if a
        service identity happens to be configured.
        """
        principal = current_principal()

        if include_service_identity and not principal.is_authenticated:
            service = request_service_identity()
            if service is not None:
                principal = replace(
                    service,
                    reason=(
                        "service identity explicitly requested by the caller "
                        "via include_service_identity=True"
                    ),
                )

        return principal.to_dict()
