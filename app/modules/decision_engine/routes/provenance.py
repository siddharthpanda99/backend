"""Provenance Routes."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.schemas import (
    ProvenanceRead,
    ProvenanceList,
    PlanProvenanceRead,
)

from common_lib.modules.decision_engine.services import DecisionRegistryService

from app.modules.decision_engine.routes._errors import http_error
from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter(prefix="/provenance", tags=["Provenance"])
_service = DecisionRegistryService()


@router.get("/decision/{decision_id}", response_model=ProvenanceRead)
async def get_decision_provenance(decision_id: str):
    """Get provenance for a single decision."""
    _require_fabric()

    try:
        prov = _service.get_decision_provenance(decision_id)
        if not prov:
            raise HTTPException(status_code=404, detail="Provenance not found")
        return ProvenanceRead.model_validate(prov)
    except HTTPException:
        raise
    except Exception as e:
        raise http_error(e, prefix="Get provenance failed")


@router.get("/plan/{plan_id}", response_model=PlanProvenanceRead)
async def get_plan_provenance(plan_id: str):
    """Get provenance for a full plan."""
    _require_fabric()

    try:
        prov = _service.get_plan_provenance(plan_id)
        if not prov:
            raise HTTPException(status_code=404, detail="Plan provenance not found")
        return PlanProvenanceRead.model_validate(prov)
    except HTTPException:
        raise
    except Exception as e:
        raise http_error(e, prefix="Get plan provenance failed")


@router.get("/plan/{plan_id}/decisions", response_model=ProvenanceList)
async def list_plan_decisions(plan_id: str):
    """List all decision provenances for a plan."""
    _require_fabric()

    try:
        provs = _service.list_plan_decisions(plan_id)
        return ProvenanceList(
            items=[ProvenanceRead.model_validate(p) for p in provs],
            total=len(provs),
        )
    except Exception as e:
        raise http_error(e, prefix="List decisions failed")
