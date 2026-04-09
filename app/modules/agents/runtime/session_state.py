"""
Session State Service - Manages live execution state for sessions.

Tracks:
- current_step: Current execution phase
- progress: 0-100% completion
- state_variables: Dynamic variables (file paths, extracted data, etc.)
- hints: Extracted insights
- facts: Verified information
- user_preferences: Learned preferences
- execution_plan: The plan being executed
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionStateService:
    """Manages session execution state in the database."""

    def __init__(self, memory_store):
        self.memory_store = memory_store

    def init_state(
        self, session_id: str, plan_id: str = "", workflow_id: str = ""
    ) -> Dict[str, Any]:
        """Initialize or reset session state."""
        state = {
            "id": f"state_{session_id}",
            "session_id": session_id,
            "plan_id": plan_id,
            "workflow_id": workflow_id,
            "current_step": "initializing",
            "progress": 0.0,
            "status": "planning",
            "state_variables": json.dumps({}),
            "hints": json.dumps([]),
            "facts": json.dumps([]),
            "user_preferences": json.dumps({}),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Also update session table
        self.memory_store._get_session().execute(
            "UPDATE agent_sessions SET current_step = :step, progress = :progress, "
            "state_variables = :vars, hints = :hints, facts = :facts, "
            "execution_plan_id = :plan_id, updated_at = :updated "
            "WHERE id = :session_id",
            {
                "step": "initializing",
                "progress": 0.0,
                "vars": json.dumps({}),
                "hints": json.dumps([]),
                "facts": json.dumps([]),
                "plan_id": plan_id or None,
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        self.memory_store._get_session().commit()

        return state

    def update_step(self, session_id: str, step: str, progress: float) -> None:
        """Update current step and progress."""
        self.memory_store._get_session().execute(
            "UPDATE agent_sessions SET current_step = :step, progress = :progress, updated_at = :updated WHERE id = :session_id",
            {
                "step": step,
                "progress": progress,
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        self.memory_store._get_session().execute(
            "UPDATE session_states SET current_step = :step, progress = :progress, updated_at = :updated WHERE session_id = :session_id",
            {
                "step": step,
                "progress": progress,
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        self.memory_store._get_session().commit()

    def update_status(self, session_id: str, status: str) -> None:
        """Update execution status."""
        self.memory_store._get_session().execute(
            "UPDATE session_states SET status = :status, updated_at = :updated WHERE session_id = :session_id",
            {"status": status, "updated": datetime.utcnow(), "session_id": session_id},
        )
        self.memory_store._get_session().commit()

    def add_hint(self, session_id: str, hint: Dict[str, Any]) -> None:
        """Add a hint to session state."""
        session = self.memory_store._get_session()
        result = session.execute(
            "SELECT hints FROM session_states WHERE session_id = :session_id",
            {"session_id": session_id},
        )
        row = result.fetchone()
        hints = json.loads(row[0]) if row and row[0] else []
        hints.append(hint)

        session.execute(
            "UPDATE session_states SET hints = :hints, updated_at = :updated WHERE session_id = :session_id",
            {
                "hints": json.dumps(hints),
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        session.execute(
            "UPDATE agent_sessions SET hints = :hints, updated_at = :updated WHERE id = :session_id",
            {
                "hints": json.dumps(hints),
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        session.commit()

    def add_fact(self, session_id: str, fact: Dict[str, Any]) -> None:
        """Add a fact to session state."""
        session = self.memory_store._get_session()
        result = session.execute(
            "SELECT facts FROM session_states WHERE session_id = :session_id",
            {"session_id": session_id},
        )
        row = result.fetchone()
        facts = json.loads(row[0]) if row and row[0] else []
        facts.append(fact)

        session.execute(
            "UPDATE session_states SET facts = :facts, updated_at = :updated WHERE session_id = :session_id",
            {
                "facts": json.dumps(facts),
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        session.execute(
            "UPDATE agent_sessions SET facts = :facts, updated_at = :updated WHERE id = :session_id",
            {
                "facts": json.dumps(facts),
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        session.commit()

    def set_variable(self, session_id: str, key: str, value: Any) -> None:
        """Set a state variable."""
        session = self.memory_store._get_session()
        result = session.execute(
            "SELECT state_variables FROM session_states WHERE session_id = :session_id",
            {"session_id": session_id},
        )
        row = result.fetchone()
        vars_dict = json.loads(row[0]) if row and row[0] else {}
        vars_dict[key] = value

        session.execute(
            "UPDATE session_states SET state_variables = :vars, updated_at = :updated WHERE session_id = :session_id",
            {
                "vars": json.dumps(vars_dict),
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        session.execute(
            "UPDATE agent_sessions SET state_variables = :vars, updated_at = :updated WHERE id = :session_id",
            {
                "vars": json.dumps(vars_dict),
                "updated": datetime.utcnow(),
                "session_id": session_id,
            },
        )
        session.commit()

    def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current session state."""
        session = self.memory_store._get_session()
        result = session.execute(
            "SELECT * FROM session_states WHERE session_id = :session_id",
            {"session_id": session_id},
        )
        row = result.fetchone()
        if not row:
            return None

        # Convert to dict
        keys = result.keys()
        state = dict(zip(keys, row))

        # Parse JSON fields
        for field in ["state_variables", "hints", "facts", "user_preferences"]:
            if state.get(field):
                state[field] = json.loads(state[field])

        return state
