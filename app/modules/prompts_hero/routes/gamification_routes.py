"""Gamification routes — streaks, badges, profile summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session

router = APIRouter()


class ActivityRequest(BaseModel):
    user_id: str


def _svc():
    from common_lib.modules.prompts_hero.services.gamification_service import (
        GamificationService,
    )

    return GamificationService()


@router.get("/streak/{user_id}")
def get_streak(user_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    info = svc.get_streak_info(session, user_id)
    return {"success": True, "data": info}


@router.post("/streak/activity")
def record_activity(body: ActivityRequest, session: Session = Depends(get_session)):
    svc = _svc()
    streak = svc.record_activity(session, body.user_id)
    awarded = svc.check_and_award_streak_badges(session, body.user_id)
    return {
        "success": True,
        "data": {"streak": streak.current_streak, "badges_awarded": awarded},
    }


@router.get("/badges")
def list_badges(session: Session = Depends(get_session)):
    svc = _svc()
    badges = svc.get_all_badges(session)
    return {"success": True, "data": [b.model_dump() for b in badges]}


@router.get("/badges/user/{user_id}")
def list_user_badges(user_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    awards = svc.get_user_awards(session, user_id)
    return {"success": True, "data": [a.model_dump() for a in awards]}


@router.post("/badges/seed")
def seed_badges(session: Session = Depends(get_session)):
    svc = _svc()
    count = svc.seed_badges(session)
    return {"success": True, "data": {"counted": count}}


@router.get("/profile/{user_id}")
def get_profile_summary(user_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    summary = svc.get_user_profile_summary(session, user_id)
    return {"success": True, "data": summary}
