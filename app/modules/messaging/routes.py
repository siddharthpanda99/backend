"""Messaging Gateway — API routes.

Provides a unified endpoint for agents and systems to send messages
across multiple channels (notification, slack, email, webhook, log).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from common_lib.modules.notification.messaging import (
    get_messaging_gateway,
    MessageChannel,
    MessagePriority,
)

router = APIRouter(prefix="/messaging", tags=["Messaging Gateway"])


# ── Schemas ─────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    channel: str = Field(description="Target channel: notification, slack, email, webhook, log")
    recipient: str = Field(description="Channel-specific recipient (user ID, Slack channel, email address, webhook URL)")
    subject: str = Field(description="Message subject / title")
    body: str = Field(description="Message body content")
    priority: str = Field(default="normal", description="Priority: low, normal, high, critical")
    source: str = Field(default="", description="Source system or component name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional structured metadata")


class SendMessageResponse(BaseModel):
    success: bool
    channel: str
    message_id: str = ""
    error: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None


class ChannelInfo(BaseModel):
    id: str
    name: str
    description: str
    requires_config: bool
    config_hint: str = ""


class ListChannelsResponse(BaseModel):
    channels: List[ChannelInfo]


# ── Routes ─────────────────────────────────────────────────────────────

@router.post("/send", response_model=SendMessageResponse)
async def send_message(req: SendMessageRequest):
    """Send a message through the specified channel.

    The gateway routes to the appropriate provider based on the channel field.
    """
    try:
        channel = MessageChannel(req.channel)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel '{req.channel}'. Supported: {[c.value for c in MessageChannel]}",
        )

    try:
        priority = MessagePriority(req.priority)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority '{req.priority}'. Supported: {[p.value for p in MessagePriority]}",
        )

    gateway = get_messaging_gateway()
    result = await gateway.send(
        channel=channel,
        recipient=req.recipient,
        subject=req.subject,
        body=req.body,
        priority=priority,
        metadata=req.metadata,
        source=req.source,
    )

    return SendMessageResponse(
        success=result.success,
        channel=result.channel.value,
        message_id=result.message_id,
        error=result.error,
        provider_response=result.provider_response,
    )


@router.get("/channels", response_model=ListChannelsResponse)
async def list_channels():
    """List all available messaging channels with descriptions."""
    gateway = get_messaging_gateway()
    return ListChannelsResponse(channels=gateway.get_channels())


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_history(limit: int = 50):
    """Get recent message dispatch history."""
    gateway = get_messaging_gateway()
    return gateway.get_history()[-limit:]
