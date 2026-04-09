"""
Session database models for chat history
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import Text
from sqlalchemy import JSON


class AgentSession(SQLModel, table=True):
    """Session table - stores chat sessions"""

    __tablename__ = "agent_sessions"

    id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(default="default", max_length=64, index=True)
    name: str = Field(max_length=256)

    agent_id: Optional[str] = Field(default=None, max_length=64)
    agent_name: Optional[str] = Field(default=None, max_length=256)
    model_id: Optional[str] = Field(default=None, max_length=128)
    model_name: Optional[str] = Field(default=None, max_length=256)
    engine: Optional[str] = Field(default="vllm", max_length=64)
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    history: Optional[str] = Field(
        default=None, sa_column=Column(Text)
    )  # Compiled conversation history
    last_compacted_message_id: Optional[str] = Field(
        default=None, max_length=64
    )  # Last message ID that was compacted

    # User-editable metadata
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    tags: Optional[str] = Field(
        default=None, sa_column=Column(JSON)
    )  # Store as JSON array
    session_metadata: Optional[str] = Field(
        default=None, sa_column=Column(JSON)
    )  # Store as JSON dict (renamed from metadata - reserved word)

    # Execution state fields
    current_step: Optional[str] = Field(default=None, max_length=256)
    progress: Optional[float] = Field(default=None)
    state_variables: Optional[str] = Field(default=None)  # JSON dict
    hints: Optional[str] = Field(default=None)  # JSON array
    facts: Optional[str] = Field(default=None)  # JSON array
    execution_plan_id: Optional[str] = Field(default=None, max_length=256)

    is_pinned: bool = Field(default=False)
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_active_at: Optional[datetime] = None

    # Relationships
    conversations: list["AgentConversation"] = Relationship(
        back_populates="session", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    state: Optional["SessionState"] = Relationship(
        back_populates="session", sa_relationship_kwargs={"cascade": "all, delete"}
    )


class AgentConversation(SQLModel, table=True):
    """Conversation table - stores individual chat threads"""

    __tablename__ = "agent_conversations"

    id: str = Field(primary_key=True, max_length=64)
    session_id: str = Field(
        max_length=64, foreign_key="agent_sessions.id", ondelete="CASCADE"
    )
    title: Optional[str] = Field(default=None, max_length=512)
    order_index: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_at: Optional[datetime] = None

    # Relationships
    session: AgentSession = Relationship(back_populates="conversations")
    messages: list["AgentMessage"] = Relationship(
        back_populates="conversation", sa_relationship_kwargs={"cascade": "all, delete"}
    )


class AgentMessage(SQLModel, table=True):
    """Message table - stores individual messages"""

    __tablename__ = "agent_messages"

    id: str = Field(primary_key=True, max_length=64)
    conversation_id: str = Field(
        max_length=64, foreign_key="agent_conversations.id", ondelete="CASCADE"
    )
    role: str = Field(max_length=32)  # user, assistant, system
    content: str = Field()
    content_html: Optional[str] = None
    reasoning: Optional[str] = None

    model_used: Optional[str] = Field(default=None, max_length=256)
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    trace_events: Optional[str] = Field(default=None)  # JSON array of trace entries

    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    conversation: AgentConversation = Relationship(back_populates="messages")
    tool_calls: list["AgentToolCall"] = Relationship(
        back_populates="message", sa_relationship_kwargs={"cascade": "all, delete"}
    )


class AgentToolCall(SQLModel, table=True):
    """Tool call table - stores tool invocations"""

    __tablename__ = "agent_tool_calls"

    id: str = Field(primary_key=True, max_length=64)
    message_id: str = Field(
        max_length=64, foreign_key="agent_messages.id", ondelete="CASCADE"
    )

    tool_id: Optional[str] = Field(default=None, max_length=128)
    tool_name: Optional[str] = Field(default=None, max_length=256)
    arguments: Optional[str] = Field(default=None)  # JSON string
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str = Field(default="completed", max_length=32)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    message: AgentMessage = Relationship(back_populates="tool_calls")


class SessionState(SQLModel, table=True):
    """Live execution state table - tracks running plan progress, variables, hints, facts."""

    __tablename__ = "session_states"

    id: str = Field(primary_key=True, max_length=64)
    session_id: str = Field(
        max_length=64, foreign_key="agent_sessions.id", ondelete="CASCADE", unique=True
    )

    # Plan tracking
    plan_id: Optional[str] = Field(default=None, max_length=256)
    workflow_id: Optional[str] = Field(default=None, max_length=256)
    current_step: Optional[str] = Field(default=None, max_length=256)
    progress: float = Field(default=0.0)
    status: str = Field(
        default="idle", max_length=32
    )  # idle, planning, awaiting_confirmation, executing, completed, failed

    # Dynamic state
    state_variables: Optional[str] = Field(
        default=None, sa_column=Column(Text)
    )  # JSON dict
    hints: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON array
    facts: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON array
    user_preferences: Optional[str] = Field(
        default=None, sa_column=Column(Text)
    )  # JSON dict
    artifacts: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON array
    metrics: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON dict
    success_count: int = Field(default=0)
    failure_count: int = Field(default=0)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    session: AgentSession = Relationship(back_populates="state")
