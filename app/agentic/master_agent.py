import json
import logging
import importlib
import sys
from typing import Dict, Any, List, Optional, Tuple, Union, AsyncGenerator
from langchain_core.tools import tool, StructuredTool, BaseTool
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.prompts import PromptTemplate
from common_lib.modules.ai_models.llm.base import AgentStrategy

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

# --- GEMINI AGENT PROMPT (Phase 6) ---
GEMINI_AGENT_PROMPT = """You are a helpful and efficient AI Assistant. 

### CONTEXT:
Recent conversation:
{conversation_history}

Current structured knowledge:
{structured_state}

Long-term Labeled Context (Hints):
{hints_state}

### STRATEGY:
{strategy}

### TOOLS:
You have access to the following tools:
{tools}

### INSTRUCTION:
You may use tools to fulfill the user's request.
When using a tool, you must respond ONLY with a JSON object in this format (no other text):
{{
  "thought": "brief reasoning",
  "tool": "tool_name",
  "input": {{ ... }}
}}

If you have the final answer, respond ONLY with a JSON object in this format (no other text):
{{
  "thought": "I have finished.",
  "final_answer": "your response"
}}

### CORE RULES (Guardrails):
{guardrails}

Begin!
Question: {input}
JSON Result:"""

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
        
    def get_formatted_prompt(self, strategy: AgentStrategy = AgentStrategy.REACT) -> str:
        """Constructs the final prompt string with guardrails injected."""
        prompt = self.system_prompt
        # Phase 6 & Strategy Refactor: Ensure JSON instructions are present if strategy is JSON_TOOL
        if strategy == AgentStrategy.JSON_TOOL and "JSON Result:" not in prompt:
            # Phase 13: Escape braces for PromptTemplate.format
            prompt = prompt + "\n\nIMPORTANT: Respond ONLY with a valid JSON object. You must include either a 'tool' call (with 'input') OR a 'final_answer'.\nFormat 1: {{ \"thought\": \"...\", \"tool\": \"...\", \"input\": {{...}} }}\nFormat 2: {{ \"thought\": \"...\", \"final_answer\": \"...\" }}\nJSON Result:"
            
        guardrails_str = "\n".join([f"{i+1}. {rule}" for i, rule in enumerate(self.guardrails)])
        return prompt.replace("{guardrails}", guardrails_str)

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
                json_part = content[content.find("{"):content.rfind("}")+1]
                found_json = json.loads(json_part)
                
                # Robust key mapping (strip quotes, spaces, and case)
                def clean_key(k):
                    return str(k).strip().strip('"').strip("'").lower()
                
                norm_json = {clean_key(k): v for k, v in found_json.items()}
                
                new_hints = norm_json.get("hints", [])
                intent = norm_json.get("intent", "other")
                strategy = norm_json.get("strategy", "Proceed with standard ReAct reasoning.")
                
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
        """Execution Node: ReAct loop with Strategy-based dispatch (Phase 6 & 11)."""
        strategy = self.model_provider.get_agent_strategy()
        
        try:
            history = state.get("conversation_history", "")
            intermediate_steps = state.get("intermediate_steps", [])
            
            # 1. Loop Guard
            if len(intermediate_steps) >= 8:
                return {"agent_outcome": AgentFinish(
                    return_values={"output": "I've stopped to prevent an infinite loop. How else can I help?"},
                    log="Loop limit (8) reached."
                )}

            # 2. Format Context
            hist_lines = history.split("\n")
            if len(hist_lines) > 20: history = "\n".join(hist_lines[-20:])
            
            tools_str = "\n".join([f"- {getattr(t, 'name', str(t))}: {getattr(t, 'description', '')}" for t in prompt_tools])
            tool_names = ", ".join([getattr(t, 'name', str(t)) for t in prompt_tools])

            chain_input = {
                "input": state["input"],
                "conversation_history": history,
                "intermediate_steps": intermediate_steps, # Required for ReAct runnable
                "structured_state": json.dumps(state.get("structured_state", {}), indent=2),
                "hints_state": json.dumps(state.get("hints", []), indent=2),
                "strategy": (state.get("operational_metadata", {}) or {}).get("current_strategy", "Use tools."),
                "tools": tools_str,
                "tool_names": tool_names,
                "agent_scratchpad": format_scratchpad(intermediate_steps)
            }

            # 3. Optimized JSON Tool Handling (Modular Adapter)
            if strategy == AgentStrategy.JSON_TOOL:
                prompt_template = PromptTemplate.from_template(self.get_formatted_prompt(strategy=strategy))
                full_prompt = prompt_template.format(**chain_input)
                
                last_error = None
                for attempt in range(2): # Phase 10: Retry rule
                    try:
                        # Phase 13: Enable native JSON mode for Gemini
                        res = await self.model_provider.ainvoke(
                            full_prompt, 
                            response_mime_type="application/json"
                        )
                        content = str(res.content if hasattr(res, 'content') else res).strip()
                        logger.info(f"LLM Raw Output ({strategy.value}): {content}")
                        
                        # Robust parsing for JSON-first models
                        if content.startswith("ERROR:"):
                            return {"agent_outcome": AgentFinish(
                                return_values={"output": content},
                                log=f"Provider Error: {content}"
                            )}

                        try:
                            # With response_mime_type, content should be pure JSON
                            json_start = content.find("{")
                            json_end = content.rfind("}")
                            if json_start != -1 and json_end != -1:
                                content = content[json_start:json_end+1]
                                
                            raw_payload = json.loads(content)
                            if isinstance(raw_payload, list) and len(raw_payload) > 0:
                                raw_payload = raw_payload[0] # Handle array wrap
                            
                            if not isinstance(raw_payload, dict):
                                raise ValueError(f"Expected JSON object, got {type(raw_payload).__name__}")

                            # Clean keys (remove LLM-inserted quotes/spaces/extra chars)
                            def clean_key(k):
                                return str(k).strip().strip('"').strip("'").lower()

                            payload = {clean_key(k): v for k, v in raw_payload.items()}
                                
                            thought = payload.get("thought") or payload.get("reasoning") or "Proceeding..."
                            
                            if "tool" in payload and payload["tool"]:
                                return {"agent_outcome": AgentAction(
                                    tool=payload["tool"],
                                    tool_input=payload.get("input", {}),
                                    log=f"Thought: {thought}\nAction: {payload['tool']}\nAction Input: {payload.get('input', {})}"
                                )}
                            elif "final_answer" in payload:
                                return {"agent_outcome": AgentFinish(
                                    return_values={"output": payload["final_answer"]},
                                    log=f"Thought: {thought}\nFinal Answer: {payload['final_answer']}"
                                )}
                            else:
                                # Fallback for smaller models (like Gemini Flash) that might only return thought
                                return {"agent_outcome": AgentFinish(
                                    return_values={"output": thought},
                                    log=f"Thought: {thought} (Fallback as Final Answer)"
                                )}
                        except Exception as parse_err:
                            logger.error(f"JSON Parse error: {parse_err}")
                            if attempt == 1:
                                return {"agent_outcome": AgentFinish(return_values={"output": content}, log=content)}
                        
                        # Phase 10: Fallback to text if JSON parse fails
                        logger.warning(f"JSON strategy attempt {attempt+1} parse failed, falling back to text.")
                        if attempt == 1:
                            return {"agent_outcome": AgentFinish(return_values={"output": content}, log=content)}
                    except Exception as e:
                        last_error = e
                        logger.error(f"JSON strategy attempt {attempt+1} failed: {e}")
                        if attempt == 1:
                            return {"agent_outcome": AgentFinish(return_values={"output": f"Engine error: {last_error}"}, log=str(last_error))}
                
                return {"agent_outcome": AgentFinish(return_values={"output": content}, log=content)}

            # 4. Standard ReAct for Common Providers
            try:
                from langchain_classic.agents import create_react_agent
            except ImportError:
                from langchain.agents import create_react_agent
                
            prompt_template = PromptTemplate.from_template(self.get_formatted_prompt(strategy=strategy))
            react_runnable = create_react_agent(
                llm=self.model_provider,
                tools=prompt_tools,
                prompt=prompt_template
            )
            
            outcome = await react_runnable.ainvoke(chain_input)
            return {"agent_outcome": outcome}
            
        except Exception as e:
            import traceback
            logger.error(f"Agent Engine Error: {e}")
            logger.error(traceback.format_exc())
            # Phase 13: Robust error reporting
            final_err_msg = str(e)
            return {"agent_outcome": AgentFinish(
                return_values={"output": f"Engine error: {final_err_msg}"}, 
                log=f"Full Traceback: {traceback.format_exc()}"
            )}
