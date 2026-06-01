from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.engine.service import get_policy_engine
from common_lib.modules.governance.models.decisions import AuthZRequest

router = APIRouter(prefix="/engine", tags=["Governance - Engine"])


class EvaluateRequest(BaseModel):
    agent_id: str
    action: str
    resource: dict = {}
    environment: str = "development"
    context: dict = {}
    agent_roles: list[str] = []
    trust_score: float = 0.0
    department: str = ""


class InterceptRequest(BaseModel):
    agent_id: str
    action: str
    resource: dict = {}
    environment: str = "development"
    context: dict = {}


@router.post("/evaluate")
def evaluate(body: EvaluateRequest):
    svc = get_policy_engine()
    req = AuthZRequest(
        agent_id=body.agent_id,
        action=body.action,
        resource=body.resource,
        environment=body.environment,
        context=body.context,
        agent_roles=body.agent_roles,
        trust_score=body.trust_score,
        department=body.department,
    )
    decision = svc.evaluate(req)
    return (
        decision.to_dict()
        if hasattr(decision, "to_dict")
        else {"decision": str(decision)}
    )


@router.post("/intercept")
def intercept(body: InterceptRequest):
    svc = get_policy_engine()
    req = AuthZRequest(
        agent_id=body.agent_id,
        action=body.action,
        resource=body.resource,
        environment=body.environment,
        context=body.context,
    )
    from common_lib.modules.governance.engine.service import PEPInterceptor

    interceptor = PEPInterceptor(svc)
    decision = interceptor.intercept(req)
    return (
        decision.to_dict()
        if hasattr(decision, "to_dict")
        else {"decision": str(decision)}
    )
