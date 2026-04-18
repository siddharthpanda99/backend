# Multi-Agent Coordination

Agent coordination following unified pipeline contracts.

## Overview

Multi-agent coordination is a **special case of the unified pipeline system** where agents (non-executable) work together following the same state, checkpoint, and retry patterns as executable workflows.

Both executable and non-executable pipelines use identical:
- State structure
- Checkpoint format
- Error handling
- Retry/Pause logic

## Agent Contract (Loose Coupling)

Agents communicate via standardized **AgentInput/AgentOutput**:

```python
# Input (received by agent)
class AgentInput:
    task_description: str   # What to do
    context: Dict          # Shared context from WorkflowState
    state_variables: Dict  # Outputs from previous steps
    max_steps: int         # Execution limit

# Output (produced by agent)
class AgentOutput:
    task_id: str
    status: str            # success/error/need_input
    result: Any            # Main result
    next_step: str        # Next step in chain
    state_updates: Dict  # Updates to WorkflowState
```

## Unified State (Same as Executable)

```python
class WorkflowState:
    # Identity
    execution_id: str
    status: str
    
    # Centralized state (SAME for all types)
    state_variables: Dict
    context: Dict
    
    # Tracing (SAME for all types)
    messages: List[Dict]
    tool_calls: List[Dict]
    execution_graph: Dict
    
    # Retry/Pause (SAME for all)
    retry_count: int
```

## Components

### PlannerAgent
```python
class PlannerAgent:
    def plan(user_request, available_agents, context) -> List[Dict]
```

### ExecutorAgent
```python
class ExecutorAgent:
    def execute(task, shared_context) -> Dict
```

### CriticAgent
```python
class CriticAgent:
    def critique(task_results, original_request) -> Dict
```

### MultiAgentCoordinator (Integrated with UnifiedPipelineExecutor)
```python
class MultiAgentCoordinator:
    def execute(user_request, available_agents, context, use_critic) -> MultiAgentCoordination
    def get_coordination(coordination_id) -> MultiAgentCoordination
    def list_coordinations() -> List[MultiAgentCoordination]

# Usage within UnifiedPipelineExecutor:
async def _execute_agent(step, state):
    """Identical execution pattern to _execute_skill / _execute_workflow"""
    # 1. Check permission (same as skill/workflow)
    if not self._check_permission(step.agent_id):
        raise PermissionError(f"Agent {step.agent_id} not allowed")
    
    # 2. Build input from state (SAME AS EXECUTABLE)
    input = AgentInput(
        task_description=step.prompt.format(**state.state_variables),
        context=state.context,
        state_variables=state.state_variables,
        max_steps=step.max_steps
    )
    
    # 3. Execute (same pattern as skill/workflow)
    result = await self.coordinator.execute(input)
    
    # 4. Update state (IDENTICAL to skill/workflow)
    state.state_variables.update(result.state_updates)
    state.messages.extend(result.messages)
    state.execution_graph.add_node(step.step_id, result)
    
    # 5. Retry/Pause (SAME LOGIC as executable)
    if result.status == "error":
        await self._handle_retry(step, state)
    
    return result
```

## Usage

### Execute Multi-Agent Task
```python
from common_lib.modules.orchestration.agents.multi_agent import MultiAgentCoordinator

coordinator = MultiAgentCoordinator(
    planner=PlannerAgent(llm),
    executor=ExecutorAgent(agent_executor),
    critic=CriticAgent(llm)
)

result = await coordinator.execute(
    user_request="Find AI papers from 2024 and create a summary",
    available_agents=["planner", "executor", "critic"],
    context={},
    use_critic=True  # Enable critique
)

print(result.coordination_id)
print(result.status)  # "success", "partial"
for task in result.tasks:
    print(task.agent_role, task.status)
```

### Example Flow

```
Request: "Find AI papers and summarize them"

Planner:
  → Task 1: Search papers (executor)
  → Task 2: Download PDF (executor)
  → Task 3: Write summary (executor)

Executor:
  → Searches, downloads, summarizes

Critic:
  → Reviews: "Good quality, well structured"
  → Approved
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/multi-agent/execute` | POST | Execute multi-agent |
| `/agents/multi-agent/executions` | GET | List coordinations |
| `/agents/multi-agent/executions/{id}` | GET | Get coordination |

## Related Files

- `common_lib/src/.../orchestration/agents/multi_agent.py`