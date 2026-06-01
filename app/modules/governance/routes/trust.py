from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from common_lib.modules.governance.trust.service import get_trust_service

router = APIRouter(prefix="/trust", tags=["Governance - Trust"])


class TrustEventBody(BaseModel):
    agent_id: str
    event_type: str
    description: str = ""


class SetScoreBody(BaseModel):
    score: float


@router.get("/scores")
def list_scores():
    svc = get_trust_service()
    items = svc.list_scores()
    result = []
    for item in items:
        d = {
            "agent_id": getattr(item, "agent_id", ""),
            "score": getattr(item, "score", 0),
        }
        for attr in [
            "tier",
            "security_score",
            "reliability_score",
            "compliance_score",
            "accuracy_score",
            "human_feedback",
            "last_updated",
        ]:
            if hasattr(item, attr):
                d[attr] = getattr(item, attr)
        result.append(d)
    return result


@router.put("/scores/{agent_id}")
def set_trust_score(agent_id: str, body: SetScoreBody):
    svc = get_trust_service()
    result = svc.get_or_create(agent_id, body.score)
    return {
        "agent_id": agent_id,
        "score": body.score,
        "tier": getattr(result, "tier", "bronze"),
    }


@router.get("/events")
def list_events():
    svc = get_trust_service()
    items: list = []
    for agent in svc.list_scores():
        try:
            items.extend(svc.get_events(getattr(agent, "agent_id", "")))
        except Exception:
            pass
    result = []
    for item in items:
        d = {
            "event_id": getattr(item, "event_id", ""),
            "agent_id": getattr(item, "agent_id", ""),
        }
        for attr in ["event_type", "impact", "description", "timestamp", "permanent"]:
            if hasattr(item, attr):
                d[attr] = getattr(item, attr)
        result.append(d)
    return result


@router.post("/events")
def apply_trust_event(body: TrustEventBody):
    svc = get_trust_service()
    updated = svc.apply_event(body.agent_id, body.event_type, body.description)
    return {"agent_id": body.agent_id, "score": getattr(updated, "score", 0)}
