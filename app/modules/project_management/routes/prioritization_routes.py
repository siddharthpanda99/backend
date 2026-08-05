"""PM Prioritization — FastAPI routes for RICE/ICE/MoSCoW/custom scoring."""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.project_management.deps import get_pm_session

from common_lib.modules.project_management.prioritization.service import PrioritizationService

router = APIRouter()


@router.post("/prioritization/rice", summary="Score using RICE")
def score_rice(body: dict, session: Session = Depends(get_pm_session)):
    svc = PrioritizationService(session)
    return svc.score_rice(**body)


@router.post("/prioritization/ice", summary="Score using ICE")
def score_ice(body: dict, session: Session = Depends(get_pm_session)):
    svc = PrioritizationService(session)
    return svc.score_ice(**body)


@router.post("/prioritization/moscow", summary="Classify using MoSCoW")
def classify_moscow(body: dict, session: Session = Depends(get_pm_session)):
    svc = PrioritizationService(session)
    return svc.classify_moscow(**body)


@router.get("/prioritization/scores", summary="Get scores for entity")
def get_scores(entity_type: str, entity_id: str, session: Session = Depends(get_pm_session)):
    svc = PrioritizationService(session)
    return svc.get_scores(entity_type=entity_type, entity_id=entity_id)


@router.get("/prioritization/leaderboard", summary="Top scored items by framework")
def leaderboard(
    framework: str = "rice",
    entity_type: Optional[str] = None,
    limit: int = 20,
    session: Session = Depends(get_pm_session),
):
    svc = PrioritizationService(session)
    return svc.list_by_framework(entity_type=entity_type, framework=framework, limit=limit)


@router.post("/prioritization/formulas", summary="Create scoring formula")
def create_formula(body: dict, session: Session = Depends(get_pm_session)):
    svc = PrioritizationService(session)
    return svc.create_formula(**body)


@router.post("/prioritization/custom", summary="Score using custom formula")
def score_custom(body: dict, session: Session = Depends(get_pm_session)):
    svc = PrioritizationService(session)
    return svc.score_custom(**body)
