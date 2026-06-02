from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
from common_lib.modules.governance.policy.service import get_policy_service
from common_lib.modules.governance.models.policies import Policy, Rule
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.rules_engine.models import (
    PolicyGroupModel,
    PolicyGroupPolicyLink,
    PolicyModel
)

router = APIRouter(prefix="/policies", tags=["Governance - Policies"])

class PolicyCreate(BaseModel):
    id: str = ""
    name: str
    policy_type: str = "access"
    algorithm: str = "deny_overrides"
    statements: List[Dict[str, Any]] = []
    priority: int = 0
    natural_language_instructions: str = ""
    metadata: Dict[str, Any] = {}
    enabled: bool = True

class PolicyUpdate(BaseModel):
    name: str = ""
    policy_type: str = ""
    algorithm: str = ""
    statements: List[Dict[str, Any]] | None = None
    priority: int | None = None
    natural_language_instructions: str | None = None
    metadata: Dict[str, Any] | None = None
    enabled: bool | None = None

# --- Policy Groups Schemas ---
class PolicyGroupCreate(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = 10

class PolicyGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None


@router.get("")
def list_policies(policy_group_id: Optional[str] = None, session: Session = Depends(get_session)):
    if policy_group_id:
        policy_ids = session.exec(select(PolicyGroupPolicyLink.policy_id).where(PolicyGroupPolicyLink.policy_group_id == policy_group_id)).all()
        query = select(PolicyModel).where(PolicyModel.policy_id.in_(policy_ids))
        models = session.exec(query).all()
        svc = get_policy_service(session)
        return [svc._to_dataclass(m).to_dict() for m in models]
        
    svc = get_policy_service(session)
    return [p.to_dict() for p in svc.list_policies()]

@router.post("")
def create_policy(body: PolicyCreate, session: Session = Depends(get_session)):
    svc = get_policy_service(session)
    policy = Policy.from_dict(body.model_dump())
    result = svc.create(policy)
    return result.to_dict()

@router.put("/{policy_id}")
def update_policy(policy_id: str, body: PolicyUpdate, session: Session = Depends(get_session)):
    svc = get_policy_service(session)
    existing = svc.get(policy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Policy not found")
        
    updates = body.model_dump(exclude_unset=True)
    if "statements" in updates and updates["statements"] is not None:
        updated_dict = existing.to_dict()
        updated_dict.update(updates)
        new_policy = Policy.from_dict(updated_dict)
        new_policy.id = policy_id
        svc.update(new_policy)
        return new_policy.to_dict()
    else:
        for field, val in updates.items():
            if val is not None:
                setattr(existing, field, val)
        svc.update(existing)
        return existing.to_dict()

@router.delete("/{policy_id}")
def delete_policy(policy_id: str, session: Session = Depends(get_session)):
    svc = get_policy_service(session)
    # Clean up group links first
    links = session.exec(select(PolicyGroupPolicyLink).where(PolicyGroupPolicyLink.policy_id == policy_id)).all()
    for link in links:
        session.delete(link)
    svc.delete(policy_id)
    return {"success": True}

@router.post("/{policy_id}/enable")
def enable_policy(policy_id: str, session: Session = Depends(get_session)):
    svc = get_policy_service(session)
    svc.enable(policy_id)
    result = svc.get(policy_id)
    return result.to_dict() if result else {"success": True}

@router.post("/{policy_id}/disable")
def disable_policy(policy_id: str, session: Session = Depends(get_session)):
    svc = get_policy_service(session)
    svc.disable(policy_id)
    result = svc.get(policy_id)
    return result.to_dict() if result else {"success": True}


# --- Policy Groups CRUD ---

@router.get("/groups", response_model=List[PolicyGroupModel])
def list_policy_groups(session: Session = Depends(get_session)):
    return session.exec(select(PolicyGroupModel)).all()

@router.post("/groups", response_model=PolicyGroupModel)
def create_policy_group(group: PolicyGroupCreate, session: Session = Depends(get_session)):
    db_group = PolicyGroupModel(
        id=f"pg_{uuid.uuid4().hex[:8]}",
        name=group.name,
        description=group.description,
        enabled=group.enabled,
        priority=group.priority,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_group)
    session.commit()
    session.refresh(db_group)
    return db_group

@router.get("/groups/{group_id}", response_model=PolicyGroupModel)
def get_policy_group(group_id: str, session: Session = Depends(get_session)):
    group = session.get(PolicyGroupModel, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Policy group not found")
    return group

@router.put("/groups/{group_id}", response_model=PolicyGroupModel)
def update_policy_group(group_id: str, updates: PolicyGroupUpdate, session: Session = Depends(get_session)):
    group = session.get(PolicyGroupModel, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Policy group not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
        
    group.updated_at = datetime.utcnow()
    session.add(group)
    session.commit()
    session.refresh(group)
    return group

@router.delete("/groups/{group_id}")
def delete_policy_group(group_id: str, session: Session = Depends(get_session)):
    group = session.get(PolicyGroupModel, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Policy group not found")
    # Clean up links first
    links = session.exec(select(PolicyGroupPolicyLink).where(PolicyGroupPolicyLink.policy_group_id == group_id)).all()
    for link in links:
        session.delete(link)
    session.delete(group)
    session.commit()
    return {"message": "Deleted successfully"}


# --- Group Policy Links ---

@router.get("/groups-links")
def list_group_links(session: Session = Depends(get_session)):
    return session.exec(select(PolicyGroupPolicyLink)).all()

@router.post("/groups/{group_id}/policies/{policy_id}")
def link_policy_to_group(group_id: str, policy_id: str, session: Session = Depends(get_session)):
    group = session.get(PolicyGroupModel, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Policy group not found")
        
    policy = session.exec(select(PolicyModel).where(PolicyModel.policy_id == policy_id)).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
        
    existing_link = session.exec(select(PolicyGroupPolicyLink).where(
        PolicyGroupPolicyLink.policy_group_id == group_id,
        PolicyGroupPolicyLink.policy_id == policy_id
    )).first()
    if existing_link:
        return {"message": "Already linked"}
        
    link = PolicyGroupPolicyLink(
        policy_group_id=group_id,
        policy_id=policy_id,
        created_at=datetime.utcnow()
    )
    session.add(link)
    session.commit()
    return {"message": "Linked successfully"}

@router.delete("/groups/{group_id}/policies/{policy_id}")
def unlink_policy_from_group(group_id: str, policy_id: str, session: Session = Depends(get_session)):
    link = session.exec(select(PolicyGroupPolicyLink).where(
        PolicyGroupPolicyLink.policy_group_id == group_id,
        PolicyGroupPolicyLink.policy_id == policy_id
    )).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
        
    session.delete(link)
    session.commit()
    return {"message": "Unlinked successfully"}
