from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.ext_apps.models import ExtAppSession
from ..schemas import ExtAppSessionCreate, ExtAppSessionResponse
from ..engine import get_ext_app_engine

router = APIRouter(prefix="/sessions", tags=["Ext-Apps"])

@router.post("/", response_model=ExtAppSessionResponse)
async def create_session(
    session_data: ExtAppSessionCreate,
    db: Session = Depends(get_session)
):
    new_session = ExtAppSession(**session_data.model_dump())
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

@router.get("/{session_id}", response_model=ExtAppSessionResponse)
async def get_session_info(
    session_id: str,
    db: Session = Depends(get_session)
):
    session_obj = db.execute(select(ExtAppSession).where(ExtAppSession.id == session_id)).scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session_obj.last_accessed_at = datetime.utcnow()
    db.commit()
    db.refresh(session_obj)
    return session_obj

@router.post("/{session_id}/event")
async def process_view_event(
    session_id: str,
    request: Request,
    db: Session = Depends(get_session),
    engine = Depends(get_ext_app_engine)
):
    """
    Handle ext-apps protocol events (e.g. tools/call, ui/message)
    """
    session_obj = db.execute(select(ExtAppSession).where(ExtAppSession.id == session_id)).scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
        
    data = await request.json()
    event_type = data.get("method", "unknown")
    
    result = await engine.handle_view_event(
        event_type=event_type,
        view_id=session_obj.view_id,
        user_id=session_obj.user_id,
        data=data
    )
    
    return result

@router.post("/{session_id}/state")
async def update_session_state(
    session_id: str,
    request: Request,
    db: Session = Depends(get_session)
):
    """
    Update persistent state (useViewState) or context_llm (data-llm)
    """
    session_obj = db.execute(select(ExtAppSession).where(ExtAppSession.id == session_id)).scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
        
    data = await request.json()
    if "session_state" in data:
        session_obj.session_state = data["session_state"]
    if "context_llm" in data:
        session_obj.context_llm = data["context_llm"]
        
    session_obj.last_accessed_at = datetime.utcnow()
    db.commit()
    db.refresh(session_obj)
    
    return {"status": "updated"}
