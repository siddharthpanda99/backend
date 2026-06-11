from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
import uuid

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.rules_engine.models import (
    RuleSetModel,
    RuleModel,
    RuleLibraryBlockModel,
    RuleSetRuleLink
)
from pydantic import BaseModel

router = APIRouter(prefix="/rules-engine", tags=["Governance / Rules Engine"])

# --- Models ---
class RuleSetCreate(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = 100

class RuleSetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None

class RuleCreate(BaseModel):
    rule_set_id: Optional[str] = None
    name: str
    type: str
    enabled: bool = True
    priority: int = 100
    condition_group: dict = {}
    actions: list = []
    metadata_json: str = "{}"

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    condition_group: Optional[dict] = None
    actions: Optional[list] = None
    metadata_json: Optional[str] = None

class RuleLibraryBlockCreate(BaseModel):
    name: str
    description: str = ""
    type: str
    data: dict

class RuleLibraryBlockUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    data: Optional[dict] = None

# --- Library Blocks (Reusable rules) ---

@router.get("/library", response_model=List[RuleLibraryBlockModel])
def list_library_blocks(type: Optional[str] = None, session: Session = Depends(get_session)):
    query = select(RuleLibraryBlockModel)
    if type:
        query = query.where(RuleLibraryBlockModel.type == type)
    return session.exec(query).all()

@router.post("/library", response_model=RuleLibraryBlockModel)
def create_library_block(block: RuleLibraryBlockCreate, session: Session = Depends(get_session)):
    db_block = RuleLibraryBlockModel(
        id=f"lib_{uuid.uuid4().hex[:8]}",
        name=block.name,
        description=block.description,
        type=block.type,
        data=block.data,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_block)
    session.commit()
    session.refresh(db_block)
    return db_block

@router.get("/library/{block_id}", response_model=RuleLibraryBlockModel)
def get_library_block(block_id: str, session: Session = Depends(get_session)):
    block = session.get(RuleLibraryBlockModel, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Library block not found")
    return block

@router.put("/library/{block_id}", response_model=RuleLibraryBlockModel)
def update_library_block(block_id: str, updates: RuleLibraryBlockUpdate, session: Session = Depends(get_session)):
    block = session.get(RuleLibraryBlockModel, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Library block not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(block, key, value)
    
    block.updated_at = datetime.utcnow()
    session.add(block)
    session.commit()
    session.refresh(block)
    return block

@router.delete("/library/{block_id}")
def delete_library_block(block_id: str, session: Session = Depends(get_session)):
    block = session.get(RuleLibraryBlockModel, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Library block not found")
    session.delete(block)
    session.commit()
    return {"message": "Deleted successfully"}


# --- Rule Sets ---

@router.get("/rulesets", response_model=List[RuleSetModel])
def list_rulesets(session: Session = Depends(get_session)):
    return session.exec(select(RuleSetModel)).all()

@router.post("/rulesets", response_model=RuleSetModel)
def create_ruleset(ruleset: RuleSetCreate, session: Session = Depends(get_session)):
    db_ruleset = RuleSetModel(
        id=f"rs_{uuid.uuid4().hex[:8]}",
        name=ruleset.name,
        description=ruleset.description,
        enabled=ruleset.enabled,
        priority=ruleset.priority,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_ruleset)
    session.commit()
    session.refresh(db_ruleset)
    return db_ruleset

@router.get("/rulesets/{ruleset_id}", response_model=RuleSetModel)
def get_ruleset(ruleset_id: str, session: Session = Depends(get_session)):
    ruleset = session.get(RuleSetModel, ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="Rule set not found")
    return ruleset

@router.put("/rulesets/{ruleset_id}", response_model=RuleSetModel)
def update_ruleset(ruleset_id: str, updates: RuleSetUpdate, session: Session = Depends(get_session)):
    ruleset = session.get(RuleSetModel, ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="Rule set not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ruleset, key, value)
        
    ruleset.updated_at = datetime.utcnow()
    session.add(ruleset)
    session.commit()
    session.refresh(ruleset)
    return ruleset

@router.delete("/rulesets/{ruleset_id}")
def delete_ruleset(ruleset_id: str, session: Session = Depends(get_session)):
    ruleset = session.get(RuleSetModel, ruleset_id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="Rule set not found")
    
    # First delete any links
    links = session.exec(select(RuleSetRuleLink).where(RuleSetRuleLink.rule_set_id == ruleset_id)).all()
    for link in links:
        session.delete(link)
    session.flush()
    
    session.delete(ruleset)
    session.commit()
    return {"message": "Deleted successfully"}

# --- Rules ---

@router.get("/rules", response_model=List[RuleModel])
def list_rules(rule_set_id: Optional[str] = None, session: Session = Depends(get_session)):
    query = select(RuleModel)
    if rule_set_id:
        query = query.join(RuleSetRuleLink, RuleSetRuleLink.rule_id == RuleModel.id).where(RuleSetRuleLink.rule_set_id == rule_set_id)
    return session.exec(query).all()

@router.post("/rules", response_model=RuleModel)
def create_rule(rule: RuleCreate, session: Session = Depends(get_session)):
    db_rule = RuleModel(
        id=f"rule_{uuid.uuid4().hex[:8]}",
        name=rule.name,
        type=rule.type,
        enabled=rule.enabled,
        priority=rule.priority,
        condition_group=rule.condition_group,
        actions=rule.actions,
        metadata_json=rule.metadata_json,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_rule)
    session.commit()
    session.refresh(db_rule)
    
    if rule.rule_set_id:
        link = RuleSetRuleLink(
            rule_set_id=rule.rule_set_id,
            rule_id=db_rule.id,
            created_at=datetime.utcnow()
        )
        session.add(link)
        session.commit()
        
    return db_rule

@router.get("/rules/{rule_id}", response_model=RuleModel)
def get_rule(rule_id: str, session: Session = Depends(get_session)):
    rule = session.get(RuleModel, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@router.put("/rules/{rule_id}", response_model=RuleModel)
def update_rule(rule_id: str, updates: RuleUpdate, session: Session = Depends(get_session)):
    rule = session.get(RuleModel, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
        
    rule.updated_at = datetime.utcnow()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule

@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, session: Session = Depends(get_session)):
    rule = session.get(RuleModel, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    # First delete any links
    links = session.exec(select(RuleSetRuleLink).where(RuleSetRuleLink.rule_id == rule_id)).all()
    for link in links:
        session.delete(link)
    session.flush()
    
    session.delete(rule)
    session.commit()
    return {"message": "Deleted successfully"}

@router.post("/rulesets/{ruleset_id}/rules/{rule_id}")
def link_rule_to_ruleset(ruleset_id: str, rule_id: str, session: Session = Depends(get_session)):
    existing_link = session.exec(select(RuleSetRuleLink).where(
        RuleSetRuleLink.rule_set_id == ruleset_id,
        RuleSetRuleLink.rule_id == rule_id
    )).first()
    if existing_link:
        return {"message": "Already linked"}
        
    link = RuleSetRuleLink(
        rule_set_id=ruleset_id,
        rule_id=rule_id,
        created_at=datetime.utcnow()
    )
    session.add(link)
    session.commit()
    return {"message": "Linked successfully"}

@router.get("/rulesets-links")
def list_ruleset_links(session: Session = Depends(get_session)):
    return session.exec(select(RuleSetRuleLink)).all()

@router.delete("/rulesets/{ruleset_id}/rules/{rule_id}")
def unlink_rule_from_ruleset(ruleset_id: str, rule_id: str, session: Session = Depends(get_session)):
    link = session.exec(select(RuleSetRuleLink).where(
        RuleSetRuleLink.rule_set_id == ruleset_id,
        RuleSetRuleLink.rule_id == rule_id
    )).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
        
    session.delete(link)
    session.commit()
    return {"message": "Unlinked successfully"}
