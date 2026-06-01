from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.tools.service import get_tool_service
from common_lib.modules.governance.models.tools import ToolDefinition

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


class ValidateInvocationRequest(BaseModel):
    agent_id: str
    parameters: dict = {}
    environment: str = "development"


@router.get("")
def list_tools():
    svc = get_tool_service()
    return [t.to_dict() for t in svc.list_tools()]


@router.post("")
def register_tool(body: ToolCreate):
    svc = get_tool_service()
    tool = ToolDefinition(
        tool_id=body.tool_id,
        name=body.name,
        description=body.description,
        owner=body.owner,
        version=body.version,
        risk_level=body.risk_level,
        category=body.category,
        resource_type=body.resource_type,
        side_effects=body.side_effects,
        reversible=body.reversible,
        idempotent=body.idempotent,
        data_classification=body.data_classification,
        rate_limits=body.rate_limits,
        parameter_rules=body.parameter_rules,
        audit_level=body.audit_level,
        approved_for_agents=body.approved_for_agents,
        status=body.status,
    )
    result = svc.register(tool)
    return result.to_dict()


@router.get("/{tool_id}")
def get_tool(tool_id: str):
    svc = get_tool_service()
    result = svc.get(tool_id)
    if not result:
        raise HTTPException(status_code=404, detail="Tool not found")
    return result.to_dict()


@router.put("/{tool_id}")
def update_tool(tool_id: str, body: ToolUpdate):
    svc = get_tool_service()
    existing = svc.get(tool_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Tool not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None and hasattr(existing, field):
            setattr(existing, field, val)
    svc.update(existing)
    return existing.to_dict()


@router.post("/{tool_id}/validate")
def validate_invocation(tool_id: str, body: ValidateInvocationRequest):
    svc = get_tool_service()
    result = svc.validate_invocation(
        body.agent_id,
        tool_id,
        body.parameters,
        body.environment,
    )
    return result


@router.get("/{tool_id}/risk")
def get_tool_risk(tool_id: str):
    svc = get_tool_service()
    return svc.get_risk_classification(tool_id)
