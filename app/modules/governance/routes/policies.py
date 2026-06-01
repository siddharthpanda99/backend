from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.policy.service import get_policy_service
from common_lib.modules.governance.models.policies import Policy, Rule

router = APIRouter(prefix="/policies", tags=["Governance - Policies"])


class PolicyCreate(BaseModel):
    policy_id: str = ""
    name: str
    description: str = ""
    category: str = "access_policy"
    status: str = "active"
    enabled: bool = True
    scope: dict = {}
    rules: list[dict] = []
    tags: list[str] = []


class PolicyUpdate(BaseModel):
    name: str = ""
    description: str = ""
    category: str = ""
    status: str = ""
    enabled: bool | None = None
    scope: dict | None = None
    rules: list[dict] | None = None
    tags: list[str] | None = None


@router.get("")
def list_policies():
    svc = get_policy_service()
    return [p.to_dict() for p in svc.list_policies()]


@router.post("")
def create_policy(body: PolicyCreate):
    svc = get_policy_service()
    rule_objs = [Rule(**r) for r in body.rules] if body.rules else []
    policy = Policy(
        policy_id=body.policy_id,
        name=body.name,
        description=body.description,
        category=body.category,
        status=body.status,
        enabled=body.enabled,
        scope=body.scope,
        rules=rule_objs,
        tags=body.tags,
    )
    result = svc.create(policy)
    return result.to_dict()


@router.put("/{policy_id}")
def update_policy(policy_id: str, body: PolicyUpdate):
    svc = get_policy_service()
    existing = svc.get(policy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Policy not found")
    updates = body.model_dump(exclude_unset=True)
    if "rules" in updates and updates["rules"] is not None:
        updates["rules"] = [Rule(**r) for r in updates["rules"]]
    for field, val in updates.items():
        if val is not None:
            setattr(existing, field, val)
    svc.update(existing)
    return existing.to_dict()


@router.delete("/{policy_id}")
def delete_policy(policy_id: str):
    svc = get_policy_service()
    svc.delete(policy_id)
    return {"success": True}


@router.post("/{policy_id}/enable")
def enable_policy(policy_id: str):
    svc = get_policy_service()
    svc.enable(policy_id)
    result = svc.get(policy_id)
    return result.to_dict() if result else {"success": True}


@router.post("/{policy_id}/disable")
def disable_policy(policy_id: str):
    svc = get_policy_service()
    svc.disable(policy_id)
    result = svc.get(policy_id)
    return result.to_dict() if result else {"success": True}
