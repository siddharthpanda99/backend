from app.modules.auth.dependencies.authz import (
    get_current_active_user,
    get_current_identity,
    get_authz_checker,
    get_tenant_id,
    require_permission,
    require_tenant,
    RoleChecker,
)

# Backward-compatible alias — offline_routes.py and universal_graph_routes.py
# import "get_current_user" which maps to get_current_active_user.
get_current_user = get_current_active_user

__all__ = [
    "get_current_active_user",
    "get_current_identity",
    "get_authz_checker",
    "get_tenant_id",
    "require_permission",
    "require_tenant",
    "RoleChecker",
    "get_current_user",
]
