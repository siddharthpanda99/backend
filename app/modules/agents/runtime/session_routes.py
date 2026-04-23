"""
Session management API for chat history
"""

from typing import List, Optional, Dict, Any
import traceback
from datetime import datetime
from uuid import uuid4
import json
import asyncio
import logging
import re

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select, func, SQLModel
from sqlalchemy import desc
import sqlalchemy as sa

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from app.modules.agents.runtime.session_models import (
    AgentSession,
    AgentConversation,
    AgentMessage,
    AgentToolCall,
    SessionState,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    name: str
    user_id: Optional[str] = "default"
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    engine: Optional[str] = "vllm"
    description: Optional[str] = None
    tags: Optional[List[str]] = []
    metadata: Optional[Dict[str, Any]] = None


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    name: str
    agent_id: Optional[str]
    agent_name: Optional[str]
    model_id: Optional[str]
    model_name: Optional[str]
    engine: Optional[str]
    is_pinned: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_active_at: Optional[datetime]
    message_count: int = 0
    conversation_id: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    thread_id: Optional[str] = None  # LangGraph thread ID for state lookup


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    session_id: str


class ConversationResponse(BaseModel):
    id: str
    session_id: str
    title: Optional[str]
    order_index: int
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime]
    message_count: int = 0


class MessageCreate(BaseModel):
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    role: str  # user, assistant, system
    content: str
    content_html: Optional[str] = None
    reasoning: Optional[str] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    trace_events: Optional[list] = None  # Thought process tree as JSON


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    content_html: Optional[str]
    reasoning: Optional[str]
    model_used: Optional[str]
    tokens_used: Optional[int]
    duration_ms: Optional[int]
    trace_events: Optional[list] = None
    order_index: int
    created_at: datetime


class ToolCallCreate(BaseModel):
    message_id: str
    tool_id: Optional[str] = None
    tool_name: Optional[str] = None
    arguments: Optional[dict] = None
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str = "completed"


class ToolCallResponse(BaseModel):
    id: str
    message_id: str
    tool_id: Optional[str]
    tool_name: Optional[str]
    arguments: Optional[dict]
    result: Optional[str]
    error: Optional[str]
    duration_ms: Optional[int]
    status: str
    created_at: datetime


@router.get("/debug/messages", tags=["Debug"])
def debug_all_messages(db: Session = Depends(get_db_session)):
    """TEMPORARY: Dump most recent messages with link info."""
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


# ---------------------------------------------------------------------------
# Execution Endpoints
# ---------------------------------------------------------------------------


@router.get("/health")
def health_check():
    """Health check for session routes"""
    return {"status": "ok", "message": "Session routes loaded"}


@router.get("", response_model=List[SessionResponse])
def list_sessions(
    user_id: str = "default",
    pinned: bool = False,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_db_session),
):
    """List all sessions for a user."""
    try:
        query = select(AgentSession).where(AgentSession.user_id == user_id)

        if pinned:
            query = query.where(AgentSession.is_pinned == True)

        query = (
            query.order_by(desc(AgentSession.created_at)).offset(offset).limit(limit)
        )

        results = session.exec(query).all()

        response = []
        for s in results:
            # Get message count
            try:
                msg_count = session.exec(
                    select(func.count(AgentMessage.id))
                    .join(AgentConversation)
                    .where(AgentConversation.session_id == s.id)
                ).one()
            except Exception as e:
                logger.warning(f"Failed to get message count for session {s.id}: {e}")
                msg_count = 0

            response.append(
                SessionResponse(
                    id=s.id,
                    user_id=s.user_id,
                    name=s.name,
                    agent_id=s.agent_id,
                    agent_name=s.agent_name,
                    model_id=s.model_id,
                    model_name=s.model_name,
                    engine=s.engine,
                    is_pinned=s.is_pinned,
                    is_active=s.is_active,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                    last_active_at=s.last_active_at,
                    message_count=msg_count or 0,
                )
            )

        return response
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="Database error during session listing"
        )


@router.post("/{session_id}/compact")
def compact_session(
    session_id: str,
    force: bool = False,
    session: Session = Depends(get_db_session),
):
    """Compact session conversation history by generating a summary.

    /compact (default): Cumulative compaction - only compacts new messages since last compaction
    /compact?force=true: Full compaction - compacts entire session history

    Stores summary in session.history and tracks last_compacted_message_id for memoization.
    """
    try:
        agent_session = session.get(AgentSession, session_id)
        if not agent_session:
            raise HTTPException(status_code=404, detail="Session not found")

        conversations = session.exec(
            select(AgentConversation)
            .where(AgentConversation.session_id == session_id)
            .order_by(AgentConversation.order_index)
        ).all()

        if not conversations:
            return {"summary": "No conversations found in session.", "message_count": 0}

        all_messages = []
        for conv in conversations:
            messages = session.exec(
                select(AgentMessage)
                .where(AgentMessage.conversation_id == conv.id)
                .order_by(AgentMessage.order_index)
            ).all()
            all_messages.extend(messages)

        if not all_messages:
            return {"summary": "No messages found in session.", "message_count": 0}

        last_compacted_id = agent_session.last_compacted_message_id
        messages_to_compact = []

        if force:
            messages_to_compact = all_messages
            last_compacted_id = all_messages[-1].id if all_messages else None
        else:
            if last_compacted_id:
                try:
                    last_idx = next(
                        i
                        for i, m in enumerate(all_messages)
                        if m.id == last_compacted_id
                    )
                    messages_to_compact = all_messages[last_idx + 1 :]
                except StopIteration:
                    messages_to_compact = all_messages
            else:
                messages_to_compact = all_messages
                last_compacted_id = all_messages[-1].id if all_messages else None

        message_count = len(messages_to_compact)

        if message_count == 0:
            return {
                "summary": agent_session.summary or "No new messages to compact.",
                "message_count": 0,
                "is_cumulative": True,
            }

        new_conversation_text = ""
        for msg in messages_to_compact:
            role_label = "User" if msg.role == "user" else "Assistant"
            new_conversation_text += (
                f"{role_label}: {msg.content or msg.text or ''}\n\n"
            )

        if force:
            full_text = ""
            for msg in all_messages:
                role_label = "User" if msg.role == "user" else "Assistant"
                full_text += f"{role_label}: {msg.content or msg.text or ''}\n\n"
            summary = _generate_summary(full_text, len(all_messages))
            history = summary
        else:
            existing_summary = agent_session.summary or ""
            existing_history = agent_session.history or ""

            new_summary = _generate_summary(new_conversation_text, message_count)

            if existing_summary:
                combined = f"{existing_summary}\n\n---\n\n{new_summary}"
            else:
                combined = new_summary

            summary = combined
            history = combined

        agent_session.summary = summary
        agent_session.history = history
        agent_session.last_compacted_message_id = last_compacted_id
        session.add(agent_session)
        session.commit()

        return {
            "summary": summary,
            "message_count": message_count,
            "total_messages": len(all_messages),
            "last_compacted_message_id": last_compacted_id,
            "is_cumulative": not force,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to compact session {session_id}: {e}\n{traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to compact session: {str(e)}"
        )


def _generate_summary(conversation_text: str, message_count: int) -> str:
    """Generate a summary of the conversation using the LLM."""
    import requests

    # vLLM endpoint
    vllm_url = "http://localhost:8000"

    # Estimate tokens (rough: 1 token ≈ 4 chars)
    max_input_tokens = 3500  # Leave room for 512+ output tokens, stay under 4096
    truncated_text = conversation_text
    if len(conversation_text) > max_input_tokens * 4:
        # Truncate to fit
        truncated_text = conversation_text[-max_input_tokens * 4 :]
        # Try to start from a clean message boundary
        user_idx = truncated_text.find("User:")
        if user_idx > 100:
            truncated_text = truncated_text[user_idx:]

    # Build summarization prompt
    summary_prompt = f"""Summarize the following conversation history into a concise 2-3 sentence context block. Focus on:
- What the user was trying to accomplish
- Key decisions or outcomes
- Any errors or issues encountered
- Final resolution or next steps

Conversation:
{truncated_text}

Summary:"""

    try:
        # Use OpenAI-compatible vLLM endpoint
        models_resp = requests.get(f"{vllm_url}/v1/models", timeout=5)
        if models_resp.status_code == 200:
            models_data = models_resp.json()
            model_name = "default"
            if "data" in models_data and len(models_data["data"]) > 0:
                model_name = models_data["data"][0]["id"]

            response = requests.post(
                f"{vllm_url}/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": summary_prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3,
                },
                timeout=15,
            )

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    summary = result["choices"][0]["message"]["content"].strip()
                    if summary and len(summary) > 10:
                        return summary
    except Exception as e:
        logger.warning(f"vLLM API call failed: {e}")

    # Fallback to extractive summary
    return _fallback_summary(conversation_text, message_count)


def _fallback_summary(conversation_text: str, message_count: int) -> str:
    """Fallback extractive summary when LLM is not available."""
    lines = conversation_text.strip().split("\n")

    # Extract all user and assistant messages
    user_msgs = []
    assistant_msgs = []

    current_role = None
    current_content = []

    for line in lines:
        if line.startswith("User:"):
            if current_role == "Assistant" and current_content:
                assistant_msgs.append(" ".join(current_content))
            current_role = "User"
            current_content = [line.replace("User:", "").strip()]
        elif line.startswith("Assistant:"):
            if current_role == "User" and current_content:
                user_msgs.append(" ".join(current_content))
            current_role = "Assistant"
            current_content = [line.replace("Assistant:", "").strip()]
        elif line.strip():
            current_content.append(line.strip())

    # Add last message
    if current_role == "User" and current_content:
        user_msgs.append(" ".join(current_content))
    elif current_role == "Assistant" and current_content:
        assistant_msgs.append(" ".join(current_content))

    # Build a more informative summary
    summary_parts = []

    # Detect user intent from first message
    if user_msgs:
        first_msg = user_msgs[0].lower()
        if "pdf" in first_msg or "file" in first_msg or "document" in first_msg:
            summary_parts.append(
                "User tried to process a PDF/file and generate insights"
            )
        elif "analyze" in first_msg:
            summary_parts.append("User wanted to analyze data or a document")
        elif "create" in first_msg or "build" in first_msg:
            summary_parts.append("User wanted to create or build something")
        else:
            summary_parts.append(f"User started with: {user_msgs[0][:40]}...")

    # Look for errors in assistant messages
    error_keywords = [
        "error",
        "failed",
        "can't",
        "cannot",
        "sorry",
        "issue",
        "problem",
        "unable",
        "exception",
    ]
    errors_count = 0
    for msg in assistant_msgs:
        msg_lower = msg.lower()
        for kw in error_keywords:
            if kw in msg_lower:
                errors_count += 1
                break

    if errors_count > 0:
        summary_parts.append(f"Conversation had {errors_count} errors/issues")

    # Check final resolution
    if assistant_msgs:
        last_msg = assistant_msgs[-1].lower()
        if "landing_page_funnel" in last_msg:
            summary_parts.append(
                "Agent recommended landing_page_funnel workflow or custom plan"
            )
        elif "would you like" in last_msg or "proceed with" in last_msg:
            summary_parts.append("Agent asked user to confirm next steps")

    if not summary_parts:
        summary_parts.append(f"{message_count // 2} conversation exchanges")

    return " | ".join(summary_parts)


@router.post("", response_model=SessionResponse)
def create_session(data: SessionCreate, session: Session = Depends(get_db_session)):
    """Create a new session with a default conversation.

    ID format: {agent_name}_{model_name}_{ddmmyyyy}
    Example: pdf_planner_qwen_08042026
    """
    # Generate readable ID: agentname_modelname_ddmmyyyy
    agent_part = (
        (data.agent_name or "agent").lower().replace(" ", "_").replace("-", "_")
    )
    model_part = (
        (data.model_name or "model")
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
    )
    date_part = datetime.now().strftime("%d%m%Y")
    sid = f"{agent_part}_{model_part}_{date_part}"

    # Handle name - use provided name or generate readable one
    name = (
        data.name
        or f"{data.agent_name or 'Agent'} / {data.model_name or 'Model'} / {datetime.now().strftime('%d-%m-%Y')}"
    )

    s = AgentSession(
        id=sid,
        user_id=data.user_id,
        name=name,
        agent_id=data.agent_id,
        agent_name=data.agent_name,
        model_id=data.model_id,
        model_name=data.model_name,
        engine=data.engine,
        description=data.description,
        tags=json.dumps(data.tags) if data.tags else None,
        session_metadata=json.dumps(data.metadata) if data.metadata else None,
        is_pinned=False,
        is_active=True,
    )

    session.add(s)
    session.commit()
    session.refresh(s)

    # Create first conversation automatically
    cid = f"conv_{uuid4().hex[:12]}"
    c = AgentConversation(id=cid, session_id=sid, title="New Chat", order_index=0)
    session.add(c)
    session.commit()

    # Get thread_id from active session if available
    thread_id = None
    try:
        from app.modules.agents.runtime.core.agent_loader import get_active_session

        active_sess = get_active_session()
        if active_sess:
            thread_id = active_sess.get("session_id")
    except Exception:
        pass

    return SessionResponse(
        id=s.id,
        user_id=s.user_id,
        name=s.name,
        agent_id=s.agent_id,
        agent_name=s.agent_name,
        model_id=s.model_id,
        model_name=s.model_name,
        engine=s.engine,
        is_pinned=s.is_pinned,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
        last_active_at=s.last_active_at,
        message_count=0,
        conversation_id=cid,
        description=data.description,
        tags=data.tags or [],
        metadata=data.metadata or {},
        thread_id=thread_id,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, session: Session = Depends(get_db_session)):
    """Get a session by ID."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_count = session.exec(
        select(func.count(AgentMessage.id))
        .join(AgentConversation)
        .where(AgentConversation.session_id == s.id)
    ).one()

    # Get the primary conversation ID
    conversation = session.exec(
        select(AgentConversation.id)
        .where(AgentConversation.session_id == s.id)
        .order_by(AgentConversation.order_index.asc())
    ).first()

    return SessionResponse(
        id=s.id,
        user_id=s.user_id,
        name=s.name,
        agent_id=s.agent_id,
        agent_name=s.agent_name,
        model_id=s.model_id,
        model_name=s.model_name,
        engine=s.engine,
        is_pinned=s.is_pinned,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
        last_active_at=s.last_active_at,
        message_count=msg_count,
        conversation_id=conversation,
        description=s.description,
        tags=json.loads(s.tags) if s.tags else [],
        metadata=json.loads(s.session_metadata) if s.session_metadata else {},
    )


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
def list_session_messages(
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_db_session),
):
    """List all messages in a session across all conversations, paginated."""
    logger.info(
        f"Listing messages for session {session_id} (limit={limit}, offset={offset})"
    )

    # Explicit join for stability
    query = (
        select(AgentMessage)
        .join(AgentConversation, AgentMessage.conversation_id == AgentConversation.id)
        .where(AgentConversation.session_id == session_id)
        .order_by(AgentMessage.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    results = session.exec(query).all()
    logger.info(f"Retrieved {len(results)} messages for session {session_id}")

    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            content_html=m.content_html,
            reasoning=m.reasoning,
            model_used=m.model_used,
            tokens_used=m.tokens_used,
            duration_ms=m.duration_ms,
            trace_events=json.loads(m.trace_events)
            if isinstance(m.trace_events, str)
            else m.trace_events,
            order_index=m.order_index,
            created_at=m.created_at,
        )
        for m in results
    ]


@router.post("/{session_id}/messages", response_model=MessageResponse)
def create_session_message(
    session_id: str,
    data: MessageCreate,
    db: Session = Depends(get_db_session),
):
    """
    Create a message for a session. Autonomously resolves/creates a conversation.
    Fulfills the requirement: 'Only message with session id need to be passed'.
    """
    logger.info(
        f"Creating message for session {session_id}: {data.role} - {data.content[:50]}..."
    )

    # 1. Verify session exists
    s = db.get(AgentSession, session_id)
    if not s:
        logger.warning(f"Session {session_id} not found. Creating default session.")
        s = AgentSession(id=session_id, name=f"Session {session_id[:8]}")
        db.add(s)
        db.commit()
        db.refresh(s)

    # 2. Find or Create latest Conversation
    c = db.exec(
        select(AgentConversation)
        .where(AgentConversation.session_id == session_id)
        .order_by(AgentConversation.created_at.desc())
    ).first()

    if not c:
        logger.info(f"Creating default conversation for session {session_id}")
        cid = f"conv_{uuid4().hex[:12]}"
        c = AgentConversation(
            id=cid, session_id=session_id, title="Session Chat", order_index=0
        )
        db.add(c)
        db.commit()
        db.refresh(c)

    # 3. Create message
    mid = data.id or f"msg_{uuid4().hex[:12]}"

    # Handle trace_events - store as JSON string
    trace_events_str = None
    if data.trace_events:
        trace_events_str = (
            json.dumps(data.trace_events)
            if not isinstance(data.trace_events, str)
            else data.trace_events
        )

    msg = AgentMessage(
        id=mid,
        conversation_id=c.id,
        role=data.role,
        content=data.content,
        content_html=data.content_html,
        reasoning=data.reasoning,
        model_used=data.model_used,
        tokens_used=data.tokens_used,
        duration_ms=data.duration_ms,
        trace_events=trace_events_str,
        order_index=0,
    )

    db.add(msg)
    db.commit()
    db.refresh(msg)

    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        content_html=msg.content_html,
        reasoning=msg.reasoning,
        model_used=msg.model_used,
        tokens_used=msg.tokens_used,
        duration_ms=msg.duration_ms,
        trace_events=json.loads(msg.trace_events)
        if isinstance(msg.trace_events, str)
        else msg.trace_events,
        order_index=msg.order_index,
        created_at=msg.created_at,
    )


@router.patch("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str, data: SessionUpdate, session: Session = Depends(get_db_session)
):
    """Update a session."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if data.name is not None:
        s.name = data.name
    if data.is_pinned is not None:
        s.is_pinned = data.is_pinned
    if data.is_active is not None:
        s.is_active = data.is_active
    if data.description is not None:
        s.description = data.description
    if data.tags is not None:
        s.tags = json.dumps(data.tags) if isinstance(data.tags, list) else data.tags
    if data.metadata is not None:
        s.session_metadata = (
            json.dumps(data.metadata)
            if isinstance(data.metadata, dict)
            else data.metadata
        )

    session.add(s)
    session.commit()
    session.refresh(s)

    msg_count = session.exec(
        select(func.count(AgentMessage.id))
        .join(AgentConversation)
        .where(AgentConversation.session_id == s.id)
    ).one()

    # Parse tags and metadata from JSON strings
    tags = []
    metadata = {}
    try:
        if s.tags:
            tags = json.loads(s.tags) if isinstance(s.tags, str) else s.tags
    except:
        pass
    try:
        if s.session_metadata:
            metadata = (
                json.loads(s.session_metadata)
                if isinstance(s.session_metadata, str)
                else s.session_metadata
            )
    except:
        pass

    # Get the primary conversation ID
    conversation = session.exec(
        select(AgentConversation.id)
        .where(AgentConversation.session_id == s.id)
        .order_by(AgentConversation.order_index.asc())
    ).first()

    return SessionResponse(
        id=s.id,
        user_id=s.user_id,
        name=s.name,
        agent_id=s.agent_id,
        agent_name=s.agent_name,
        model_id=s.model_id,
        model_name=s.model_name,
        engine=s.engine,
        is_pinned=s.is_pinned,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
        last_active_at=s.last_active_at,
        message_count=msg_count or 0,
        conversation_id=conversation,
        description=s.description,
        tags=tags,
        metadata=metadata,
        thread_id=None,
    )


@router.delete("/{session_id}")
def delete_session(session_id: str, session: Session = Depends(get_db_session)):
    """Delete a session and all its conversations/messages."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    session.delete(s)
    session.commit()

    return {"status": "deleted", "id": session_id}


@router.post("/prune-empty", response_model=dict)
def prune_empty_sessions(session: Session = Depends(get_db_session)):
    """Delete all sessions that have no messages."""
    sql = """
        SELECT s.id 
        FROM agent_sessions s
        LEFT JOIN agent_conversations c ON c.session_id = s.id
        LEFT JOIN agent_messages m ON m.conversation_id = c.id
        GROUP BY s.id
        HAVING COUNT(m.id) = 0
    """
    result = session.exec(sa.text(sql)).all()
    deleted_ids = [row[0] for row in result]

    for id in deleted_ids:
        session.exec(sa.text(f"DELETE FROM agent_sessions WHERE id = '{id}'"))
    session.commit()

    logger.info(f"Pruned {len(deleted_ids)} empty sessions")
    return {"deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


# ---------------------------------------------------------------------------
# Conversation Endpoints
# ---------------------------------------------------------------------------


@router.get("/{session_id}/conversations", response_model=List[ConversationResponse])
def list_conversations(session_id: str, session: Session = Depends(get_db_session)):
    """List all conversations in a session."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    query = (
        select(AgentConversation)
        .where(AgentConversation.session_id == session_id)
        .order_by(AgentConversation.order_index)
    )

    results = session.exec(query).all()

    response = []
    for c in results:
        msg_count = session.exec(
            select(func.count(AgentMessage.id)).where(
                AgentMessage.conversation_id == c.id
            )
        ).one()

        response.append(
            ConversationResponse(
                id=c.id,
                session_id=c.session_id,
                title=c.title,
                order_index=c.order_index,
                created_at=c.created_at,
                updated_at=c.updated_at,
                last_message_at=c.last_message_at,
                message_count=msg_count or 0,
            )
        )

    return response


@router.post("/{session_id}/conversations", response_model=ConversationResponse)
def create_conversation(
    session_id: str,
    data: ConversationCreate,
    session: Session = Depends(get_db_session),
):
    """Create a new conversation in a session."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get max order_index
    max_order = (
        session.exec(
            select(func.max(AgentConversation.order_index)).where(
                AgentConversation.session_id == session_id
            )
        ).one()
        or -1
    )

    cid = f"conv_{uuid4().hex[:12]}"

    c = AgentConversation(
        id=cid,
        session_id=session_id,
        title=data.title or "New Chat",
        order_index=max_order + 1,
    )

    session.add(c)
    session.commit()
    session.refresh(c)

    return ConversationResponse(
        id=c.id,
        session_id=c.session_id,
        title=c.title,
        order_index=c.order_index,
        created_at=c.created_at,
        updated_at=c.updated_at,
        last_message_at=c.last_message_at,
        message_count=0,
    )


# ---------------------------------------------------------------------------
# Message Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/conversations/{conversation_id}/messages", response_model=List[MessageResponse]
)
def list_messages(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_db_session),
):
    """List all messages in a conversation."""
    c = session.get(AgentConversation, conversation_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")

    query = (
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conversation_id)
        .order_by(AgentMessage.order_index)
        .offset(offset)
        .limit(limit)
    )

    results = session.exec(query).all()

    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            content_html=m.content_html,
            reasoning=m.reasoning,
            model_used=m.model_used,
            tokens_used=m.tokens_used,
            duration_ms=m.duration_ms,
            trace_events=json.loads(m.trace_events) if m.trace_events else None,
            order_index=m.order_index,
            created_at=m.created_at,
        )
        for m in results
    ]


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageResponse
)
def create_message(
    conversation_id: str,
    data: MessageCreate,
    session: Session = Depends(get_db_session),
):
    """Create a new message."""
    logger.info(
        f"Creating message in conversation {conversation_id}: {data.role} - {data.content[:50]}..."
    )
    c = session.get(AgentConversation, conversation_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get max order_index
    max_order = (
        session.exec(
            select(func.max(AgentMessage.order_index)).where(
                AgentMessage.conversation_id == conversation_id
            )
        ).one()
        or -1
    )

    mid = f"msg_{uuid4().hex[:12]}"

    m = AgentMessage(
        id=mid,
        conversation_id=conversation_id,
        role=data.role,
        content=data.content,
        content_html=data.content_html,
        reasoning=data.reasoning,
        model_used=data.model_used,
        tokens_used=data.tokens_used,
        duration_ms=data.duration_ms,
        trace_events=json.dumps(data.trace_events) if data.trace_events else None,
        order_index=max_order + 1,
    )

    session.add(m)
    session.commit()
    session.refresh(m)

    # Update conversation last_message_at
    c.last_message_at = m.created_at
    session.add(c)
    session.commit()

    # Update session last_active_at
    s = session.get(AgentSession, c.session_id)
    if s:
        s.last_active_at = m.created_at
        session.add(s)
        session.commit()

    return MessageResponse(
        id=m.id,
        conversation_id=m.conversation_id,
        role=m.role,
        content=m.content,
        content_html=m.content_html,
        reasoning=m.reasoning,
        model_used=m.model_used,
        tokens_used=m.tokens_used,
        duration_ms=m.duration_ms,
        trace_events=json.loads(m.trace_events) if m.trace_events else None,
        order_index=m.order_index,
        created_at=m.created_at,
    )


# ---------------------------------------------------------------------------
# Tool Call Endpoints
# ---------------------------------------------------------------------------


@router.get("/messages/{message_id}/tool_calls", response_model=List[ToolCallResponse])
def list_tool_calls(message_id: str, session: Session = Depends(get_db_session)):
    """List all tool calls for a message."""
    query = select(AgentToolCall).where(AgentToolCall.message_id == message_id)
    results = session.exec(query).all()

    return [
        ToolCallResponse(
            id=t.id,
            message_id=t.message_id,
            tool_id=t.tool_id,
            tool_name=t.tool_name,
            arguments=t.arguments,
            result=t.result,
            error=t.error,
            duration_ms=t.duration_ms,
            status=t.status,
            created_at=t.created_at,
        )
        for t in results
    ]


@router.post("/messages/{message_id}/tool_calls", response_model=ToolCallResponse)
def create_tool_call(
    message_id: str, data: ToolCallCreate, session: Session = Depends(get_db_session)
):
    """Create a new tool call."""
    tid = f"tool_{uuid4().hex[:12]}"

    t = AgentToolCall(
        id=tid,
        message_id=message_id,
        tool_id=data.tool_id,
        tool_name=data.tool_name,
        arguments=data.arguments,
        result=data.result,
        error=data.error,
        duration_ms=data.duration_ms,
        status=data.status,
    )

    session.add(t)
    session.commit()
    session.refresh(t)

    return ToolCallResponse(
        id=t.id,
        message_id=t.message_id,
        tool_id=t.tool_id,
        tool_name=t.tool_name,
        arguments=t.arguments,
        result=t.result,
        error=t.error,
        duration_ms=t.duration_ms,
        status=t.status,
        created_at=t.created_at,
    )


# ---------------------------------------------------------------------------
# Database Models are imported from session_models
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Session State Endpoints
# ---------------------------------------------------------------------------


class SessionStateUpdate(BaseModel):
    current_step: Optional[str] = None
    progress: Optional[float] = None
    status: Optional[str] = None
    state_variables: Optional[dict] = None
    hints: Optional[list] = None
    facts: Optional[list] = None
    user_preferences: Optional[dict] = None
    plan_id: Optional[str] = None
    workflow_id: Optional[str] = None


class SessionStateResponse(BaseModel):
    id: str
    session_id: str
    plan_id: Optional[str]
    workflow_id: Optional[str]
    current_step: Optional[str]
    progress: float
    status: str
    state_variables: Optional[dict]
    hints: Optional[list]
    facts: Optional[list]
    user_preferences: Optional[dict]
    artifacts: Optional[list]
    metrics: Optional[dict]
    success_count: int
    failure_count: int
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@router.get("/{session_id}/state", response_model=SessionStateResponse)
def get_session_state(session_id: str, session: Session = Depends(get_db_session)):
    """Get current execution state for a session."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    state = session.exec(
        select(SessionState).where(SessionState.session_id == session_id)
    ).first()

    if not state:
        # Create default state
        state = SessionState(
            id=f"state_{session_id}",
            session_id=session_id,
            current_step=s.current_step or "idle",
            progress=s.progress or 0.0,
            status="idle",
        )
        session.add(state)
        session.commit()
        session.refresh(state)

    return SessionStateResponse(
        id=state.id,
        session_id=state.session_id,
        plan_id=state.plan_id,
        workflow_id=state.workflow_id,
        current_step=state.current_step,
        progress=state.progress,
        status=state.status,
        state_variables=json.loads(state.state_variables)
        if state.state_variables
        else {},
        hints=json.loads(state.hints) if state.hints else [],
        facts=json.loads(state.facts) if state.facts else [],
        user_preferences=json.loads(state.user_preferences)
        if state.user_preferences
        else {},
        artifacts=json.loads(state.artifacts) if state.artifacts else [],
        metrics=json.loads(state.metrics) if state.metrics else {},
        success_count=state.success_count,
        failure_count=state.failure_count,
        summary=s.summary,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


@router.put("/{session_id}/state", response_model=SessionStateResponse)
def update_session_state(
    session_id: str,
    data: SessionStateUpdate,
    session: Session = Depends(get_db_session),
):
    """Update execution state for a session."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    state = session.exec(
        select(SessionState).where(SessionState.session_id == session_id)
    ).first()

    if not state:
        state = SessionState(
            id=f"state_{session_id}",
            session_id=session_id,
        )
        session.add(state)

    # Update fields
    if data.current_step is not None:
        state.current_step = data.current_step
        s.current_step = data.current_step
    if data.progress is not None:
        state.progress = data.progress
        s.progress = data.progress
    if data.status is not None:
        state.status = data.status
    if data.state_variables is not None:
        state.state_variables = json.dumps(data.state_variables)
        s.state_variables = json.dumps(data.state_variables)
    if data.hints is not None:
        state.hints = json.dumps(data.hints)
        s.hints = json.dumps(data.hints)
    if data.facts is not None:
        state.facts = json.dumps(data.facts)
        s.facts = json.dumps(data.facts)
    if data.user_preferences is not None:
        state.user_preferences = json.dumps(data.user_preferences)
    if data.plan_id is not None:
        state.plan_id = data.plan_id
        s.execution_plan_id = data.plan_id
    if data.workflow_id is not None:
        state.workflow_id = data.workflow_id

    state.updated_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()

    session.add(state)
    session.add(s)
    session.commit()
    session.refresh(state)

    return SessionStateResponse(
        id=state.id,
        session_id=state.session_id,
        plan_id=state.plan_id,
        workflow_id=state.workflow_id,
        current_step=state.current_step,
        progress=state.progress,
        status=state.status,
        state_variables=json.loads(state.state_variables)
        if state.state_variables
        else {},
        hints=json.loads(state.hints) if state.hints else [],
        facts=json.loads(state.facts) if state.facts else [],
        user_preferences=json.loads(state.user_preferences)
        if state.user_preferences
        else {},
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


# ---------------------------------------------------------------------------
# Execution Plan Endpoints
# ---------------------------------------------------------------------------


class ExecutePlanRequest(BaseModel):
    session_id: str
    workflow_id: str
    inputs: Dict[str, Any] = {}


class SmartChatRequest(BaseModel):
    session_id: str
    message: str
    conversation_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Intent Detection
# ---------------------------------------------------------------------------

SIMPLE_INTENTS = {
    "greeting": re.compile(
        r"\b(hi|hello|hey|greetings|good morning|good afternoon|good evening|howdy|sup|yo)\b",
        re.I,
    ),
    "thanks": re.compile(r"\b(thanks|thank you|thx|ty|appreciate)\b", re.I),
    "farewell": re.compile(r"\b(bye|goodbye|see you|later|cya|take care)\b", re.I),
    "status": re.compile(
        r"\b(how are you|what\'s up|what is up|how\'s it going|how do you do)\b", re.I
    ),
    "help": re.compile(
        r"\b(help|what can you do|capabilities|features|commands)\b", re.I
    ),
}

COMPLEX_INTENTS = {
    "pdf_processing": re.compile(
        r"\b(pdf|document|file.*process|extract.*text|analyze.*pdf|read.*pdf|pdf.*file)\b",
        re.I,
    ),
    "data_analysis": re.compile(
        r"\b(analyz|data|dataset|csv|excel|spreadsheet|statistic|chart|graph)\b", re.I
    ),
    "code_task": re.compile(
        r"\b(code|program|script|function|debug|refactor|implement|api|build)\b", re.I
    ),
    "research": re.compile(
        r"\b(research|search|find.*info|look.*up|investigate|study|survey)\b", re.I
    ),
    "image_task": re.compile(
        r"\b(image|photo|picture|generate.*image|visual|design|create.*image)\b", re.I
    ),
    "text_task": re.compile(
        r"\b(summariz|write|translate|edit|content|text.*process|rewrite)\b", re.I
    ),
}


def detect_intent(message: str) -> Dict[str, Any]:
    """Detect user intent and classify as simple or complex."""
    msg = message.strip()

    # Check simple intents
    for intent, pattern in SIMPLE_INTENTS.items():
        if pattern.search(msg):
            return {"type": "simple", "intent": intent, "requires_planning": False}

    # Check complex intents
    best_match = None
    best_score = 0
    for intent, pattern in COMPLEX_INTENTS.items():
        matches = len(pattern.findall(msg))
        if matches > best_score:
            best_score = matches
            best_match = intent

    if best_match and best_score > 0:
        return {
            "type": "complex",
            "intent": best_match,
            "requires_planning": True,
            "confidence": min(1.0, best_score * 0.5),
        }

    # Default: treat as complex if message is substantive
    word_count = len(msg.split())
    if word_count >= 5:
        return {
            "type": "complex",
            "intent": "general",
            "requires_planning": True,
            "confidence": 0.3,
        }

    return {"type": "simple", "intent": "general", "requires_planning": False}


# ---------------------------------------------------------------------------
# Smart Chat Endpoint (Intent Detection + Routing)
# ---------------------------------------------------------------------------


@router.post("/chat")
async def smart_chat(
    request: SmartChatRequest, session: Session = Depends(get_db_session)
):
    """
    Smart chat endpoint with intent detection.
    - Simple intents → direct LLM response
    - Complex intents → planner agent → workflow execution
    """
    s = session.get(AgentSession, request.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    intent = detect_intent(request.message)

    async def event_generator():
        loop = asyncio.get_event_loop()
        event_queue = asyncio.Queue()

        def emit(event_type: str, data: Dict[str, Any]):
            event = {
                "event_type": event_type,
                "ts": datetime.utcnow().isoformat(),
                **data,
            }
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        def run_routing():
            try:
                emit("intent_detected", intent)

                if not intent["requires_planning"]:
                    # Simple intent → direct response
                    emit(
                        "direct_response",
                        {
                            "intent": intent["intent"],
                            "message": f"Detected: {intent['intent']}. Processing directly.",
                        },
                    )
                else:
                    # Complex intent → find matching workflow
                    emit("planning_started", {"intent": intent["intent"]})

                    from common_lib.modules.orchestration.agents.agent.execution.workflow_matcher import (
                        WorkflowMatcher,
                    )

                    matcher = WorkflowMatcher()
                    matches = matcher.find_matches(
                        user_request=request.message,
                        domain=intent["intent"].split("_")[0]
                        if "_" in intent["intent"]
                        else None,
                    )

                    emit(
                        "workflows_found",
                        {
                            "count": len(matches),
                            "matches": [
                                {
                                    "id": m.workflow_id,
                                    "name": m.name,
                                    "score": m.score,
                                    "type": m.match_type,
                                }
                                for m in matches[:3]
                            ],
                        },
                    )

                    if matches and matches[0].score >= 0.5:
                        best = matches[0]
                        emit(
                            "workflow_selected",
                            {
                                "workflow_id": best.workflow_id,
                                "name": best.name,
                                "score": best.score,
                                "match_type": best.match_type,
                                "adaptation_notes": best.adaptation_notes,
                            },
                        )

                        # Initialize state for execution
                        state = session.exec(
                            select(SessionState).where(
                                SessionState.session_id == request.session_id
                            )
                        ).first()
                        if not state:
                            state = SessionState(
                                id=f"state_{request.session_id}",
                                session_id=request.session_id,
                                plan_id=best.workflow_id,
                                workflow_id=best.workflow_id,
                                current_step="planning",
                                progress=0.0,
                                status="awaiting_confirmation",
                                state_variables=json.dumps(
                                    {"user_request": request.message, "intent": intent}
                                ),
                                hints=json.dumps([]),
                                facts=json.dumps([]),
                            )
                            session.add(state)
                        else:
                            state.plan_id = best.workflow_id
                            state.workflow_id = best.workflow_id
                            state.current_step = "planning"
                            state.progress = 0.0
                            state.status = "awaiting_confirmation"
                            state.state_variables = json.dumps(
                                {"user_request": request.message, "intent": intent}
                            )
                            state.updated_at = datetime.utcnow()

                        s.current_step = "planning"
                        s.progress = 0.0
                        s.execution_plan_id = best.workflow_id
                        s.updated_at = datetime.utcnow()
                        session.commit()

                        emit(
                            "plan_ready",
                            {
                                "workflow_id": best.workflow_id,
                                "status": "awaiting_confirmation",
                                "message": f"Plan ready: {best.name} ({best.match_type} match, {best.score:.0%} confidence). Ready to execute.",
                            },
                        )
                    else:
                        emit(
                            "no_workflow_match",
                            {
                                "message": "No matching workflow found. Creating new plan...",
                                "intent": intent["intent"],
                            },
                        )

            except Exception as e:
                logger.error(f"[SmartChat] Routing failed: {e}", exc_info=True)
                emit("error", {"message": str(e)})

        await loop.run_in_executor(None, run_routing)
        await event_queue.put_nowait({"event_type": "DONE"})

        while True:
            event = await event_queue.get()
            if event.get("event_type") == "DONE":
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# File Upload Endpoint
# ---------------------------------------------------------------------------

import os
import shutil
from fastapi import UploadFile, File


UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "uploads",
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    path: str
    size: int
    content_type: str
    session_id: str


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
):
    """Upload a file for session processing."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    # Create session-specific upload dir
    session_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    # Sanitize filename
    safe_name = re.sub(r"[^\w\.\-]", "_", file.filename or "uploaded_file")
    file_id = f"file_{uuid4().hex[:8]}"
    ext = os.path.splitext(safe_name)[1]
    final_name = f"{file_id}{ext}"
    file_path = os.path.join(session_dir, final_name)

    # Save file
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Update session state with file info
    state = session.exec(
        select(SessionState).where(SessionState.session_id == session_id)
    ).first()
    if state and state.state_variables:
        vars_dict = json.loads(state.state_variables)
        vars_dict.setdefault("uploaded_files", [])

        vars_dict["uploaded_files"].append(
            {
                "file_id": file_id,
                "filename": safe_name,
                "path": file_path,
                "size": len(content),
                "content_type": file.content_type or "application/octet-stream",
            }
        )
        state.state_variables = json.dumps(vars_dict)
        state.updated_at = datetime.utcnow()
        session.add(state)
        session.commit()

    return FileUploadResponse(
        file_id=file_id,
        filename=safe_name,
        path=file_path,
        size=len(content),
        content_type=file.content_type or "application/octet-stream",
        session_id=session_id,
    )


@router.get("/{session_id}/files")
async def list_session_files(
    session_id: str, session: Session = Depends(get_db_session)
):
    """List all uploaded files for a session."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    state = session.exec(
        select(SessionState).where(SessionState.session_id == session_id)
    ).first()

    files = []
    if state and state.state_variables:
        vars_dict = json.loads(state.state_variables)
        files = vars_dict.get("uploaded_files", [])

    return {"session_id": session_id, "files": files}


@router.delete("/{session_id}/files/{file_id}")
async def delete_session_file(
    session_id: str, file_id: str, session: Session = Depends(get_db_session)
):
    """Delete an uploaded file for a session."""
    s = session.get(AgentSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    state = session.exec(
        select(SessionState).where(SessionState.session_id == session_id)
    ).first()

    if not state or not state.state_variables:
        raise HTTPException(status_code=404, detail="No files found for session")

    vars_dict = json.loads(state.state_variables)
    files = vars_dict.get("uploaded_files", [])
    file_entry = next((f for f in files if f["file_id"] == file_id), None)

    if not file_entry:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")

    # Delete physical file
    if os.path.exists(file_entry["path"]):
        os.remove(file_entry["path"])

    # Remove from state
    vars_dict["uploaded_files"] = [f for f in files if f["file_id"] != file_id]
    state.state_variables = json.dumps(vars_dict)
    state.updated_at = datetime.utcnow()
    session.add(state)
    session.commit()

    return {"success": True, "file_id": file_id}


# ---------------------------------------------------------------------------
# Self-Evolution Feedback Endpoint
# ---------------------------------------------------------------------------


class EvolutionFeedbackRequest(BaseModel):
    session_id: str
    workflow_id: str
    outcome: str  # success, partial, failed
    user_feedback: Optional[Dict[str, Any]] = None


@router.post("/evolve")
async def evolve_workflow(
    request: EvolutionFeedbackRequest, session: Session = Depends(get_db_session)
):
    """Update workflow similarity weights based on execution outcome."""
    from common_lib.modules.orchestration.agents.agent.execution.workflow_matcher import (
        WorkflowMatcher,
    )

    matcher = WorkflowMatcher()
    result = matcher.update_similarity_weights(
        workflow_id=request.workflow_id,
        outcome=request.outcome,
        user_feedback=request.user_feedback,
    )

    # Update session state
    state = session.exec(
        select(SessionState).where(SessionState.session_id == request.session_id)
    ).first()
    if state:
        state.status = request.outcome
        state.updated_at = datetime.utcnow()
        session.add(state)
        session.commit()

    return result


# ---------------------------------------------------------------------------
# Execution Plan Endpoints (continued)
# ---------------------------------------------------------------------------
async def execute_plan(
    request: ExecutePlanRequest, session: Session = Depends(get_db_session)
):
    """Execute a workflow plan via EntityExecutor with SSE streaming."""
    s = session.get(AgentSession, request.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    from common_lib.modules.orchestration.agents.agent.execution.workflow_matcher import (
        WorkflowMatcher,
    )

    matcher = WorkflowMatcher()
    wf = matcher.get_workflow_by_id(request.workflow_id)
    if not wf:
        raise HTTPException(
            status_code=404, detail=f"Workflow not found: {request.workflow_id}"
        )

    state = session.exec(
        select(SessionState).where(SessionState.session_id == request.session_id)
    ).first()
    if not state:
        state = SessionState(
            id=f"state_{request.session_id}",
            session_id=request.session_id,
            plan_id=request.workflow_id,
            workflow_id=request.workflow_id,
            current_step="initializing",
            progress=0.0,
            status="executing",
            state_variables=json.dumps({}),
            hints=json.dumps([]),
            facts=json.dumps([]),
        )
        session.add(state)
    else:
        state.plan_id = request.workflow_id
        state.workflow_id = request.workflow_id
        state.current_step = "initializing"
        state.progress = 0.0
        state.status = "executing"
        state.updated_at = datetime.utcnow()
    s.current_step = "initializing"
    s.progress = 0.0
    s.updated_at = datetime.utcnow()
    session.commit()

    async def event_generator():
        loop = asyncio.get_event_loop()
        event_queue = asyncio.Queue()

        def emit(event_type: str, data: Dict[str, Any]):
            event = {
                "event_type": event_type,
                "ts": datetime.utcnow().isoformat(),
                **data,
            }
            loop.call_soon_threadsafe(event_queue.put_nowait, event)

        def run_execution():
            try:
                from common_lib.modules.orchestration.entity_executor import (
                    EntityExecutor,
                    ExecutionContext,
                )

                emit("plan_started", {"workflow_id": request.workflow_id})

                steps = wf.get("steps", [])
                if not steps:
                    emit("error", {"message": "Workflow has no steps"})
                    return

                executor_steps = []
                for step in steps:
                    if not isinstance(step, dict):
                        continue
                    step_dict = {
                        "id": step.get("id", f"step_{len(executor_steps)}"),
                        "entity_type": step.get("entity_type", "tool"),
                        "entity_id": step.get(
                            "entity_id", step.get("tool_id", step.get("agent_id", ""))
                        ),
                        "input": step.get("input", {}),
                    }
                    output_schema = step.get("output", {}).get("schema")
                    if output_schema:
                        step_dict["output_schema"] = output_schema
                    executor_steps.append(step_dict)

                ctx = ExecutionContext(
                    session_id=request.session_id,
                    thread_id=request.session_id,
                )

                executor = EntityExecutor()

                for i, step_def in enumerate(executor_steps):
                    step_id = step_def["id"]
                    emit(
                        "step_started",
                        {"step_id": step_id, "entity_id": step_def["entity_id"]},
                    )

                    progress_val = ((i + 1) / len(executor_steps)) * 100
                    session.execute(
                        "UPDATE session_states SET current_step = :step, progress = :progress WHERE session_id = :sid",
                        {
                            "step": step_id,
                            "progress": progress_val,
                            "sid": request.session_id,
                        },
                    )
                    session.execute(
                        "UPDATE agent_sessions SET current_step = :step, progress = :progress WHERE id = :sid",
                        {
                            "step": step_id,
                            "progress": progress_val,
                            "sid": request.session_id,
                        },
                    )
                    session.commit()

                    result = executor.execute(
                        entity_type=step_def["entity_type"],
                        entity_id=step_def["entity_id"],
                        inputs=step_def.get("input", {}),
                        context=ctx,
                        target_schema=step_def.get("output_schema"),
                    )

                    if result.status == "success":
                        emit(
                            "step_completed", {"step_id": step_id, "data": result.data}
                        )
                        for hint in result.hints:
                            emit("hint", hint)
                        for fact in result.facts:
                            emit("fact", fact)
                    else:
                        emit("step_failed", {"step_id": step_id, "error": result.error})

                session.execute(
                    "UPDATE session_states SET status = :status, progress = 100.0, current_step = 'completed' WHERE session_id = :sid",
                    {"status": "completed", "sid": request.session_id},
                )
                session.execute(
                    "UPDATE agent_sessions SET current_step = 'completed', progress = 100.0 WHERE id = :sid",
                    {"sid": request.session_id},
                )
                session.commit()

                emit("plan_completed", {"workflow_id": request.workflow_id})

            except Exception as e:
                logger.error(f"[ExecutePlan] Execution failed: {e}", exc_info=True)
                session.execute(
                    "UPDATE session_states SET status = :status WHERE session_id = :sid",
                    {"status": "failed", "sid": request.session_id},
                )
                session.commit()
                emit("error", {"message": str(e)})

        await loop.run_in_executor(None, run_execution)
        await event_queue.put_nowait({"event_type": "DONE"})

        while True:
            event = await event_queue.get()
            if event.get("event_type") == "DONE":
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
