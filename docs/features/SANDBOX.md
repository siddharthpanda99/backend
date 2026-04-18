# Tool Permission & Sandbox

Security system for tool access control and execution safety.

## Overview

The Sandbox System provides permissions, rate limits, and command blocking for tool execution.

## Components

### ToolPermission
```python
class ToolPermission(BaseModel):
    tool_id: str
    allowed: bool = True
    requires_approval: bool = False
    max_calls_per_minute: int = 60
    max_concurrent: int = 5
    timeout_ms: int = 30000
```

### ToolPolicy
```python
class ToolPolicy(BaseModel):
    policy_id: str
    name: str
    description: str
    permissions: Dict[str, ToolPermission]
    blocked_patterns: List[str]  # Regex patterns
    allowed_agents: List[str]
```

### SandboxedExecution
```python
class SandboxedExecution(BaseModel):
    tool_id: str
    allowed: bool
    reason: str
    output: Any
    error: Optional[str]
    executed_at: datetime
    duration_ms: int
```

## Usage

### Create Policy
```python
from common_lib.modules.orchestration.tools.sandbox import (
    ToolPermissionManager, SandboxBuilder
)

manager = ToolPermissionManager()

# Builder approach
policy = SandboxBuilder().allow_tool("file_read", max_calls_per_minute=10)\
    .block_tool("system_exec")\
    .block_pattern(r"rm\s+-rf")\
    .build("safe_policy", "Safe Tool Policy")

manager.register_policy(policy)
```

### Assign to Agent
```python
manager.assign_policy_to_agent("base_agent", "safe_policy")
```

### Check Permission
```python
result = manager.check_permission("base_agent", "file_read")

if result.allowed:
    print(result.reason)  # "Allowed"
else:
    print(result.reason)  # "Rate limit exceeded"
```

### Execute with Sandbox
```python
result = await manager.execute_with_sandbox(
    agent_id="base_agent",
    tool_id="file_read",
    tool_executor=read_file,
    tool_args={"path": "/data/file.txt"}
)

print(result.allowed)
print(result.duration_ms)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/policies` | POST | Create policy |
| `/agents/policies` | GET | List policies |
| `/agents/policies/{id}/assign` | POST | Assign to agent |

## Related Files

- `common_lib/src/.../orchestration/tools/sandbox.py`