"""
app/agentic/master_agent.py
--------------------------
Proxy for the common_lib MasterAgent.
"""
from common_lib.modules.orchestration.agent.master_agent import (
    MasterAgent as CLMasterAgent,
    DEFAULT_SYSTEM_PROMPT,
    GEMINI_AGENT_PROMPT,
    DEFAULT_GUARDRAILS,
    format_scratchpad
)

# Re-export for backward compatibility
MasterAgent = CLMasterAgent
