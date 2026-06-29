"""Session management API — thin router delegating to SessionService."""

import json
import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlmodel import Session as SQLSession

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.session_service.service import SessionService
from common_lib.modules.agents.session_service.exceptions import NotFoundError
from common_lib.modules.agents.session_schemas import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    ToolCallCreate,
    ToolCallResponse,
    SessionStateUpdate,
    SessionStateResponse,
    SmartChatRequest,
    FileUploadResponse,
    EvolutionFeedbackRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])
svc = SessionService()


def _or_404(result, detail="Resource not found"):
    if result is None:
        raise HTTPException(status_code=404, detail=detail)
    return result


@router.get("/health")
def health_check():
    return {"status": "ok", "message": "Session routes loaded"}


@router.get("/debug/messages", tags=["Debug"])
def debug_all_messages(db: SQLSession = Depends(get_db_session)):
    from common_lib.modules.agents.models.session_models import (
        AgentMessage,
        AgentConversation,
    )
    from sqlmodel import select
    from sqlalchemy import desc

    query = (
        select(AgentMessage, AgentConversation)
        .join(AgentConversation, AgentMessage.conversation_id == AgentConversation.id)
        .order_by(AgentMessage.created_at.desc())
        .limit(20)
    )
    results = db.exec(query).all()
    return [
        {
            "msg_id": m.id,
            "content": m.content[:50],
            "conv_id": c.id,
            "session_id": c.session_id,
            "created_at": m.created_at,
        }
        for m, c in results
    ]


@router.get("", response_model=List[SessionResponse])
def list_sessions(
    user_id: str = "default",
    pinned: bool = False,
    limit: int = 50,
    offset: int = 0,
    session: SQLSession = Depends(get_db_session),
):
    return svc.list_sessions(
        session, user_id=user_id, pinned=pinned, limit=limit, offset=offset
    )


@router.post("", response_model=SessionResponse)
def create_session(data: SessionCreate, session: SQLSession = Depends(get_db_session)):
    return svc.create_session(session, data)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, session: SQLSession = Depends(get_db_session)):
    try:
        return svc.get_session(session, session_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.patch("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str, data: SessionUpdate, session: SQLSession = Depends(get_db_session)
):
    try:
        return svc.update_session(session, session_id, data)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/{session_id}")
def delete_session(session_id: str, session: SQLSession = Depends(get_db_session)):
    try:
        return svc.delete_session(session, session_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/{session_id}/compact")
def compact_session(
    session_id: str,
    force: bool = False,
    session: SQLSession = Depends(get_db_session),
):
    try:
        return svc.compact_session(session, session_id, force=force)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/prune-empty")
def prune_empty_sessions(session: SQLSession = Depends(get_db_session)):
    return svc.prune_empty_sessions(session)


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
def list_session_messages(
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    session: SQLSession = Depends(get_db_session),
):
    return svc.list_session_messages(session, session_id, limit=limit, offset=offset)


@router.post("/{session_id}/messages", response_model=MessageResponse)
def create_session_message(
    session_id: str,
    data: MessageCreate,
    db: SQLSession = Depends(get_db_session),
):
    return svc.create_session_message(db, session_id, data)


@router.get("/{session_id}/conversations", response_model=List[ConversationResponse])
def list_conversations(session_id: str, session: SQLSession = Depends(get_db_session)):
    try:
        return svc.list_conversations(session, session_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/{session_id}/conversations", response_model=ConversationResponse)
def create_conversation(
    session_id: str,
    data: ConversationCreate,
    session: SQLSession = Depends(get_db_session),
):
    try:
        return svc.create_conversation(session, session_id, data)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get(
    "/conversations/{conversation_id}/messages", response_model=List[MessageResponse]
)
def list_messages(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
    session: SQLSession = Depends(get_db_session),
):
    try:
        return svc.list_messages(session, conversation_id, limit=limit, offset=offset)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageResponse
)
def create_message(
    conversation_id: str,
    data: MessageCreate,
    session: SQLSession = Depends(get_db_session),
):
    try:
        return svc.create_message(session, conversation_id, data)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/messages/{message_id}/tool_calls", response_model=List[ToolCallResponse])
def list_tool_calls(message_id: str, session: SQLSession = Depends(get_db_session)):
    return svc.list_tool_calls(session, message_id)


@router.post("/messages/{message_id}/tool_calls", response_model=ToolCallResponse)
def create_tool_call(
    message_id: str, data: ToolCallCreate, session: SQLSession = Depends(get_db_session)
):
    return svc.create_tool_call(session, message_id, data)


@router.get("/{session_id}/state", response_model=SessionStateResponse)
def get_session_state(session_id: str, session: SQLSession = Depends(get_db_session)):
    try:
        return svc.get_session_state(session, session_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.put("/{session_id}/state", response_model=SessionStateResponse)
def update_session_state(
    session_id: str,
    data: SessionStateUpdate,
    session: SQLSession = Depends(get_db_session),
):
    try:
        return svc.update_session_state(session, session_id, data)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/chat")
async def smart_chat(
    request: SmartChatRequest, session: SQLSession = Depends(get_db_session)
):
    gen = svc.smart_chat(session, request)

    async def sse_wrapper() -> AsyncGenerator[str, None]:
        async for event in gen:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(sse_wrapper(), media_type="text/event-stream")


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    session: SQLSession = Depends(get_db_session),
):
    import os

    UPLOAD_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "uploads",
    )
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    return await svc.upload_file(session, session_id, file, UPLOAD_DIR)


@router.get("/{session_id}/files")
async def list_session_files(
    session_id: str, session: SQLSession = Depends(get_db_session)
):
    try:
        return svc.list_session_files(session, session_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/{session_id}/files/{file_id}")
async def delete_session_file(
    session_id: str, file_id: str, session: SQLSession = Depends(get_db_session)
):
    try:
        return svc.delete_session_file(session, session_id, file_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session or file not found")


@router.post("/evolve")
async def evolve_workflow(
    request: EvolutionFeedbackRequest, session: SQLSession = Depends(get_db_session)
):
    return await svc.evolve_workflow(session, request)
