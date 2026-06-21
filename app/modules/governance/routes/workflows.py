from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import (
    GovernanceWorkflowDefinition,
    GovernanceWorkflowLineage,
)
import json

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


def _wf_to_dict(w: GovernanceWorkflowDefinition) -> dict:
    return {
        "workflow_id": w.workflow_id,
        "name": w.name,
        "version": w.version,
        "owner": w.owner,
        "department": w.department,
        "risk_level": w.risk_level,
        "status": w.status,
        "steps": json.loads(w.steps) if w.steps else [],
        "rollback_policy": json.loads(w.rollback_policy) if w.rollback_policy else {},
    }


def _lineage_to_dict(l: GovernanceWorkflowLineage) -> dict:
    return {
        "workflow_execution_id": l.workflow_execution_id,
        "workflow_id": l.workflow_id,
        "version": l.version,
        "initiated_by": l.initiated_by,
        "started_at": l.started_at,
        "steps": json.loads(l.steps) if l.steps else [],
        "status": l.status,
    }


@router.get("")
def list_workflows(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceWorkflowDefinition)).all()
    return [_wf_to_dict(w) for w in items]


@router.post("")
def register_workflow(body: WorkflowCreate, session: Session = Depends(get_session)):
    existing = session.exec(
        select(GovernanceWorkflowDefinition).where(
            GovernanceWorkflowDefinition.workflow_id == body.workflow_id
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Workflow already exists")
    wf = GovernanceWorkflowDefinition(
        workflow_id=body.workflow_id,
        name=body.name,
        version=body.version,
        owner=body.owner,
        department=body.department,
        risk_level=body.risk_level,
        status=body.status,
        steps=json.dumps(body.steps),
        rollback_policy=json.dumps(body.rollback_policy),
    )
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return _wf_to_dict(wf)


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, session: Session = Depends(get_session)):
    wf = session.exec(
        select(GovernanceWorkflowDefinition).where(
            GovernanceWorkflowDefinition.workflow_id == workflow_id
        )
    ).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _wf_to_dict(wf)


@router.post("/{workflow_id}/validate")
def validate_workflow(workflow_id: str, session: Session = Depends(get_session)):
    wf = session.exec(
        select(GovernanceWorkflowDefinition).where(
            GovernanceWorkflowDefinition.workflow_id == workflow_id
        )
    ).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    steps = json.loads(wf.steps) if wf.steps else []
    return {
        "valid": len(steps) > 0,
        "step_count": len(steps),
        "status": wf.status,
    }


@router.post("/{workflow_id}/transition")
def validate_transition(
    workflow_id: str,
    body: ValidateTransitionRequest,
    session: Session = Depends(get_session),
):
    wf = session.exec(
        select(GovernanceWorkflowDefinition).where(
            GovernanceWorkflowDefinition.workflow_id == workflow_id
        )
    ).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    steps = json.loads(wf.steps) if wf.steps else []
    step_ids = [s.get("id", "") for s in steps]
    from_valid = body.from_step in step_ids
    to_valid = body.to_step in step_ids
    return {
        "valid": from_valid and to_valid,
        "from_step_valid": from_valid,
        "to_step_valid": to_valid,
    }


@router.post("/lineage")
def start_lineage(body: StartLineageRequest, session: Session = Depends(get_session)):
    existing = session.exec(
        select(GovernanceWorkflowLineage).where(
            GovernanceWorkflowLineage.workflow_execution_id
            == body.workflow_execution_id
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Lineage already exists")
    lineage = GovernanceWorkflowLineage(
        workflow_execution_id=body.workflow_execution_id,
        workflow_id=body.workflow_id,
        version=body.version,
        initiated_by=body.initiated_by,
        started_at=body.started_at or datetime.utcnow().isoformat(),
        steps="[]",
        status="running",
    )
    session.add(lineage)
    session.commit()
    session.refresh(lineage)
    return _lineage_to_dict(lineage)


@router.post("/lineage/step")
def record_step(body: RecordStepRequest, session: Session = Depends(get_session)):
    lineage = session.exec(
        select(GovernanceWorkflowLineage).where(
            GovernanceWorkflowLineage.workflow_execution_id == body.execution_id
        )
    ).first()
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    steps = json.loads(lineage.steps) if lineage.steps else []
    steps.append(body.step)
    lineage.steps = json.dumps(steps)
    session.add(lineage)
    session.commit()
    return {"success": True}


@router.post("/lineage/{execution_id}/complete")
def complete_lineage(execution_id: str, session: Session = Depends(get_session)):
    lineage = session.exec(
        select(GovernanceWorkflowLineage).where(
            GovernanceWorkflowLineage.workflow_execution_id == execution_id
        )
    ).first()
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    lineage.status = "completed"
    session.add(lineage)
    session.commit()
    return {"success": True}


@router.get("/lineage/{execution_id}")
def get_lineage(execution_id: str, session: Session = Depends(get_session)):
    lineage = session.exec(
        select(GovernanceWorkflowLineage).where(
            GovernanceWorkflowLineage.workflow_execution_id == execution_id
        )
    ).first()
    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found")
    return _lineage_to_dict(lineage)
