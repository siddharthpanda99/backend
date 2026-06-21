from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import GovernanceRoleAssignment

router = APIRouter(prefix="/role-assignments", tags=["Governance - Role Assignments"])


class AssignmentCreate(BaseModel):
    id: str = ""
    principal_type: str = "agent"
    principal_id: str
    role: str
    granted_by: str = ""
    granted_at: str = ""
    expires_at: str = ""
    scope_override: dict = {}
    justification: str = ""
    status: str = "active"


def _assignment_to_dict(a: GovernanceRoleAssignment) -> dict:
    return {
        "id": a.id,
        "principal_type": a.subject_type,
        "principal_id": a.subject_id,
        "role": a.role_name,
        "granted_by": a.assigned_by or "",
        "granted_at": a.created_at.isoformat() if a.created_at else None,
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        "scope_override": {},
        "justification": "",
        "status": "active",
    }


@router.get("")
def list_assignments(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceRoleAssignment)).all()
    return [_assignment_to_dict(a) for a in items]


@router.post("")
def create_assignment(body: AssignmentCreate, session: Session = Depends(get_session)):
    assignment = GovernanceRoleAssignment(
        subject_id=body.principal_id,
        subject_type=body.principal_type,
        role_name=body.role,
        assigned_by=body.granted_by,
    )
    if body.expires_at:
        try:
            assignment.expires_at = datetime.fromisoformat(body.expires_at)
        except (ValueError, TypeError):
            pass
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return _assignment_to_dict(assignment)


@router.delete("/{assignment_id}")
def revoke_assignment(assignment_id: int, session: Session = Depends(get_session)):
    assignment = session.exec(
        select(GovernanceRoleAssignment).where(
            GovernanceRoleAssignment.id == assignment_id
        )
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    session.delete(assignment)
    session.commit()
    return {"success": True}


@router.get("/agent/{agent_id}")
def get_agent_roles(agent_id: str, session: Session = Depends(get_session)):
    assignments = session.exec(
        select(GovernanceRoleAssignment).where(
            GovernanceRoleAssignment.subject_id == agent_id
        )
    ).all()
    roles = list({a.role_name for a in assignments})
    return {
        "agent_id": agent_id,
        "roles": roles,
        "permissions": [],
    }
