"""Agent Snapshot System - Core Innovation from Agent OS Spec

Captures full agent state for:
- Resume interrupted tasks
- Audit agent behavior
- Share agent states
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
import json
import logging

logger = logging.getLogger(__name__)

# Import AgentSession lazily to avoid circular imports
AgentSession = None


class AgentSnapshot(SQLModel, table=True):
    """Snapshot table - captures full agent state at a point in time"""

    __tablename__ = "agent_snapshots"

    id: str = Field(primary_key=True, max_length=64)
    session_id: str = Field(max_length=64, index=True)

    name: str = Field(max_length=256, description="Snapshot name/label")
    description: Optional[str] = Field(default=None, description="Snapshot description")

    snapshot_data: str = Field(
        description="JSON containing full state",
    )

    # State components captured
    context_summary: Optional[str] = Field(
        default=None, description="LTM context summary"
    )
    memory_snapshot: Optional[str] = Field(
        default=None, description="Memory state JSON"
    )
    execution_graph: Optional[str] = Field(default=None, description="DAG state JSON")
    tool_states: Optional[str] = Field(default=None, description="Tool state JSON")

    # Metadata
    message_count: int = Field(default=0, description="Number of messages at snapshot")
    token_count: Optional[int] = Field(
        default=None, description="Token count at snapshot"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    is_auto: bool = Field(default=False, description="Auto-snapshot vs manual")
    is_replay_source: bool = Field(default=False, description="Used as replay source")


class SnapshotManager:
    """Manages agent snapshots - save, restore, replay"""

    def __init__(self, session):
        self.session = session

    def create_snapshot(
        self,
        session_id: str,
        name: str,
        agent_session: Any,
        include_memories: bool = True,
        include_tool_states: bool = True,
        is_auto: bool = False,
    ) -> AgentSnapshot:
        """Create a snapshot of current agent state"""

        snapshot_data = {
            "session_id": session_id,
            "session_name": agent_session.name,
            "agent_id": agent_session.agent_id,
            "model_id": agent_session.model_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        if agent_session.history:
            snapshot_data["history"] = agent_session.history

        if agent_session.state_variables:
            snapshot_data["state_variables"] = agent_session.state_variables

        if agent_session.hints:
            snapshot_data["hints"] = agent_session.hints

        if agent_session.facts:
            snapshot_data["facts"] = agent_session.facts

        snapshot_data["current_step"] = agent_session.current_step
        snapshot_data["progress"] = agent_session.progress

        msg_count = 0
        if hasattr(agent_session, "conversations") and agent_session.conversations:
            msg_count = len(agent_session.conversations)

        snapshot = AgentSnapshot(
            id=f"{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            session_id=session_id,
            name=name,
            snapshot_data=json.dumps(snapshot_data),
            context_summary=agent_session.summary
            if hasattr(agent_session, "summary")
            else None,
            execution_graph=agent_session.execution_plan_id
            if hasattr(agent_session, "execution_plan_id")
            else None,
            message_count=msg_count,
            is_auto=is_auto,
        )

        self.session.add(snapshot)
        self.session.commit()
        self.session.refresh(snapshot)

        logger.info(f"Created snapshot {snapshot.id} for session {session_id}")
        return snapshot

    def restore_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Restore agent state from snapshot"""

        snapshot = self.session.get(AgentSnapshot, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        return json.loads(snapshot.snapshot_data)

    def list_snapshots(
        self,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[AgentSnapshot]:
        """List snapshots, optionally filtered by session"""

        query = self.session.query(AgentSnapshot)
        if session_id:
            query = query.where(AgentSnapshot.session_id == session_id)

        return query.order_by(AgentSnapshot.created_at.desc()).limit(limit).all()

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot"""

        snapshot = self.session.get(AgentSnapshot, snapshot_id)
        if snapshot:
            self.session.delete(snapshot)
            self.session.commit()
            return True
        return False

    def replay_to_session(
        self,
        snapshot_id: str,
        new_session_id: str,
    ):
        """Create new session from snapshot (for auditing/debugging)"""
        global AgentSession

        snapshot = self.session.get(AgentSnapshot, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        data = json.loads(snapshot.snapshot_data)

        if AgentSession is None:
            from app.modules.agents.runtime.session_models import AgentSession

        new_session = AgentSession(
            id=new_session_id,
            name=f"Replay: {snapshot.name}",
            user_id="system",
            agent_id=data.get("agent_id"),
            model_id=data.get("model_id"),
            history=data.get("history"),
            state_variables=data.get("state_variables"),
            hints=data.get("hints"),
            facts=data.get("facts"),
            current_step=data.get("current_step"),
            progress=data.get("progress"),
            description=f"Replayed from snapshot {snapshot_id}",
        )

        self.session.add(new_session)
        self.session.commit()

        return new_session
