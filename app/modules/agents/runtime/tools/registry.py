"""
app/modules/agents/runtime/tools/registry.py
-------------------------------------------
Proxy for common_lib tool registry.
"""

from common_lib.modules.orchestration.agents.agent.execution.tools.registry import (
    BUILTIN_TOOL_REGISTRY,
    get_tool_meta,
    get_tools_by_category,
)
