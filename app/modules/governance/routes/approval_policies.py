from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import (
    GovernanceApprovalPolicy,
    GovernanceTriggerDB,
    GovernanceHookDB,
    GovernanceInterceptorDB,
    GovernancePolicyTriggerLink,
    GovernancePolicyHookLink,
)
import json

router = APIRouter(prefix="/approval-policies", tags=["Governance - Approval Policies"])


class ApprovalPolicyCreate(BaseModel):
    approval_policy_id: str
    name: str = ""
    description: str = ""
    trigger_conditions: list[dict] = []
    approvers: dict = {}
    timeout: dict = {}
    escalation: dict = {}
    trigger_ids: list[str] = []
    hook_ids: list[str] = []


class ApprovalPolicyUpdate(BaseModel):
    name: str = ""
    description: str = ""
    trigger_conditions: list[dict] | None = None
    approvers: dict | None = None
    timeout: dict | None = None
    escalation: dict | None = None
    trigger_ids: list[str] | None = None
    hook_ids: list[str] | None = None


class InterceptorCreate(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    priority: int = 100
    policy_id: str = ""
    conditions: list[dict] = []
    action: str = "chain"
    enabled: bool = True
    triggers: list[dict] = []
    hooks: list[dict] = []
    approvers: dict = {}
    timeout: dict = {}
    escalation: dict = {}


class InterceptorUpdate(BaseModel):
    name: str = ""
    description: str = ""
    priority: int | None = None
    policy_id: str | None = None
    conditions: list[dict] | None = None
    action: str | None = None
    enabled: bool | None = None
    triggers: list[dict] | None = None
    hooks: list[dict] | None = None
    approvers: dict | None = None
    timeout: dict | None = None
    escalation: dict | None = None


def _policy_to_dict(p: GovernanceApprovalPolicy) -> dict:
    return {
        "approval_policy_id": p.approval_policy_id,
        "name": p.name,
        "description": p.description,
        "trigger_conditions": json.loads(p.trigger_conditions)
        if p.trigger_conditions
        else [],
        "approvers": json.loads(p.approvers) if p.approvers else {},
        "timeout": json.loads(p.timeout) if p.timeout else {},
        "escalation": json.loads(p.escalation) if p.escalation else {},
        "trigger_ids": json.loads(p.trigger_ids) if p.trigger_ids else [],
        "hook_ids": json.loads(p.hook_ids) if p.hook_ids else [],
    }


def _trigger_to_dict(t: GovernanceTriggerDB) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "conditions": json.loads(t.conditions) if t.conditions else {},
    }


def _hook_to_dict(h: GovernanceHookDB) -> dict:
    return {
        "id": h.id,
        "name": h.name,
        "description": h.description,
        "approvers": json.loads(h.approvers) if h.approvers else {},
        "timeout": json.loads(h.timeout) if h.timeout else {},
        "escalation": json.loads(h.escalation) if h.escalation else {},
    }


def _interceptor_to_dict(i: GovernanceInterceptorDB) -> dict:
    return {
        "id": i.id,
        "name": i.name,
        "description": i.description,
        "priority": i.priority,
        "policy_id": i.policy_id,
        "conditions": json.loads(i.conditions) if i.conditions else [],
        "action": i.action,
        "enabled": i.enabled,
        "triggers": json.loads(i.triggers_data) if i.triggers_data else [],
        "hooks": json.loads(i.hooks_data) if i.hooks_data else [],
        "approvers": json.loads(i.approvers) if i.approvers else {},
        "timeout": json.loads(i.timeout) if i.timeout else {},
        "escalation": json.loads(i.escalation) if i.escalation else {},
    }


@router.get("")
def list_approval_policies(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceApprovalPolicy)).all()
    return [_policy_to_dict(p) for p in items]


@router.post("")
def create_approval_policy(
    body: ApprovalPolicyCreate, session: Session = Depends(get_session)
):
    existing = session.exec(
        select(GovernanceApprovalPolicy).where(
            GovernanceApprovalPolicy.approval_policy_id == body.approval_policy_id
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Approval policy already exists")
    policy = GovernanceApprovalPolicy(
        approval_policy_id=body.approval_policy_id,
        name=body.name,
        description=body.description,
        trigger_conditions=json.dumps(body.trigger_conditions),
        approvers=json.dumps(body.approvers),
        timeout=json.dumps(body.timeout),
        escalation=json.dumps(body.escalation),
        trigger_ids=json.dumps(body.trigger_ids),
        hook_ids=json.dumps(body.hook_ids),
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return _policy_to_dict(policy)


# --- Triggers CRUD ---
@router.get("/triggers")
def list_triggers(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceTriggerDB)).all()
    return [_trigger_to_dict(t) for t in items]


@router.post("/triggers")
def create_trigger(body: dict, session: Session = Depends(get_session)):
    existing = session.exec(
        select(GovernanceTriggerDB).where(GovernanceTriggerDB.id == body.get("id"))
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Trigger already exists")
    trigger = GovernanceTriggerDB(
        id=body.get("id", ""),
        name=body.get("name", ""),
        description=body.get("description"),
        conditions=json.dumps(body.get("conditions", {})),
    )
    session.add(trigger)
    session.commit()
    session.refresh(trigger)
    return _trigger_to_dict(trigger)


@router.get("/triggers/{trigger_id}")
def get_trigger(trigger_id: str, session: Session = Depends(get_session)):
    t = session.exec(
        select(GovernanceTriggerDB).where(GovernanceTriggerDB.id == trigger_id)
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _trigger_to_dict(t)


@router.put("/triggers/{trigger_id}")
def update_trigger(
    trigger_id: str, body: dict, session: Session = Depends(get_session)
):
    t = session.exec(
        select(GovernanceTriggerDB).where(GovernanceTriggerDB.id == trigger_id)
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Trigger not found")
    if "name" in body:
        t.name = body["name"]
    if "description" in body:
        t.description = body["description"]
    if "conditions" in body:
        t.conditions = json.dumps(body["conditions"])
    t.updated_at = datetime.utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return _trigger_to_dict(t)


@router.delete("/triggers/{trigger_id}")
def delete_trigger(trigger_id: str, session: Session = Depends(get_session)):
    t = session.exec(
        select(GovernanceTriggerDB).where(GovernanceTriggerDB.id == trigger_id)
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Trigger not found")
    session.delete(t)
    session.commit()
    return {"status": "success"}


# --- Hooks CRUD ---
@router.get("/hooks")
def list_hooks(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceHookDB)).all()
    return [_hook_to_dict(h) for h in items]


@router.post("/hooks")
def create_hook(body: dict, session: Session = Depends(get_session)):
    existing = session.exec(
        select(GovernanceHookDB).where(GovernanceHookDB.id == body.get("id"))
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Hook already exists")
    hook = GovernanceHookDB(
        id=body.get("id", ""),
        name=body.get("name", ""),
        description=body.get("description"),
        approvers=json.dumps(body.get("approvers", {})),
        timeout=json.dumps(body.get("timeout", {})),
        escalation=json.dumps(body.get("escalation", {})),
    )
    session.add(hook)
    session.commit()
    session.refresh(hook)
    return _hook_to_dict(hook)


@router.get("/hooks/{hook_id}")
def get_hook(hook_id: str, session: Session = Depends(get_session)):
    h = session.exec(
        select(GovernanceHookDB).where(GovernanceHookDB.id == hook_id)
    ).first()
    if not h:
        raise HTTPException(status_code=404, detail="Hook not found")
    return _hook_to_dict(h)


@router.put("/hooks/{hook_id}")
def update_hook(hook_id: str, body: dict, session: Session = Depends(get_session)):
    h = session.exec(
        select(GovernanceHookDB).where(GovernanceHookDB.id == hook_id)
    ).first()
    if not h:
        raise HTTPException(status_code=404, detail="Hook not found")
    if "name" in body:
        h.name = body["name"]
    if "description" in body:
        h.description = body["description"]
    if "approvers" in body:
        h.approvers = json.dumps(body["approvers"])
    if "timeout" in body:
        h.timeout = json.dumps(body["timeout"])
    if "escalation" in body:
        h.escalation = json.dumps(body["escalation"])
    h.updated_at = datetime.utcnow()
    session.add(h)
    session.commit()
    session.refresh(h)
    return _hook_to_dict(h)


@router.delete("/hooks/{hook_id}")
def delete_hook(hook_id: str, session: Session = Depends(get_session)):
    h = session.exec(
        select(GovernanceHookDB).where(GovernanceHookDB.id == hook_id)
    ).first()
    if not h:
        raise HTTPException(status_code=404, detail="Hook not found")
    session.delete(h)
    session.commit()
    return {"status": "success"}


# --- Interceptors CRUD ---
@router.get("/interceptors")
def list_interceptors(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceInterceptorDB)).all()
    return [_interceptor_to_dict(i) for i in items]


@router.get("/interceptors/{interceptor_id}")
def get_interceptor(interceptor_id: str, session: Session = Depends(get_session)):
    i = session.exec(
        select(GovernanceInterceptorDB).where(
            GovernanceInterceptorDB.id == interceptor_id
        )
    ).first()
    if not i:
        raise HTTPException(status_code=404, detail="Interceptor not found")
    return _interceptor_to_dict(i)


@router.post("/interceptors")
def create_interceptor(
    body: InterceptorCreate, session: Session = Depends(get_session)
):
    existing = session.exec(
        select(GovernanceInterceptorDB).where(GovernanceInterceptorDB.id == body.id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Interceptor already exists")
    interceptor = GovernanceInterceptorDB(
        id=body.id,
        name=body.name,
        description=body.description,
        priority=body.priority,
        policy_id=body.policy_id,
        conditions=json.dumps(body.conditions),
        action=body.action,
        enabled=body.enabled,
        triggers_data=json.dumps(body.triggers),
        hooks_data=json.dumps(body.hooks),
        approvers=json.dumps(body.approvers),
        timeout=json.dumps(body.timeout),
        escalation=json.dumps(body.escalation),
    )
    session.add(interceptor)
    session.commit()
    session.refresh(interceptor)
    return _interceptor_to_dict(interceptor)


@router.put("/interceptors/{interceptor_id}")
def update_interceptor(
    interceptor_id: str,
    body: InterceptorUpdate,
    session: Session = Depends(get_session),
):
    i = session.exec(
        select(GovernanceInterceptorDB).where(
            GovernanceInterceptorDB.id == interceptor_id
        )
    ).first()
    if not i:
        raise HTTPException(status_code=404, detail="Interceptor not found")
    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data:
        i.name = update_data["name"]
    if "description" in update_data:
        i.description = update_data["description"]
    if "priority" in update_data:
        i.priority = update_data["priority"]
    if "policy_id" in update_data:
        i.policy_id = update_data["policy_id"]
    if "conditions" in update_data:
        i.conditions = json.dumps(update_data["conditions"])
    if "action" in update_data:
        i.action = update_data["action"]
    if "enabled" in update_data:
        i.enabled = update_data["enabled"]
    if "triggers" in update_data:
        i.triggers_data = json.dumps(update_data["triggers"])
    if "hooks" in update_data:
        i.hooks_data = json.dumps(update_data["hooks"])
    if "approvers" in update_data:
        i.approvers = json.dumps(update_data["approvers"])
    if "timeout" in update_data:
        i.timeout = json.dumps(update_data["timeout"])
    if "escalation" in update_data:
        i.escalation = json.dumps(update_data["escalation"])
    i.updated_at = datetime.utcnow()
    session.add(i)
    session.commit()
    session.refresh(i)
    return _interceptor_to_dict(i)


@router.delete("/interceptors/{interceptor_id}")
def delete_interceptor(interceptor_id: str, session: Session = Depends(get_session)):
    i = session.exec(
        select(GovernanceInterceptorDB).where(
            GovernanceInterceptorDB.id == interceptor_id
        )
    ).first()
    if not i:
        raise HTTPException(status_code=404, detail="Interceptor not found")
    session.delete(i)
    session.commit()
    return {"status": "success"}


# --- Policy CRUD (must be last to avoid conflict with static prefixes) ---
@router.get("/{policy_id}")
def get_approval_policy(policy_id: str, session: Session = Depends(get_session)):
    p = session.exec(
        select(GovernanceApprovalPolicy).where(
            GovernanceApprovalPolicy.approval_policy_id == policy_id
        )
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Approval policy not found")
    return _policy_to_dict(p)


@router.put("/{policy_id}")
def update_approval_policy(
    policy_id: str, body: ApprovalPolicyUpdate, session: Session = Depends(get_session)
):
    p = session.exec(
        select(GovernanceApprovalPolicy).where(
            GovernanceApprovalPolicy.approval_policy_id == policy_id
        )
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Approval policy not found")
    update_data = body.model_dump(exclude_unset=True)
    if "trigger_conditions" in update_data:
        p.trigger_conditions = json.dumps(update_data["trigger_conditions"])
    if "approvers" in update_data:
        p.approvers = json.dumps(update_data["approvers"])
    if "timeout" in update_data:
        p.timeout = json.dumps(update_data["timeout"])
    if "escalation" in update_data:
        p.escalation = json.dumps(update_data["escalation"])
    if "trigger_ids" in update_data:
        p.trigger_ids = json.dumps(update_data["trigger_ids"])
    if "hook_ids" in update_data:
        p.hook_ids = json.dumps(update_data["hook_ids"])
    if "name" in update_data:
        p.name = update_data["name"]
    if "description" in update_data:
        p.description = update_data["description"]
    p.updated_at = datetime.utcnow()
    session.add(p)
    session.commit()
    session.refresh(p)
    return _policy_to_dict(p)


@router.delete("/{policy_id}")
def delete_approval_policy(policy_id: str, session: Session = Depends(get_session)):
    p = session.exec(
        select(GovernanceApprovalPolicy).where(
            GovernanceApprovalPolicy.approval_policy_id == policy_id
        )
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Approval policy not found")
    session.delete(p)
    session.commit()
    return {"status": "success"}
