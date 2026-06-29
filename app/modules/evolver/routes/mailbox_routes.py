"""Evolver Mailbox routes — proxy mailbox for async tool execution."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from app.modules.common.types.index import APIResponse

router = APIRouter(prefix="/mailbox", tags=["Evolver Mailbox"])


class MailboxPostRequest(BaseModel):
    message_type: str = "tool_execution"
    source: str = ""
    target: str = ""
    payload: Dict[str, Any] = {}
    priority: str = "normal"
    ttl_seconds: int = 3600
    sign: bool = False


class MailboxStatusUpdate(BaseModel):
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("", response_model=APIResponse[Dict[str, Any]])
async def post_message(req: MailboxPostRequest):
    """Post a new message to the proxy mailbox."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver import (
            get_mailbox_service,
            MessagePriority,
        )

        mbox = get_mailbox_service()
        msg = mbox.post(
            type=req.message_type,
            payload=req.payload,
            source=req.source,
            target=req.target,
            priority=MessagePriority(req.priority),
            ttl_seconds=req.ttl_seconds,
            sign=req.sign,
        )
        return APIResponse(
            data={"message_id": msg.id, "status": msg.status.value},
            message="Message posted",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending", response_model=APIResponse[List[Dict[str, Any]]])
async def poll_pending(
    message_type: Optional[str] = None,
    limit: int = 10,
):
    """Poll for pending messages."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver import (
            get_mailbox_service,
            MessageStatus,
        )

        mbox = get_mailbox_service()
        msgs = mbox.poll(
            status=MessageStatus.PENDING,
            type=message_type,
            limit=limit,
        )
        return APIResponse(
            data=[{"id": m.id, "type": m.type, "payload": m.payload} for m in msgs],
            message=f"Found {len(msgs)} pending messages",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{message_id}", response_model=APIResponse)
async def update_message_status(message_id: str, req: MailboxStatusUpdate):
    """Acknowledge or fail a message."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver import (
            get_mailbox_service,
        )

        mbox = get_mailbox_service()
        if req.status == "completed":
            mbox.ack(message_id, result=req.result)
        elif req.status == "failed":
            mbox.nack(message_id, error=req.error or "Unknown error")
        else:
            raise HTTPException(status_code=400, detail=f"Invalid status: {req.status}")
        return APIResponse(
            data=None, message=f"Message {message_id} updated to {req.status}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
async def get_mailbox_stats():
    """Get mailbox statistics."""
    try:
        from common_lib.modules.knowledge_engine.learning.evolver import (
            get_mailbox_service,
        )

        mbox = get_mailbox_service()
        stats = mbox.get_stats()
        return APIResponse(data=stats, message="Mailbox stats retrieved")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
