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
            "trigger_ids",
            "hook_ids",
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
        trigger_ids=body.trigger_ids,
        hook_ids=body.hook_ids,
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
        "trigger_ids",
        "hook_ids",
    ]:
        if hasattr(result, attr):
            d[attr] = getattr(result, attr)
    return d


# --- Triggers CRUD (static routes before dynamic /{policy_id}) ---
@router.get("/triggers")
def list_triggers():
    svc = get_hitl_service()
    return svc.list_triggers()


@router.post("/triggers")
def create_trigger(body: dict):
    svc = get_hitl_service()
    return svc.define_trigger(body)


@router.get("/triggers/{trigger_id}")
def get_trigger(trigger_id: str):
    svc = get_hitl_service()
    result = svc.get_trigger(trigger_id)
    if not result:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return result.to_dict()


@router.put("/triggers/{trigger_id}")
def update_trigger(trigger_id: str, body: dict):
    svc = get_hitl_service()
    body["id"] = trigger_id
    result = svc.define_trigger(body)
    return result.to_dict()


@router.delete("/triggers/{trigger_id}")
def delete_trigger(trigger_id: str):
    svc = get_hitl_service()
    if not svc.delete_trigger(trigger_id):
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"status": "success"}


# --- Hooks CRUD ---
@router.get("/hooks")
def list_hooks():
    svc = get_hitl_service()
    return svc.list_hooks()


@router.post("/hooks")
def create_hook(body: dict):
    svc = get_hitl_service()
    return svc.define_hook(body)


@router.get("/hooks/{hook_id}")
def get_hook(hook_id: str):
    svc = get_hitl_service()
    result = svc.get_hook(hook_id)
    if not result:
        raise HTTPException(status_code=404, detail="Hook not found")
    return result.to_dict()


@router.put("/hooks/{hook_id}")
def update_hook(hook_id: str, body: dict):
    svc = get_hitl_service()
    body["id"] = hook_id
    result = svc.define_hook(body)
    return result.to_dict()


@router.delete("/hooks/{hook_id}")
def delete_hook(hook_id: str):
    svc = get_hitl_service()
    if not svc.delete_hook(hook_id):
        raise HTTPException(status_code=404, detail="Hook not found")
    return {"status": "success"}


# --- Interceptors CRUD ---
@router.get("/interceptors")
def list_interceptors():
    svc = get_hitl_service()
    return [i.to_dict() for i in svc.list_interceptors()]


@router.get("/interceptors/{interceptor_id}")
def get_interceptor(interceptor_id: str):
    svc = get_hitl_service()
    result = svc.get_interceptor(interceptor_id)
    if not result:
        raise HTTPException(status_code=404, detail="Interceptor not found")
    return result.to_dict()


@router.post("/interceptors")
def create_interceptor(body: InterceptorCreate):
    svc = get_hitl_service()
    result = svc.define_interceptor(body.model_dump())
    return result.to_dict()


@router.put("/interceptors/{interceptor_id}")
def update_interceptor(interceptor_id: str, body: InterceptorUpdate):
    svc = get_hitl_service()
    existing = svc.get_interceptor(interceptor_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Interceptor not found")
    data = body.model_dump(exclude_unset=True)
    data["id"] = interceptor_id
    result = svc.define_interceptor(data)
    return result.to_dict()


@router.delete("/interceptors/{interceptor_id}")
def delete_interceptor(interceptor_id: str):
    svc = get_hitl_service()
    if not svc.delete_interceptor(interceptor_id):
        raise HTTPException(status_code=404, detail="Interceptor not found")
    return {"status": "success"}


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
        "trigger_ids",
        "hook_ids",
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
        "trigger_ids",
        "hook_ids",
    ]:
        if hasattr(existing, attr):
            d[attr] = getattr(existing, attr)
    return d


@router.delete("/{policy_id}")
def delete_approval_policy(policy_id: str):
    svc = get_hitl_service()
    if not svc.delete_approval_policy(policy_id):
        raise HTTPException(status_code=404, detail="Approval policy not found")
    return {"status": "success"}
