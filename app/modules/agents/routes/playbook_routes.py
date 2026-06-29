"""Playbook routes — CRUD and execution for YAML-defined workflows."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.modules.common.types.index import APIResponse
from common_lib.modules.agents.services.playbook_service import PlaybookService
from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)

router = APIRouter()


class PlaybookRead(BaseModel):
    id: str
    name: str
    description: str | None
    parameters_json: str | None
    created_at: str | None
    updated_at: str | None


class PlaybookCreateRequest(BaseModel):
    name: str
    yaml_content: str
    description: str | None = None


class PlaybookRunRead(BaseModel):
    id: str
    playbook_id: str
    session_id: str | None
    status: str
    current_step_index: int
    state_variables: str | None
    error_message: str | None
    created_at: str | None
    updated_at: str | None


class PlaybookStepRunRead(BaseModel):
    id: str
    run_id: str
    step_index: int
    step_name: str
    status: str
    output: str | None
    gate_type: str | None
    gate_response: str | None
    error_message: str | None


class StartRunRequest(BaseModel):
    playbook_id: str
    session_id: str | None = None
    parameters: dict | None = None


class GateResponseRequest(BaseModel):
    step_index: int
    response: str = ""
    approved: bool = True


def _get_db():
    from common_lib.modules.data_storage.database.connection import get_session

    yield from get_session()


@router.get("/", response_model=APIResponse[List[PlaybookRead]])
def list_playbooks(
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    playbooks = svc.list_playbooks(db)
    return APIResponse(
        data=[
            PlaybookRead(
                id=p.id,
                name=p.name,
                description=p.description,
                parameters_json=p.parameters_json,
                created_at=p.created_at.isoformat() if p.created_at else None,
                updated_at=p.updated_at.isoformat() if p.updated_at else None,
            )
            for p in playbooks
        ],
        message="Retrieved playbooks",
    )


@router.post("/", response_model=APIResponse[PlaybookRead])
def create_playbook(
    req: PlaybookCreateRequest,
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    try:
        playbook = svc.create_playbook(
            db,
            name=req.name,
            yaml_content=req.yaml_content,
            description=req.description,
        )
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return APIResponse(
        data=PlaybookRead(
            id=playbook.id,
            name=playbook.name,
            description=playbook.description,
            parameters_json=playbook.parameters_json,
            created_at=playbook.created_at.isoformat() if playbook.created_at else None,
            updated_at=playbook.updated_at.isoformat() if playbook.updated_at else None,
        ),
        message="Playbook created",
    )


@router.get("/{playbook_id}", response_model=APIResponse[PlaybookRead])
def get_playbook(
    playbook_id: str,
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    pb = svc.get_playbook(db, playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return APIResponse(
        data=PlaybookRead(
            id=pb.id,
            name=pb.name,
            description=pb.description,
            parameters_json=pb.parameters_json,
            created_at=pb.created_at.isoformat() if pb.created_at else None,
            updated_at=pb.updated_at.isoformat() if pb.updated_at else None,
        ),
        message="Retrieved playbook",
    )


@router.delete("/{playbook_id}")
def delete_playbook(
    playbook_id: str,
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    deleted = svc.delete_playbook(db, playbook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return APIResponse(data={"deleted": True}, message="Playbook deleted")


# --- Run endpoints ---


@router.post("/runs", response_model=APIResponse[PlaybookRunRead])
def start_run(
    req: StartRunRequest,
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    try:
        run = svc.start_run(
            db,
            playbook_id=req.playbook_id,
            session_id=req.session_id,
            parameters=req.parameters,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return APIResponse(
        data=PlaybookRunRead(
            id=run.id,
            playbook_id=run.playbook_id,
            session_id=run.session_id,
            status=run.status,
            current_step_index=run.current_step_index,
            state_variables=run.state_variables,
            error_message=run.error_message,
            created_at=run.created_at.isoformat() if run.created_at else None,
            updated_at=run.updated_at.isoformat() if run.updated_at else None,
        ),
        message="Run started",
    )


@router.get("/runs/{run_id}", response_model=APIResponse[PlaybookRunRead])
def get_run(
    run_id: str,
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    run = svc.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return APIResponse(
        data=PlaybookRunRead(
            id=run.id,
            playbook_id=run.playbook_id,
            session_id=run.session_id,
            status=run.status,
            current_step_index=run.current_step_index,
            state_variables=run.state_variables,
            error_message=run.error_message,
            created_at=run.created_at.isoformat() if run.created_at else None,
            updated_at=run.updated_at.isoformat() if run.updated_at else None,
        ),
        message="Retrieved run",
    )


@router.get(
    "/runs/{run_id}/steps", response_model=APIResponse[List[PlaybookStepRunRead]]
)
def get_run_steps(
    run_id: str,
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    steps = svc.get_step_runs(db, run_id)
    return APIResponse(
        data=[
            PlaybookStepRunRead(
                id=s.id,
                run_id=s.run_id,
                step_index=s.step_index,
                step_name=s.step_name,
                status=s.status,
                output=s.output,
                gate_type=s.gate_type,
                gate_response=s.gate_response,
                error_message=s.error_message,
            )
            for s in steps
        ],
        message="Retrieved step runs",
    )


@router.post("/runs/{run_id}/advance")
def advance_run(
    run_id: str,
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    result = svc.advance_run(db, run_id)
    return APIResponse(data=result, message="Run advanced")


@router.post("/runs/{run_id}/gate")
def handle_gate(
    run_id: str,
    req: GateResponseRequest,
    db: Session = Depends(get_db_session),
):
    svc = PlaybookService()
    result = svc.handle_gate(
        db,
        run_id=run_id,
        step_index=req.step_index,
        response=req.response,
        approved=req.approved,
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Run not found")
    return APIResponse(data=result, message="Gate response recorded")
