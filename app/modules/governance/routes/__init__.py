from fastapi import APIRouter
from app.modules.governance.routes.identity import router as identity_router
from app.modules.governance.routes.auth import router as auth_router
from app.modules.governance.routes.rbac import router as rbac_router
from app.modules.governance.routes.policies import router as policies_router
from app.modules.governance.routes.hitl import router as hitl_router
from app.modules.governance.routes.trust import router as trust_router
from app.modules.governance.routes.audit import router as audit_router
from app.modules.governance.routes.compliance import router as compliance_router
from app.modules.governance.routes.incidents import router as incidents_router
from app.modules.governance.routes.engine import router as engine_router
from app.modules.governance.routes.tools import router as tools_router
from app.modules.governance.routes.workflows import router as workflows_router
from app.modules.governance.routes.memory_gov import router as memory_gov_router
from app.modules.governance.routes.integration import router as integration_router
from app.modules.governance.routes.delegation import router as delegation_router
from app.modules.governance.routes.role_assignments import (
    router as role_assignments_router,
)
from app.modules.governance.routes.approval_policies import (
    router as approval_policies_router,
)

router = APIRouter()
router.include_router(identity_router)
router.include_router(auth_router)
router.include_router(rbac_router)
router.include_router(policies_router)
router.include_router(hitl_router)
router.include_router(trust_router)
router.include_router(audit_router)
router.include_router(compliance_router)
router.include_router(incidents_router)
router.include_router(engine_router)
router.include_router(tools_router)
router.include_router(workflows_router)
router.include_router(memory_gov_router)
router.include_router(integration_router)
router.include_router(delegation_router)
router.include_router(role_assignments_router)
router.include_router(approval_policies_router)

__all__ = ["router"]
