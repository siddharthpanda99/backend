# Pipeline System

Unified execution system for skills, workflows, and agent chains.

## Overview

The Pipeline System provides a **single unified architecture** for all execution types:
- **Executable** (tools, workflows) - Direct execution
- **Non-Executable** (agent chains, skill chains) - Coordinated execution

Both follow identical patterns for state, tracing, retry, and pause.

## Unified Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                    UnifiedPipelineExecutor                         │
├────────────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────┐    ┌──────────────┐    ┌─────────────┐   │
│   │  Pipeline   │───▶│  Execution   │───▶│   Result    │   │
│   │  Definition │    │   Engine     │    │  Tracking  │   │
│   └─────────────┘    └──────────────┘    └─────────────┘   │
│         │                    │                    │            │
│         ▼                    ▼                    ▼            │
│   ┌─────────────────────────────────────────────────────────┐ │
│   │              WorkflowState (Unified)                       │ │
│   │  - current_step: str                                    │ │
│   │  - state_variables: Dict                               │ │
│   │  - context: Dict                                      │ │
│   │  - execution_graph: Dict    ◀── Centralized State  │ │
│   │  - messages: List[Dict]                               │ │
│   │  - tool_calls: List[Dict]                             │ │
│   └─────────────────────────────────────────────────────────┘ │
│                                                             │
└────────────────────────────────────────────────────────────────────┘
```

## Execution Types

### Type 1: Skill Execution
```yaml
steps:
  - step_id: skill_step
    type: skill
    skill_id: entity_search
```
Executes skill directly with state tracking.

### Type 2: Workflow Execution  
```yaml
steps:
  - step_id: workflow_step
    type: workflow
    workflow_id: process_data
```
Executes workflow with state tracking.

### Type 3: Agent Chain (Non-Executable)
```yaml
steps:
  - step_id: planner_task
    type: agent
    agent_role: planner
    prompt: "Decompose: {input}"
    outputs_mapping:
      subtasks: plan_result
  
  - step_id: executor_task
    type: agent
    agent_role: executor
    depends_on: [planner_task]
    
  - step_id: critic_task
    type: agent
    agent_role: critic
    depends_on: [executor_task]
```

**Both run identically** - same state, same checkpointing, same retry logic.

## State Contract

All pipeline types use the same `WorkflowState`:

```python
class WorkflowState:
    # Identity
    pipeline_id: str
    execution_id: str
    status: str  # pending/running/completed/failed
    
    # Centralized state (all types)
    current_step: str
    state_variables: Dict[str, Any]
    context: Dict[str, Any]
    
    # Tracing (identical for all types)
    messages: List[Dict]      # Conversation history
    tool_calls: List[Dict]    # Tool invocations
    execution_graph: Dict   # DAG for tracing
    
    # Retry/Pause support
    retry_count: int
    pause_reason: Optional[str]
```

## Agent Contract (Loose Coupling)

Agents communicate via standardized state:

```python
# Agent input contract
class AgentInput:
    task_description: str
    context: Dict        # Shared context from state
    state_variables: Dict  # Previous outputs
    max_steps: int
    
# Agent output contract
class AgentOutput:
    task_id: str
    status: str           # success/error/need_input
    result: Any
    next_step: Optional[str]
    state_updates: Dict   # Writes to state_variables
```

## Retry & Pause (Identical for All)

```python
# All pipeline types support:
pipeline.steps[step_id].retry_count = 3  # Same for all
pipeline.steps[step_id].timeout_ms = 30000 # Same for all
pipeline.steps[step_id].condition = "{status} == success"  # Same for all
```

## Checkpoint Integration

All execution types save to same checkpoint format:

```python
snapshot = AgentSnapshot(
    state_variables=state.state_variables,
    context=state.context,
    messages=state.messages,
    tool_calls=state.tool_calls,
    execution_graph=state.execution_graph,
)
# Replay works identically for all types
```

## Example: Skill Chain vs Agent Chain

### Skill Chain (Executable)
```yaml
id: extract_and_summarize
steps:
  - type: skill
    skill_id: extract_entities
  - type: skill  
    skill_id: summarize
```

### Agent Chain (Non-Executable)
```yaml
id: research_and_summarize
steps:
  - type: agent
    agent_role: planner
  - type: agent
    agent_role: executor
  - type: agent
    agent_role: critic
```

**Both:**
- Save checkpoints at same points
- Use same retry logic
- Same state structure
- Same API endpoints
- Identical replay/debug

## API Endpoints

All types use same endpoints:

| Endpoint | All Types |
|----------|----------|
| `/pipelines/execute` | skill/workflow/agent |
| `/pipelines/executions/{id}` | Same response |
| `/pipelines/checkpoints` | Same format |
| `/pipelines/checkpoints/{id}/replay` | Identical |

## Implementation

```python
class UnifiedPipelineExecutor:
    async def execute(self, pipeline, initial_inputs):
        state = WorkflowState(
            pipeline_id=pipeline.id,
            execution_id=uuid4(),
            state_variables=initial_inputs
        )
        
        for step in pipeline.steps:
            # 1. Create checkpoint
            await checkpoint_manager.create(state)
            
            # 2. Execute (any type)
            if step.type == "skill":
                result = await self._execute_skill(step, state)
            elif step.type == "workflow":
                result = await self._execute_workflow(step, state)
            elif step.type == "agent":
                result = await self._execute_agent(step, state)  # Same pattern
            
            # 3. Update state identically
            state.state_variables.update(result.outputs)
            state.messages.extend(result.messages)
            
            # 4. Check retry/pause
            if step.retry_count > 0 and result.status == "error":
                # Retry logic applied to all types
                pass
                
        return state
```