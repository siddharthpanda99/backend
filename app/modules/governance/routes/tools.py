from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import GovernanceTool
import json

router = APIRouter(prefix="/tools", tags=["Governance - Tools"])


class ToolCreate(BaseModel):
    tool_id: str
    name: str = ""
    description: str = ""
    owner: str = ""
    version: str = "1.0.0"
    risk_level: str = "low"
    category: str = "general"
    resource_type: str = ""
    side_effects: bool = False
    reversible: bool = True
    idempotent: bool = True
    data_classification: str = "internal"
    rate_limits: dict = {}
    parameter_rules: list[dict] = []
    audit_level: str = "full"
    approved_for_agents: list[str] = []
    status: str = "active"


class ToolUpdate(BaseModel):
    name: str = ""
    description: str = ""
    owner: str = ""
    version: str = ""
    risk_level: str = ""
    category: str = ""
    side_effects: bool | None = None
    reversible: bool | None = None
    data_classification: str = ""
    audit_level: str = ""
    status: str = ""


def _tool_to_dict(t: GovernanceTool) -> dict:
    extras = (
        json.loads(t.extras_json) if hasattr(t, "extras_json") and t.extras_json else {}
    )
    allowed = json.loads(t.allowed_roles_json) if t.allowed_roles_json else ["admin"]
    return {
        "tool_id": t.tool_id,
        "name": t.name,
        "description": t.description or "",
        "risk_level": t.risk_level,
        "enabled": t.enabled,
        "allowed_agents": allowed,
        "owner": extras.get("owner", ""),
        "version": extras.get("version", "1.0.0"),
        "category": extras.get("category", "general"),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("")
def list_tools(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceTool)).all()
    return [_tool_to_dict(t) for t in items]


@router.post("")
def register_tool(body: ToolCreate, session: Session = Depends(get_session)):
    existing = session.exec(
        select(GovernanceTool).where(GovernanceTool.tool_id == body.tool_id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tool already exists")
    tool = GovernanceTool(
        tool_id=body.tool_id,
        name=body.name or body.tool_id,
        description=body.description,
        risk_level=body.risk_level,
        allowed_roles_json=json.dumps(body.approved_for_agents),
        enabled=(body.status == "active"),
    )
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return _tool_to_dict(tool)


@router.get("/{tool_id}")
def get_tool(tool_id: str, session: Session = Depends(get_session)):
    tool = session.exec(
        select(GovernanceTool).where(GovernanceTool.tool_id == tool_id)
    ).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return _tool_to_dict(tool)


@router.put("/{tool_id}")
def update_tool(
    tool_id: str, body: ToolUpdate, session: Session = Depends(get_session)
):
    tool = session.exec(
        select(GovernanceTool).where(GovernanceTool.tool_id == tool_id)
    ).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if body.name:
        tool.name = body.name
    if body.description:
        tool.description = body.description
    if body.risk_level:
        tool.risk_level = body.risk_level
    if body.status:
        tool.enabled = body.status == "active"
    tool.updated_at = datetime.utcnow()
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return _tool_to_dict(tool)


@router.post("/{tool_id}/validate")
def validate_invocation(
    tool_id: str, body: dict, session: Session = Depends(get_session)
):
    tool = session.exec(
        select(GovernanceTool).where(GovernanceTool.tool_id == tool_id)
    ).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"tool_id": tool_id, "valid": tool.enabled, "risk_level": tool.risk_level}


@router.get("/{tool_id}/risk")
def get_tool_risk(tool_id: str, session: Session = Depends(get_session)):
    tool = session.exec(
        select(GovernanceTool).where(GovernanceTool.tool_id == tool_id)
    ).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"tool_id": tool_id, "risk_level": tool.risk_level, "enabled": tool.enabled}
