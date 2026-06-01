from fastapi import APIRouter
from pydantic import BaseModel
from common_lib.modules.governance.integration.client import get_governance_client
from common_lib.modules.governance.integration.client import PEPKind

router = APIRouter(prefix="/integration", tags=["Governance - Integration"])


class EvaluateRequest(BaseModel):
    agent_id: str
    action: str
    resource: dict = {}
    environment: str = "development"
    context: dict = {}


class ValidateTokenRequest(BaseModel):
    token: str
    required_capabilities: list[str] = []
    required_tool: str = ""


class InterceptRequest(BaseModel):
    kind: str = "pre"
    agent_id: str
    action: str
    resource: dict = {}
    environment: str = "development"
    context: dict = {}


class AuditEventRequest(BaseModel):
    event_type: str
    agent_id: str
    action: str
    decision: dict = {}
    context: dict = {}
    outcome: dict = {}
    trace_id: str = ""


class ApprovalRequestCreate(BaseModel):
    approval_policy_id: str
    requesting_agent: str
    action: str
    tool: str
    justification: str = ""
    context: dict = {}


@router.post("/evaluate")
def evaluate(body: EvaluateRequest):
    client = get_governance_client()
    return client.evaluate(
        body.agent_id,
        body.action,
        body.resource,
        body.environment,
        body.context,
    )


@router.post("/validate-token")
def validate_token(body: ValidateTokenRequest):
    client = get_governance_client()
    return client.validate_token(
        body.token,
        body.required_capabilities,
        body.required_tool,
    )


@router.post("/intercept")
def intercept(body: InterceptRequest):
    client = get_governance_client()
    kind = body.kind
    if isinstance(kind, str):
        try:
            kind = PEPKind(kind)
        except ValueError:
            kind = PEPKind.PRE
    return client.intercept(
        kind,
        body.agent_id,
        body.action,
        body.resource,
        body.environment,
        body.context,
    )


@router.post("/audit-event")
def write_audit_event(body: AuditEventRequest):
    client = get_governance_client()
    event = client.write_audit_event(
        body.event_type,
        body.agent_id,
        body.action,
        body.decision,
        body.context,
        body.outcome,
        body.trace_id,
    )
    return {"event_id": getattr(event, "event_id", ""), "success": True}


@router.post("/approval-request")
def create_approval_request(body: ApprovalRequestCreate):
    client = get_governance_client()
    return client.create_approval_request(
        body.approval_policy_id,
        body.requesting_agent,
        body.action,
        body.tool,
        body.justification,
        body.context,
    )


@router.get("/approval-request/{request_id}/status")
def poll_approval_status(request_id: str):
    client = get_governance_client()
    return client.poll_approval_status(request_id)


@router.get("/contract/{kind}")
def get_integration_contract(kind: str):
    client = get_governance_client()
    try:
        pk = PEPKind(kind)
    except ValueError:
        pk = PEPKind.PRE
    return client.get_integration_contract(pk)
