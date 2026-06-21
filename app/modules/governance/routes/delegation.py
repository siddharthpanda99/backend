from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import GovernanceDelegation

router = APIRouter(prefix="/delegations", tags=["Governance - Delegation"])


class DelegationCreate(BaseModel):
    delegation_id: str
    delegating_agent: str
    delegatee_agent: str
    task_id: str = ""
    permissions_granted: list[str] = []
    constraints: dict = {}
    expires_at: str = ""
    max_invocations: int = 0


def _delegation_to_dict(d: GovernanceDelegation) -> dict:
    return {
        "delegation_id": d.id,
        "delegating_agent": d.delegator_id,
        "delegatee_agent": d.delegate_id,
        "task_id": d.role_name,
        "permissions_granted": [d.role_name],
        "constraints": {},
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "expires_at": d.expires_at.isoformat() if d.expires_at else None,
        "max_invocations": 0,
        "invocation_count": 0,
        "revoked": not d.is_active,
    }


@router.get("")
def list_delegations(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceDelegation)).all()
    return [_delegation_to_dict(d) for d in items]


@router.post("")
def create_delegation(body: DelegationCreate, session: Session = Depends(get_session)):
    delegation = GovernanceDelegation(
        delegator_id=body.delegating_agent,
        delegate_id=body.delegatee_agent,
        role_name=body.task_id or "default",
        is_active=True,
    )
    if body.expires_at:
        try:
            delegation.expires_at = datetime.fromisoformat(body.expires_at)
        except (ValueError, TypeError):
            pass
    session.add(delegation)
    session.commit()
    session.refresh(delegation)
    return _delegation_to_dict(delegation)


@router.post("/{delegation_id}/revoke")
def revoke_delegation(delegation_id: int, session: Session = Depends(get_session)):
    delegation = session.exec(
        select(GovernanceDelegation).where(GovernanceDelegation.id == delegation_id)
    ).first()
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    delegation.is_active = False
    session.add(delegation)
    session.commit()
    return {"success": True}


@router.get("/check")
def check_delegation(
    agent_id: str, task_id: str, session: Session = Depends(get_session)
):
    items = session.exec(
        select(GovernanceDelegation).where(
            GovernanceDelegation.delegate_id == agent_id,
            GovernanceDelegation.role_name == task_id,
            GovernanceDelegation.is_active == True,
        )
    ).all()
    return {"active": len(items) > 0, "delegations": len(items)}
