import json
import logging
import importlib
import sys
from typing import Dict, Any, List, Optional, Tuple, Union, AsyncGenerator
from langchain_core.tools import tool, StructuredTool, BaseTool
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.prompts import PromptTemplate

# Re-use existing agent logic and structures
from common_lib.modules.orchestration.agent.react_master_agent import ReactMasterAgent, ReActState
from common_lib.modules.orchestration.agent.schemas import AgentDefinition, AgentIdentity, AgentType
from common_lib.modules.core_infrastructure.shared.enums import Status, AgentRole, ReasoningLevel, AutonomyLevel

logger = logging.getLogger(__name__)

# --- DEFAULT AGENT PROMPT ---
DEFAULT_SYSTEM_PROMPT = """You are a helpful and efficient AI Assistant. 

### CONTEXT:
Recent conversation:
{conversation_history}

Current structured knowledge:
{structured_state}

Long-term Labeled Context (Hints):
{hints_state}

### TOOLS:
You have access to the following tools:
{tools}

To use a tool, you must use precisely this format:
Action: one of [{tool_names}]
Action Input: the precise input for the tool

### CURRENT STRATEGY:
{strategy}

### CORE RULES (Guardrails):
{guardrails}

Begin!
Question: {input}
Thought: {agent_scratchpad}"""

DEFAULT_GUARDRAILS = [
    "Handle greetings and introductions naturally. For simple phrases like 'hi' or 'hello', provide a direct 'Final Answer' acknowledging the user.",
    "If a user introduces themselves, use 'Final Answer' to greet them. The system will automatically remember their name.",
    "If a user asks for a capability (e.g., 'PDF extraction') and you don't see an exact tool match above, you MUST use 'query_capability_inventory' first to search for it.",
    "NEVER repeat the same tool call with the same input. If a tool didn't return what you need, try a different search query or use 'query_capability_inventory'.",
    "Once you've found tool details using 'query_capability_inventory', provide them in your Final Answer (names, IDs, and functional descriptions)."
]

def format_scratchpad(intermediate_steps):
    log = ""
    for action, observation in intermediate_steps:
        log += f"Thought: {action.log}\n"
        log += f"Action: {action.tool}\n"
        log += f"Action Input: {action.tool_input}\n"
        log += f"Observation: {observation}\n"
    return log

class MasterAgent:
    """
    Modular Agentic service for the backend.
    Enables dynamic injection of:
    - system_prompt
    - guardrails
    - tools/workflows
    - initial state/hints
    """
    
    def __init__(
        self, 
        model_provider, 
        engine_manager=None, 
        system_prompt: str = None,
        guardrails: List[str] = None
    ):
        self.model_provider = model_provider
        self.engine_manager = engine_manager
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.guardrails = guardrails or DEFAULT_GUARDRAILS
        self.tool_map = {}
        
    def get_formatted_prompt(self) -> str:
        """Constructs the final prompt string with guardrails injected."""
        guardrails_str = "\n".join([f"{i+1}. {rule}" for i, rule in enumerate(self.guardrails)])
        return self.system_prompt.replace("{guardrails}", guardrails_str)

    def query_capability_inventory(self, query: str = "current") -> str:
        """Search for advanced or specialized tools NOT currently listed in your prompt."""
        query_lc = (query or "current").lower().strip().strip("'").strip('"').strip()
        is_search = query_lc not in ["current", "session", "active", "all"]
        all_capabilities = []

        if self.engine_manager:
            if hasattr(self.engine_manager, 'registry_svc') and self.engine_manager.registry_svc:
                try:
                    dynamic_tools = self.engine_manager.registry_svc.get_tools_by_category()
                    for cat, tools in dynamic_tools.items():
                        for t in tools:
                            all_capabilities.append({
                                "id": t['id'], "name": t['name'], "description": t['description'], 
                                "type": t.get("type", "tool"), "source": "registry",
                                "schema": t.get("capability", {}).get("arguments", [])
                            })
                except Exception: pass
            
            try:
                from app.core.common_lib_integration import common_memory
                workflows = common_memory.list_workflow_definitions()
                for w in workflows:
                    all_capabilities.append({
                        "id": w['id'], "name": w.get('name') or w['id'], 
                        "description": "Workflow execution or composite process", 
                        "type": "workflow", "source": "memory", "schema": w.get("inputs", [])
                    })
            except Exception: pass

        if is_search:
            keywords = [k for k in query_lc.replace("-", " ").replace(".", " ").split() if len(k) > 1]
            matches = []
            exact = next((c for c in all_capabilities if c['id'].lower() == query_lc), None)
            if exact: 
                res = f"### Detailed Capability: {exact['name']} (`{exact['id']}`)\n"
                res += f"**Description**: {exact['description']}\n\n**Input Arguments**:\n"
                for arg in exact.get("schema", []): 
                    res += f"- `{arg.get('name')}` ({arg.get('type')}): {arg.get('description')}\n"
                return res

            for cap in all_capabilities:
                text = (cap['id'] + " " + cap['name'] + " " + cap['description']).lower()
                if any(kw in text for kw in keywords): matches.append(cap)
            
            if not matches: return f"No specialized capabilities found matching '{query_lc}'."
            res = f"Found {len(matches)} matching capabilities:\n"
            for m in matches: res += f"- **{m['name']}** (`{m['id']}`): {m['description'][:100]}...\n"
            return res
        return "Search using common keywords to find specialized tools or workflows."

    async def preprocess_input(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Strategic Planner Node: Analyzes intent, extracts hints, and generates a strategy."""
        user_input = state.get("input", "")
        # This prompt is also modular if we wanted, but keeping it focused for now
        prompt = f"""Analyze the User Input for intent and key information.
User Input: {user_input}

1. Categorize intent: (greeting, instruction, question, casual, or other)
2. Extract 'hints' (entities, preferences, settings, config).
3. Generate a 'strategy': A 1-sentence high-level plan for the agent.

Format as JSON:
{{
  "intent": "...",
  "strategy": "...",
  "hints": [{{ "label": "...", "description": "...", "reasoning": "..." }}]
}}

JSON Result:"""
        try:
            res = await self.model_provider.ainvoke(prompt)
            content = str(res.content if hasattr(res, 'content') else res).strip()
            if "{" in content and "}" in content:
                found_json = json.loads(content[content.find("{"):content.rfind("}")+1])
                new_hints = found_json.get("hints", [])
                intent = found_json.get("intent", "other")
                strategy = found_json.get("strategy", "Proceed with standard ReAct reasoning.")
                
                meta = state.get("operational_metadata", {}) or {}
                meta["last_intent"] = intent
                meta["current_strategy"] = strategy
                
                # Merge with existing hints
                current_hints = state.get("hints", []) or []
                if new_hints:
                    existing_labels = {h.get("label") for h in current_hints}
                    for h in new_hints:
                        if h.get("label") not in existing_labels:
                            current_hints.append(h)

                return {"hints": current_hints, "operational_metadata": meta}
            return {}
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            return {}

    async def run_agent(self, state: Dict[str, Any], prompt_tools: List[Any]) -> Dict[str, Any]:
        """Execution Node: ReAct loop with feedback and loop prevention."""
        try:
            try:
                from langchain_classic.agents import create_react_agent
            except ImportError:
                from langchain.agents import create_react_agent
            prompt_template = PromptTemplate.from_template(self.get_formatted_prompt())
            
            react_runnable = create_react_agent(
                llm=self.model_provider,
                tools=prompt_tools,
                prompt=prompt_template
            )
            
            history = state.get("conversation_history", "")
            intermediate_steps = state.get("intermediate_steps", [])
            
            # Context window management
            hist_lines = history.split("\n")
            if len(hist_lines) > 20: history = "\n".join(hist_lines[-20:])
            
            # Loop Guard
            if len(intermediate_steps) >= 8:
                return {"agent_outcome": AgentFinish(
                    return_values={"output": "I've stopped to prevent a reasoning loop. How else can I help?"},
                    log="Loop limit (8) reached."
                )}

            # Repetition feedback
            if len(intermediate_steps) >= 2:
                last_act, last_obs = intermediate_steps[-1]
                prev_act, prev_obs = intermediate_steps[-2]
                if isinstance(last_act, AgentAction) and isinstance(prev_act, AgentAction):
                    if last_act.tool == prev_act.tool and last_act.tool_input == prev_act.tool_input:
                        if len(intermediate_steps) < 5:
                            return {"agent_outcome": AgentAction(tool="feedback", tool_input="feedback", 
                                log=f"ALERT: Repeating tool '{last_act.tool}'. Result: {last_obs}. change query.")}
                        return {"agent_outcome": AgentFinish(return_values={"output": "Stuck in repetition loop. Try rephrasing."}, log="Stuck.")}

            chain_input = {
                "input": state["input"],
                "conversation_history": history,
                "structured_state": json.dumps(state.get("structured_state", {}), indent=2),
                "hints_state": json.dumps(state.get("hints", []), indent=2),
                "strategy": (state.get("operational_metadata", {}) or {}).get("current_strategy", "Use tools."),
                "agent_scratchpad": format_scratchpad(intermediate_steps),
                "intermediate_steps": intermediate_steps
            }

            outcome = await react_runnable.ainvoke(chain_input)
            return {"agent_outcome": outcome}
        except Exception as e:
            logger.error(f"Agent Engine Error: {e}")
            return {"agent_outcome": AgentFinish(return_values={"output": f"Engine error: {e}"}, log=str(e))}
