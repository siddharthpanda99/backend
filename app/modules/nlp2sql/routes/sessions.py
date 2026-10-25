"""nlp2sql sessions + ask routes — thin transport (G1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.modules.nlp2sql.routes import _shared as shared
from common_lib.modules.nlp2sql.schemas import ChatMessageCreate
from common_lib.modules.nlp2sql.schemas import SessionCreate
from common_lib.modules.nlp2sql.schemas import SessionRead

router = APIRouter(prefix="/data-intelligence/sessions", tags=["NLP-to-SQL — Sessions"])


class MessageBody(ChatMessageCreate):
    """Ask body — imports the source contract (G10) and adds route fields.

    ``connection_id`` comes from ``ChatMessageCreate`` but ``ask_question``
    accepts no connection id (service gap, documented — the field is accepted
    additively and ignored rather than rejected).
    """

    role: str = "analyst"
    auto_execute: bool = False
    catalog_objects: list[dict[str, Any]] = []


@router.post("", status_code=201, response_model=SessionRead)
@router.post("/", status_code=201, response_model=SessionRead, include_in_schema=False)
async def create_session_route(payload: SessionCreate) -> dict:
    try:
        from common_lib.modules.nlp2sql import service

        return service.create_session(
            payload.workspace_id, payload.connection_id, payload.title
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("", response_model=dict)
@router.get("/", response_model=dict, include_in_schema=False)
async def list_sessions_route(workspace_id: str = "default") -> dict:
    """Session list (UI ``listSessions``) — workspace-scoped.

    Backed by ``service.list_sessions`` (in-memory registry read); unknown or
    empty workspaces return ``{"sessions": []}``. ``response_model`` stays
    ``dict`` (declared contract); each row carries the ``SessionRead`` shape.
    """
    try:
        from common_lib.modules.nlp2sql import service

        return {"sessions": service.list_sessions(workspace_id)}
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/{session_id}/messages", response_model=dict)
async def post_message_route(session_id: str, payload: MessageBody) -> dict:
    try:
        from common_lib.modules.nlp2sql import service

        return service.ask_question(
            session_id,
            payload.content,
            role=payload.role,
            catalog_objects=payload.catalog_objects,
            auto_execute=payload.auto_execute,
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.get("/{session_id}/messages", response_model=dict)
async def list_messages_route(session_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql import service

        return {"messages": service.session_messages(session_id)}
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise
