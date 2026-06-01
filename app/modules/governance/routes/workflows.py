from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.workflows.service import (
    get_workflow_governance_service,
)
from common_lib.modules.governance.models.workflows import (
    WorkflowDefinition,
    WorkflowLineage,
)

router = APIRouter(prefix="/workflows", tags=["Governance - Workflows"])


class WorkflowCreate(BaseModel):
    workflow_id: str
    name: str = ""
    version: str = "1.0.0"
    owner: str = ""
    department: str = ""
    risk_level: str = "medium"
    status: str = "draft"
    steps: list[dict] = []
    rollback_policy: dict = {}


class ValidateTransitionRequest(BaseModel):
    from_step: str
    to_step: str
    agent_id: str = ""
    environment: str = "development"


class StartLineageRequest(BaseModel):
    workflow_execution_id: str
    workflow_id: str
    version: str = ""
    initiated_by: str = ""
    started_at: str = ""


class RecordStepRequest(BaseModel):
    execution_id: str
    step: dict


@router.get("")
def list_workflows():
    svc = get_workflow_governance_service()
    items = svc.list_workflows()
    result = []
    for w in items:
        d = {}
        for attr in [
            "workflow_id",
            "version",
            "name",
            "owner",
            "department",
            "risk_level",
            "status",
            "steps",
            "rollback_policy",
        ]:
            if hasattr(w, attr):
                d[attr] = getattr(w, attr)
        result.append(d)
    return result


@router.post("")
def register_workflow(body: WorkflowCreate):
    svc = get_workflow_governance_service()
    workflow = WorkflowDefinition(
        workflow_id=body.workflow_id,
        name=body.name,
        version=body.version,
        owner=body.owner,
        department=body.department,
        risk_level=body.risk_level,
        status=body.status,
        steps=body.steps,
        rollback_policy=body.rollback_policy,
    )
    result = svc.register(workflow)
    d = {}
    for attr in [
        "workflow_id",
        "version",
        "name",
        "owner",
        "department",
        "risk_level",
        "status",
        "steps",
        "rollback_policy",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str):
    svc = get_workflow_governance_service()
    result = svc.get(workflow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Workflow not found")
    d = {}
    for attr in [
        "workflow_id",
        "version",
        "name",
        "owner",
        "department",
        "risk_level",
        "status",
        "steps",
        "rollback_policy",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.post("/{workflow_id}/validate")
def validate_workflow(workflow_id: str):
    svc = get_workflow_governance_service()
    workflow = svc.get(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return svc.validate_workflow(workflow)


@router.post("/{workflow_id}/transition")
def validate_transition(workflow_id: str, body: ValidateTransitionRequest):
    svc = get_workflow_governance_service()
    return svc.validate_transition(
        workflow_id,
        body.from_step,
        body.to_step,
        body.agent_id,
        body.environment,
    )


@router.post("/lineage")
def start_lineage(body: StartLineageRequest):
    svc = get_workflow_governance_service()
    lineage = WorkflowLineage(
        workflow_execution_id=body.workflow_execution_id,
        workflow_id=body.workflow_id,
        version=body.version,
        initiated_by=body.initiated_by,
        started_at=body.started_at,
    )
    result = svc.start_lineage(lineage)
    return (
        result.to_dict()
        if hasattr(result, "to_dict")
        else {"execution_id": body.workflow_execution_id}
    )


@router.post("/lineage/step")
def record_step(body: RecordStepRequest):
    svc = get_workflow_governance_service()
    success = svc.record_step(body.execution_id, body.step)
    return {"success": success}


@router.post("/lineage/{execution_id}/complete")
def complete_lineage(execution_id: str):
    svc = get_workflow_governance_service()
    success = svc.complete_lineage(execution_id)
    return {"success": success}


@router.get("/lineage/{execution_id}")
def get_lineage(execution_id: str):
    svc = get_workflow_governance_service()
    result = svc.get_lineage(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Lineage not found")
    return (
        result.to_dict()
        if hasattr(result, "to_dict")
        else {"execution_id": execution_id}
    )
