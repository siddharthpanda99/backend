"""Re-export auth dependencies from the real implementation.

All consumers should import from this module for backward compatibility.
The actual implementations live in authz.py.
"""

from app.modules.auth.dependencies.authz import (  # noqa: F401
    get_current_active_user,
    get_current_identity,
    get_tenant_id,
    get_authz_checker,
    require_permission,
    require_tenant,
    RoleChecker,
)
