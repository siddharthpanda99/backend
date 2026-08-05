"""PM Triage & Inbox — FastAPI routes (Module 14)."""

from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.modules.project_management.deps import get_pm_session

from common_lib.modules.project_management.triage.service import TriageService

router = APIRouter()


@router.get("/triage/inbox", summary="Get triage inbox")
def get_triage_inbox(
    team_id: Optional[str] = None,
    project_id: Optional[str] = None,
    session: Session = Depends(get_pm_session),
):
    svc = TriageService(session)
    return svc.get_inbox(team_id=team_id, project_id=project_id)


@router.post("/triage/inbox", summary="Add issue to triage inbox")
def add_to_inbox(body: dict, session: Session = Depends(get_pm_session)):
    svc = TriageService(session)
    return svc.add_to_inbox(**body)


@router.post("/triage/batch-triage", summary="Batch triage inbox entries")
def batch_triage(body: dict, session: Session = Depends(get_pm_session)):
    svc = TriageService(session)
    return {"count": svc.batch_triage(**body)}


@router.post("/triage/{entry_id}/mark-triaged", summary="Mark single entry as triaged")
def mark_triaged(entry_id: str, body: dict, session: Session = Depends(get_pm_session)):
    svc = TriageService(session)
    return svc.mark_triaged(entry_id, **body)


@router.post("/triage/{entry_id}/needs-info", summary="Mark entry as needing info")
def mark_needs_info(entry_id: str, body: dict, session: Session = Depends(get_pm_session)):
    svc = TriageService(session)
    return svc.mark_needs_info(entry_id, **body)


@router.get("/my-work/{user_id}", summary="Get user's personal inbox")
def get_my_work(user_id: str, session: Session = Depends(get_pm_session)):
    svc = TriageService(session)
    return svc.get_my_work(user_id=user_id)


@router.post("/my-work/dismiss/{item_id}", summary="Dismiss a work item")
def dismiss_item(item_id: str, session: Session = Depends(get_pm_session)):
    svc = TriageService(session)
    return {"ok": svc.dismiss_item(item_id)}


@router.post("/my-work/snooze/{item_id}", summary="Snooze a work item")
def snooze_item(item_id: str, hours: int = 24, session: Session = Depends(get_pm_session)):
    svc = TriageService(session)
    return svc.snooze_item(item_id, snooze_hours=hours)
