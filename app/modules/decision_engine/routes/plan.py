"""Plan Routes - Build, approve, compile decision plans."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.schemas import (
    PlanCreateRequest,
    PlanRead,
    PlanApproveRequest,
    CompilePlanRequest,
    ContractRead,
)

from common_lib.modules.decision_engine.services import (
    DecisionEngineService,
    ApprovalService,
    DecisionRegistryService,
)

from app.modules.decision_engine.routes._errors import http_error
from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter(prefix="/plan", tags=["Plan"])
_decision_service = DecisionEngineService()
_approval_service = ApprovalService()
_registry_service = DecisionRegistryService()


@router.post("", response_model=PlanRead)
async def build_plan(request: PlanCreateRequest):
    """Build decision plan from decisions and goal."""
    _require_fabric()

    try:
        plan = _decision_service.build_plan(request)
        return PlanRead.model_validate(plan)
    except ValueError as e:
        raise http_error(e)
    except Exception as e:
        raise http_error(e, prefix="Plan build failed")


@router.get("/{plan_id}", response_model=PlanRead)
async def get_plan(plan_id: str):
    """Get plan by ID."""
    _require_fabric()

    try:
        plan = _decision_service.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        return PlanRead.model_validate(plan)
    except HTTPException:
        raise
    except Exception as e:
        raise http_error(e, prefix="Plan retrieval failed")


@router.post("/{plan_id}/approve", response_model=PlanRead)
async def approve_plan(plan_id: str, request: PlanApproveRequest):
    """Approve, reject, or modify a plan."""
    _require_fabric()

    try:
        plan = _approval_service.approve_request(plan_id, request)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        return PlanRead.model_validate(plan)
    except HTTPException:
        raise
    except Exception as e:
        raise http_error(e, prefix="Approval failed")


@router.post("/{plan_id}/compile", response_model=ContractRead)
async def compile_plan(plan_id: str, request: CompilePlanRequest):
    """Compile approved plan into execution contract."""
    _require_fabric()

    try:
        contract = _decision_service.compile_plan(plan_id=plan_id, request=request)
        return ContractRead.model_validate(contract)
    except ValueError as e:
        raise http_error(e)
    except Exception as e:
        raise http_error(e, prefix="Compilation failed")
