# Checkpoint System

State snapshots for agent execution replay and debugging.

## Overview

The Checkpoint System captures full agent state at each step, enabling resume and debugging.

## Components

### AgentSnapshot
```python
class AgentSnapshot(BaseModel):
    snapshot_id: str
    session_id: str
    agent_id: str
    step_number: int
    step_name: str
    state_variables: Dict
    context: Dict
    messages: List[Dict]
    tool_calls: List[Dict]
    execution_graph: Dict
    created_at: datetime
```

### CheckpointManager
```python
class CheckpointManager:
    def create_checkpoint(session_id, agent_id, step_number, step_name, ...) -> checkpoint_id
    def get_checkpoint(checkpoint_id) -> AgentSnapshot
    def get_latest_checkpoint(session_id) -> AgentSnapshot
    def list_checkpoints(session_id, agent_id, limit) -> List[CheckpointMetadata]
    def delete_checkpoint(checkpoint_id) -> bool
```

### ExecutionReplay
```python
class ExecutionReplay:
    def replay_session(session_id, from_step) -> Dict
    def get_execution_timeline(session_id) -> List[Dict]
```

## Usage

### Create Checkpoint
```python
from common_lib.modules.orchestration.agents.checkpoint import CheckpointManager

manager = CheckpointManager(db_session)

checkpoint_id = await manager.create_checkpoint(
    session_id="session_123",
    agent_id="base_agent",
    step_number=1,
    step_name="search_entities",
    state_variables={"results": [...]},
    context={},
    messages=[...],
    tool_calls=[...]
)
```

### Replay from Checkpoint
```python
snapshot = await manager.get_checkpoint(checkpoint_id)

# Resume execution from this point
state = snapshot.state_variables
messages = snapshot.messages
```

### Get Timeline
```python
timeline = await replay.get_execution_timeline("session_123")

for step in timeline:
    print(step["step_number"], step["created_at"])
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/pipelines/checkpoints` | POST | Create checkpoint |
| `/agents/pipelines/checkpoints` | GET | List checkpoints |
| `/agents/pipelines/checkpoints/{id}` | GET | Get checkpoint |
| `/agents/pipelines/checkpoints/{id}/replay` | POST | Replay from checkpoint |
| `/agents/pipelines/checkpoints/{id}` | DELETE | Delete checkpoint |

## Database Schema

```sql
CREATE TABLE agent_checkpoints (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    step_name TEXT,
    state_json JSONB,
    context_json JSONB,
    messages_json JSONB,
    tool_calls_json JSONB,
    execution_graph_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
)
```

## Related Files

- `common_lib/src/.../orchestration/agents/checkpoint.py`