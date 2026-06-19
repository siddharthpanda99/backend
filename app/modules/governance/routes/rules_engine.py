from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Optional

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.data_storage.database.repository import NotFoundError
from common_lib.modules.rules_engine.models import (
    RuleSetModel,
    RuleModel,
    RuleLibraryBlockModel,
    RuleSetRuleLink,
)
from common_lib.modules.governance.rule_engine_service import RuleEngineService
from pydantic import BaseModel

router = APIRouter(prefix="/rules-engine", tags=["Governance / Rules Engine"])

_service = RuleEngineService()


def get_service() -> RuleEngineService:
    return _service


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
def list_library_blocks(
    type: Optional[str] = None,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    return service.list_library_blocks(session, type_filter=type)


@router.post("/library", response_model=RuleLibraryBlockModel)
def create_library_block(
    block: RuleLibraryBlockCreate,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    return service.create_library_block(session, block.model_dump())


@router.get("/library/{block_id}", response_model=RuleLibraryBlockModel)
def get_library_block(
    block_id: str,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        return service.get_library_block(session, block_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Library block not found")


@router.put("/library/{block_id}", response_model=RuleLibraryBlockModel)
def update_library_block(
    block_id: str,
    updates: RuleLibraryBlockUpdate,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        return service.update_library_block(
            session, block_id, updates.model_dump(exclude_unset=True)
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Library block not found")


@router.delete("/library/{block_id}")
def delete_library_block(
    block_id: str,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        service.delete_library_block(session, block_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Library block not found")
    return {"message": "Deleted successfully"}


# --- Rule Sets ---


@router.get("/rulesets", response_model=List[RuleSetModel])
def list_rulesets(
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    return service.list_rulesets(session)


@router.post("/rulesets", response_model=RuleSetModel)
def create_ruleset(
    ruleset: RuleSetCreate,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    return service.create_ruleset(session, ruleset.model_dump())


@router.get("/rulesets/{ruleset_id}", response_model=RuleSetModel)
def get_ruleset(
    ruleset_id: str,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        return service.get_ruleset(session, ruleset_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Rule set not found")


@router.put("/rulesets/{ruleset_id}", response_model=RuleSetModel)
def update_ruleset(
    ruleset_id: str,
    updates: RuleSetUpdate,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        return service.update_ruleset(
            session, ruleset_id, updates.model_dump(exclude_unset=True)
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Rule set not found")


@router.delete("/rulesets/{ruleset_id}")
def delete_ruleset(
    ruleset_id: str,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        service.delete_ruleset(session, ruleset_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Rule set not found")
    return {"message": "Deleted successfully"}


# --- Rules ---


@router.get("/rules", response_model=List[RuleModel])
def list_rules(
    rule_set_id: Optional[str] = None,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    return service.list_rules(session, ruleset_id=rule_set_id)


@router.post("/rules", response_model=RuleModel)
def create_rule(
    rule: RuleCreate,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    return service.create_rule(session, rule.model_dump())


@router.get("/rules/{rule_id}", response_model=RuleModel)
def get_rule(
    rule_id: str,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        return service.get_rule(session, rule_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Rule not found")


@router.put("/rules/{rule_id}", response_model=RuleModel)
def update_rule(
    rule_id: str,
    updates: RuleUpdate,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        return service.update_rule(
            session, rule_id, updates.model_dump(exclude_unset=True)
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Rule not found")


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        service.delete_rule(session, rule_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Deleted successfully"}


@router.post("/rulesets/{ruleset_id}/rules/{rule_id}")
def link_rule_to_ruleset(
    ruleset_id: str,
    rule_id: str,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    service.link_rule_to_ruleset(session, ruleset_id, rule_id)
    return {"message": "Linked successfully"}


@router.get("/rulesets-links")
def list_ruleset_links(
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    return service.list_ruleset_links(session)


@router.delete("/rulesets/{ruleset_id}/rules/{rule_id}")
def unlink_rule_from_ruleset(
    ruleset_id: str,
    rule_id: str,
    session: Session = Depends(get_session),
    service: RuleEngineService = Depends(get_service),
):
    try:
        service.unlink_rule_from_ruleset(session, ruleset_id, rule_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"message": "Unlinked successfully"}
