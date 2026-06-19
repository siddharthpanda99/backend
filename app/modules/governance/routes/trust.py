from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from datetime import datetime
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.governance.db_models import (
    GovernanceTrustScore,
    GovernanceTrustEvent,
)

router = APIRouter(prefix="/trust", tags=["Governance - Trust"])


class TrustEventBody(BaseModel):
    subject_id: str
    event_type: str
    score_delta: float = 0.0
    reason: str = ""


class SetScoreBody(BaseModel):
    score: float
    reason: str = ""


def _compute_tier(score: float) -> str:
    if score > 0.8:
        return "exemplary"
    if score > 0.6:
        return "good_standing"
    if score > 0.4:
        return "monitored"
    if score > 0.2:
        return "probationary"
    return "restricted"


@router.get("/scores")
def list_scores(session: Session = Depends(get_session)):
    items = session.exec(select(GovernanceTrustScore)).all()
    return [
        {
            "subject_id": s.subject_id,
            "score": s.score,
            "tier": s.tier,
            "reason": s.reason,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in items
    ]


@router.put("/scores/{subject_id}")
def set_trust_score(
    subject_id: str, body: SetScoreBody, session: Session = Depends(get_session)
):
    tier = _compute_tier(body.score)
    existing = session.exec(
        select(GovernanceTrustScore).where(
            GovernanceTrustScore.subject_id == subject_id
        )
    ).first()
    if existing:
        existing.score = body.score
        existing.tier = tier
        existing.reason = body.reason
    else:
        existing = GovernanceTrustScore(
            subject_id=subject_id, score=body.score, tier=tier, reason=body.reason
        )
        session.add(existing)
    session.commit()
    session.refresh(existing)
    return {"subject_id": subject_id, "score": body.score, "tier": tier}


@router.get("/events")
def list_events(subject_id: str | None = None, session: Session = Depends(get_session)):
    stmt = select(GovernanceTrustEvent)
    if subject_id:
        stmt = stmt.where(GovernanceTrustEvent.subject_id == subject_id)
    items = session.exec(stmt).all()
    return [
        {
            "id": e.id,
            "subject_id": e.subject_id,
            "event_type": e.event_type,
            "score_delta": e.score_delta,
            "reason": e.reason,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in items
    ]


@router.post("/events")
def apply_trust_event(body: TrustEventBody, session: Session = Depends(get_session)):
    event = GovernanceTrustEvent(
        subject_id=body.subject_id,
        event_type=body.event_type,
        score_delta=body.score_delta,
        reason=body.reason,
    )
    session.add(event)

    existing = session.exec(
        select(GovernanceTrustScore).where(
            GovernanceTrustScore.subject_id == body.subject_id
        )
    ).first()
    new_score = (existing.score if existing else 0.5) + body.score_delta
    new_score = max(0.0, min(1.0, new_score))
    tier = _compute_tier(new_score)
    if existing:
        existing.score = new_score
        existing.tier = tier
        existing.reason = body.reason
    else:
        existing = GovernanceTrustScore(
            subject_id=body.subject_id, score=new_score, tier=tier, reason=body.reason
        )
        session.add(existing)
    session.commit()
    session.refresh(existing)
    return {"subject_id": body.subject_id, "score": new_score, "tier": tier}
