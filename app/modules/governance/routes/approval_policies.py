from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.hitl.service import get_hitl_service
from common_lib.modules.governance.models.approvals import ApprovalPolicyDef

router = APIRouter(prefix="/approval-policies", tags=["Governance - Approval Policies"])


class ApprovalPolicyCreate(BaseModel):
    approval_policy_id: str
    name: str = ""
    description: str = ""
    trigger_conditions: list[dict] = []
    approvers: dict = {}
    timeout: dict = {}
    escalation: dict = {}


class ApprovalPolicyUpdate(BaseModel):
    name: str = ""
    description: str = ""
    trigger_conditions: list[dict] | None = None
    approvers: dict | None = None
    timeout: dict | None = None
    escalation: dict | None = None


@router.get("")
def list_approval_policies():
    svc = get_hitl_service()
    items = svc.list_approval_policies()
    result = []
    for p in items:
        d = {}
        for attr in [
            "approval_policy_id",
            "name",
            "description",
            "trigger_conditions",
            "approvers",
            "timeout",
            "escalation",
        ]:
            if hasattr(p, attr):
                d[attr] = getattr(p, attr)
        result.append(d)
    return result


@router.post("")
def create_approval_policy(body: ApprovalPolicyCreate):
    svc = get_hitl_service()
    policy = ApprovalPolicyDef(
        approval_policy_id=body.approval_policy_id,
        name=body.name,
        description=body.description,
        trigger_conditions=body.trigger_conditions,
        approvers=body.approvers,
        timeout=body.timeout,
        escalation=body.escalation,
    )
    result = svc.define_approval_policy(policy)
    d = {}
    for attr in [
        "approval_policy_id",
        "name",
        "description",
        "trigger_conditions",
        "approvers",
        "timeout",
        "escalation",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.get("/{policy_id}")
def get_approval_policy(policy_id: str):
    svc = get_hitl_service()
    result = svc.get_approval_policy(policy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Approval policy not found")
    d = {}
    for attr in [
        "approval_policy_id",
        "name",
        "description",
        "trigger_conditions",
        "approvers",
        "timeout",
        "escalation",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


@router.put("/{policy_id}")
def update_approval_policy(policy_id: str, body: ApprovalPolicyUpdate):
    svc = get_hitl_service()
    existing = svc.get_approval_policy(policy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Approval policy not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None and hasattr(existing, field):
            setattr(existing, field, val)
    svc.define_approval_policy(existing)
    d = {}
    for attr in [
        "approval_policy_id",
        "name",
        "description",
        "trigger_conditions",
        "approvers",
        "timeout",
        "escalation",
    ]:
        if hasattr(existing, attr):
            d[attr] = getattr(existing, attr)
    return d
