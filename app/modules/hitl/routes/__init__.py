from fastapi import APIRouter
from app.modules.hitl.routes.router import router as hitl_policies_router
from app.modules.hitl.routes.decisions import router as decisions_router
from app.modules.hitl.routes.tasks import router as tasks_router
from app.modules.hitl.routes.assignments import router as assignments_router
from app.modules.hitl.routes.audit_logs import router as audit_logs_router

router = APIRouter()
router.include_router(hitl_policies_router)
router.include_router(decisions_router)
router.include_router(tasks_router)
router.include_router(assignments_router)
router.include_router(audit_logs_router)

__all__ = ["router"]
