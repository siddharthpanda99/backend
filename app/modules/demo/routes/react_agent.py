import os
import json
import logging
import traceback
import sys
import importlib
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Dict, Any
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_core.tools import tool, StructuredTool

from common_lib.modules.orchestration.agent.react_master_agent import ReactMasterAgent, ReActState, AgentAction, AgentFinish
from common_lib.modules.orchestration.agent.schemas import AgentDefinition, AgentIdentity, AgentType
from common_lib.modules.core_infrastructure.shared.enums import Status, AgentRole, ReasoningLevel, AutonomyLevel
from app.core.common_lib_integration import common_memory

# ANSI Colors for terminal
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"
CYAN = "\033[96m"
GRAY = "\033[90m"

router = APIRouter()
VERSION_ID = "1.1.3-BETA"

# Setup high-fidelity logging for the demo module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    # Custom colored formatter
    class ColoredFormatter(logging.Formatter):
        def format(self, record):
            msg = super().format(record)
            if record.levelno >= logging.ERROR:
                return f"{RED}{msg}{RESET}"
            elif record.levelno >= logging.WARNING:
                return f"{YELLOW}{msg}{RESET}"
            elif "Entering node" in msg or "Exiting node" in msg:
                return f"{CYAN}{msg}{RESET}"
            elif "Tool called" in msg or "Tool result" in msg:
                return f"{GREEN}{msg}{RESET}"
            return msg

    formatter = ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Same tools as before
@tool
def get_current_weather(location: str) -> str:
    """Get the current weather in a given location"""
    if "san francisco" in location.lower():
        return "It's 60 degrees and foggy."
    elif "new york" in location.lower():
        return "It's 80 degrees and sunny."
    return "It's 72 degrees and pleasant."

@tool
def calculate_math(expression: str) -> str:
    """Safely calculate simple numeric math expressions. 
    ONLY pass valid mathematical expressions like '10 + 5' or 'max(10, 20)'. 
    Do NOT pass words, names, or sentences.
    """
    try:
        # Basic sanitization: expression must contain at least one digit or math operator
        import re
        if not re.search(r'[0-9+\-*/().]', expression):
             return "Error: Expression does not look like math. Please provide a numeric expression."
             
        # Limited builtins for safety
        return str(eval(expression, {"__builtins__": None}, {"abs": abs, "round": round, "min": min, "max": max}))
    except Exception as e:
        return f"Error calculating: {e}"

@tool
def query_capability_inventory(query: str = "current") -> str:
    """
    Search for advanced or specialized tools NOT currently listed in your prompt.
    If 'query' is an exact tool ID, returns the full input schema.
    Returns names, identifiers, AND detailed input/output schemas if found.
    """
    global _active_session_config, _engine_manager
    
    query_lc = (query or "current").lower().strip()
    is_search = query_lc not in ["current", "session", "active"]
    all_capabilities = []

    # 1. Collate all known capabilities
    if _engine_manager:
        # Static demo tools
        for t in DEMO_TOOL_REGISTRY:
             all_capabilities.append({
                 "id": t['id'], 
                 "name": t['name'], 
                 "description": t['description'], 
                 "type": "tool",
                 "source": "demo"
             })
        
        # Dynamic tools from registry
        if _engine_manager.registry_svc:
            try:
                dynamic_tools = _engine_manager.registry_svc.get_tools_by_category()
                for cat, tools in dynamic_tools.items():
                    for t in tools:
                        all_capabilities.append({
                            "id": t['id'], 
                            "name": t['name'], 
                            "description": t['description'], 
                            "type": "tool",
                            "source": "registry",
                            "schema": t.get("capability", {}).get("arguments", [])
                        })
            except Exception: pass
            
        try:
            from common_lib.modules.memory import common_memory
            workflows = common_memory.list_workflow_definitions()
            for w in workflows:
                all_capabilities.append({
                    "id": w['id'], 
                    "name": w.get('name') or w['id'], 
                    "description": "Workflow execution", 
                    "type": "workflow",
                    "source": "memory",
                    "schema": w.get("inputs", [])
                })
        except Exception: pass

    # 2. If it's a search, filter the results
    if is_search:
        matches = []
        keywords = query_lc.split()
        
        # Check for exact ID match first (detailed view)
        exact_match = next((c for c in all_capabilities if c['id'].lower() == query_lc), None)
        if exact_match:
            res = f"### Detailed Capability: {exact_match['name']} (`{exact_match['id']}`)\n"
            res += f"**Description**: {exact_match['description']}\n"
            res += f"**Type**: {exact_match['type'].title()}\n\n"
            
            schema = exact_match.get("schema")
            if schema:
                res += "**Input Arguments**:\n"
                if isinstance(schema, list):
                    for arg in schema:
                        name = arg.get("name", "arg")
                        a_type = arg.get("type", "any")
                        a_desc = arg.get("description", "")
                        res += f"- `{name}` ({a_type}): {a_desc}\n"
                else:
                    res += f"```json\n{json.dumps(schema, indent=2)}\n```\n"
            else:
                 res += "*No detailed schema available for this capability.*\n"
            return res

        # Fallback to general search
        for cap in all_capabilities:
            text = f"{cap['id']} {cap['name']} {cap['description']}".lower()
            if any(k in text for k in keywords):
                matches.append(cap)
        
        if not matches:
            return f"No specialized capabilities found matching '{query}'. If it is not here, it is currently unavailable."
            
        res = f"### Search Results for '{query}'\n"
        for m in matches[:10]: # Limit to 10 for prompt efficiency
            res += f"- {m['name']} (`{m['id']}`): {m['description']}\n"
            # If search is specific and few matches, include schema summary
            if len(matches) <= 3 and m.get("schema"):
                res += "  *Arguments*: " + ", ".join([a.get('name', '') for a in m['schema'] if isinstance(a, dict)]) + "\n"
        
        res += "\nTo see full input requirements for a tool, call `query_capability_inventory` with its unique ID."
        return res

    # 3. Default: Show active session tools
    if not _active_session_config:
        agent_name = "Master Agent"
        active_tools = DEMO_TOOL_REGISTRY
    else:
        agent_name = _active_session_config.get('agent_display_name', 'Master Agent')
        active_tools = _active_session_config.get("tools", [])

    header = f"### Active Capabilities for '{agent_name}'\n"
    if not active_tools:
        return header + "No tools are currently active."
        
    res = header
    for t in active_tools:
        res += f"- **{t['name']}** (`{t['id']}`): {t['description'][:100]}...\n"
    return res

@tool
def remember_info(key: str, value: Any) -> str:
    """
    Store or update a key/value pair in your structured state.
    Use this to track entities, user preferences, or checklist progress.
    """
    return f"Fact remembered: {key} = {value}"

@tool
async def extract_and_remember_hints(text: str) -> str:
    """
    Analyzes text to extract useful hints like user names, preferences, or context labels.
    Automatically categorizes and labels them for structured memory.
    """
    if not _master_agent:
        return "Error: Agent not initialized."
        
    prompt = f"""Analyze the following interaction and extract key 'hints' about the user or context.
For each hint, provide:
- label: A short name/key (e.g. "User Name")
- description: The core fact or preference
- reasoning: Why you labeled this (e.g. "User introduced himself")

Format as a JSON list under the key "hints".
Example: {{"hints": [{{ "label": "User Name", "description": "Siddharth", "reasoning": "Explicit introduction" }}]}}

Interaction: {text}

JSON Result:"""
    
    try:
        # We use a direct call to the underlying model for extraction
        response = await _master_agent.model_provider.ainvoke(prompt)
        content = str(response.content if hasattr(response, 'content') else response).strip()
        if "{" in content and "}" in content:
            found_json = json.loads(content[content.find("{"):content.rfind("}")+1])
            new_hints = found_json.get("hints", [])
            return f"Hints picked up and labeled:\n{json.dumps(new_hints, indent=2)}"
        return "No clear hints extracted."
    except Exception as e:
        return f"Extraction failed: {e}"

def resolve_handler(handler_path: str) -> Optional[Any]:
    """Resolves a string handler path (e.g. 'pkg.module.function') to the actual callable."""
    if not handler_path:
        return None
    if not isinstance(handler_path, str):
        return handler_path # It might already be a callable
        
    try:
        if "." not in handler_path:
            # Check if it's in the current module's globals
            return globals().get(handler_path)
            
        module_path, func_name = handler_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, func_name)
    except Exception as e:
        logger.error(f"Failed to resolve handler {handler_path}: {e}")
        return None

def tool_schema_to_langchain(schema: Any) -> Optional[StructuredTool]:
    """Converts a Registry ToolSchema to a LangChain StructuredTool."""
    handler = resolve_handler(schema.execution.handler)
    if not handler:
        return None
        
    return StructuredTool.from_function(
        func=handler,
        name=schema.id.replace(".", "__"),
        description=schema.capability.description,
    )

# Robust ReAct prompt - Strict formatting for reliable parsing with local LLMs
DEMO_AGENT_PROMPT = """You are a helpful and efficient AI Assistant. 

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

### CORE RULES:
1. Handle greetings and introductions naturally. For simple phrases like "hi", "hello", "my name is...", or casual chat, provide a direct 'Final Answer' acknowledging the user.
2. DO NOT use tools (like 'remember_info') for basic introductions or casual chat. The system automatically handles long-term context extraction for you after the turn is finished.
3. ONLY use tools if you need specific, external information (weather, calculation, or searching for advanced tool capabilities).
4. If a user asks for a capability (e.g., 'PDF parsing') and you don't see an exact match in {tool_names}, ALWAYS use 'query_capability_inventory' with synonyms like 'extract', 'read', or 'parse' before saying no.
5. NEVER repeat the same tool call with the same input. If a search result didn't change, provide a 'Final Answer' based on the current results.
6. Once you find a capability match, provide a 'Final Answer' summarizing the tool names, their IDs, and their functional descriptions to the user.
7. Once you have acknowledged a greeting or introduction, finish with a 'Final Answer' immediately.
7. Example for "I am Siddharth": 
   Thought: The user is introducing himself. I should acknowledge this naturally without tools.
   Final Answer: Nice to meet you, Siddharth! How can I help today?


### FORMAT:
Question: {input}
Thought: [brief reasoning]
Action: [{tool_names}] (only if needed)
Action Input: [input]
Observation: [result]
... (repeat if needed)
Thought: I have finished.
Final Answer: [your response]

Begin!
Question: {input}
Thought: {agent_scratchpad}"""

# Registry of all available demo tools with metadata (single source of truth)
DEMO_TOOL_REGISTRY = [
    {
        "id": "get_current_weather",
        "name": "Weather Lookup",
        "description": "Get the current weather for a given location.",
        "handler": get_current_weather,
        "category": "demo"
    },
    {
        "id": "calculate_math",
        "name": "Math Calculator",
        "description": "Safely evaluate simple math expressions (e.g. '2 + 2 * 3').",
        "handler": calculate_math,
        "category": "demo"
    },
    {
        "id": "query_capability_inventory",
        "name": "Capability Inventory",
        "description": "Explore and list all tools and workflows available to the agent.",
        "handler": query_capability_inventory,
        "category": "system"
    },
    {
        "id": "remember_info",
        "name": "Remember Info",
        "description": "Store key facts or user preferences in your structured state.",
        "handler": remember_info,
        "category": "system"
    },
    {
        "id": "extract_and_remember_hints",
        "name": "Hint Extractor",
        "description": "Automatically extract names, preferences, and context labels from the conversation.",
        "handler": extract_and_remember_hints,
        "category": "system"
    },
]

ALL_DEMO_TOOLS = [entry["handler"] for entry in DEMO_TOOL_REGISTRY]


from inference_platform.core.engine_manager import EngineManager
from inference_platform.core.schema import CommandContext

from common_lib.modules.ai_models.llm.langchain_adapter import LangChainModelAdapter

# Global state for the demo
_engine_manager: Optional[EngineManager] = None
_master_agent: Optional[ReactMasterAgent] = None
_active_session_config: Dict[str, Any] = {}  # Tracks what's currently deployed

# Persistence for session state (Memory, History, ReAct Steps)
from langgraph.checkpoint.memory import MemorySaver
_checkpointer = MemorySaver()

# --- Registry and Initialization ---

def load_agent(
    model_path: str = None,
    provider: str = "local_llama",
    agent_id: str = "demo_master_agent",
    tool_ids: list = None
) -> ReactMasterAgent:
    """Dynamically loads or reloads the master agent."""
    global _engine_manager, _master_agent
    
    class DummyContext:
        def __init__(self):
            self.adapter = None
            self.service = None 
            
    ctx = DummyContext()
    
    if _engine_manager is None:
        _engine_manager = EngineManager(ctx)
    
    env_model = os.getenv("LOCAL_LLM_MODEL_PATH") or os.getenv("LOCAL_HF_MODEL_PATH")
    env_provider = os.getenv("LLM_PROVIDER_TYPE", provider)
    
    _engine_manager.setup(
        target_files=[], 
        model_path=env_model or model_path, 
        provider_type=env_provider,
        preload=True
    )

    raw_provider = _engine_manager.main_llm
    model_provider = LangChainModelAdapter(provider=raw_provider)
    
    identity = AgentIdentity(
        agent_name=agent_id,
        display_name=agent_id.replace("_", " ").capitalize(),
        version="1.0",
        status=Status.ACTIVE,
        owner="system"
    )
    agent_type = AgentType(
        role=AgentRole.ORCHESTRATOR,
        secondary_roles=[],
        reasoning_level=ReasoningLevel.ANALYTICAL,
        autonomy=AutonomyLevel.FULL,
        template=None
    )
    
    definition = AgentDefinition(
        identity=identity,
        type=agent_type,
        system_prompt_override=DEMO_AGENT_PROMPT
    )
    
    # Filter tools by selected IDs; default to all if none specified
    selected_tools = []
    active_tool_meta = []
    tool_count = 0
    workflow_count = 0
    
    # Check hardcoded tools
    for e in DEMO_TOOL_REGISTRY:
        # ALWAYS include core system tools for state management and discovery
        is_core = e["id"] in ["query_capability_inventory", "remember_info", "extract_and_remember_hints"]
        if is_core or (not tool_ids or e["id"] in tool_ids):
            selected_tools.append(e["handler"])
            active_tool_meta.append({"id": e["id"], "name": e["name"], "description": e["description"]})
            tool_count += 1
            
    # Load dynamic tools and workflows
    if tool_ids:
        # 1. Check Tool Registry
        if _engine_manager.registry_svc:
            _engine_manager.sync_registry()
            
            for tid in tool_ids:
                if any(m["id"] == tid for m in active_tool_meta): continue
                    
                schema = _engine_manager.registry_svc.get_tool(tid)
                if schema:
                    lc_tool = tool_schema_to_langchain(schema)
                    if lc_tool:
                        selected_tools.append(lc_tool)
                        active_tool_meta.append({"id": tid, "name": schema.name, "description": schema.capability.description})
                        
                        is_wf = (schema.metadata or {}).get("entity_type") == "workflow" or tid.startswith("workflows.")
                        if is_wf: workflow_count += 1
                        else: tool_count += 1
                        logger.info(f"Loaded dynamic {'workflow' if is_wf else 'tool'}: {tid}")

        # 2. Check Workflow Engine (for workflows not in tool registry)
        if _engine_manager.engine and _engine_manager.engine.workflows:
            for tid in tool_ids:
                if any(m["id"] == tid for m in active_tool_meta): continue
                
                if tid in _engine_manager.engine.workflows:
                    wf_obj = _engine_manager.engine.workflows[tid]
                    
                    def create_wf_wrapper(w_id, w_name, w_desc):
                        @tool
                        def run_workflow_exec(inputs: str) -> str:
                            """Execute a specialized workflow."""
                            res = _engine_manager.engine._handle_workflow(inputs, workflow_id=w_id)
                            mem = res.get("final_memory", {})
                            if isinstance(mem, dict):
                                return str(mem.get("output") or mem.get("response") or mem)
                            return str(mem)
                        run_workflow_exec.name = f"wf__{w_id.replace('.', '__')}"
                        run_workflow_exec.description = f"Specialized Workflow: {w_name}. {w_desc}"
                        return run_workflow_exec

                    name = getattr(wf_obj, 'name', tid.replace("_", " ").title())
                    desc = "Execute a multi-agent orchestration workflow."
                    
                    wf_tool = create_wf_wrapper(tid, name, desc)
                    selected_tools.append(wf_tool)
                    active_tool_meta.append({"id": tid, "name": name, "description": desc})
                    workflow_count += 1
                    logger.info(f"Loaded workflow as tool: {tid}")

    if not selected_tools:
        # Always give the agent at least something to work with
        selected_tools = ALL_DEMO_TOOLS
        active_tool_meta = [{"id": e["id"], "name": e["name"], "description": e["description"]} for e in DEMO_TOOL_REGISTRY]
        tool_count = len(selected_tools)
        logger.warning("No valid tools selected — using fallback demo tools.")

    # --- Tool Segmentation ---
    # 1. Internal tools for graph nodes (Not visible to LLM)
    INTERNAL_TOOLS = ["remember_info", "extract_and_remember_hints"]
    internal_tool_map = {e["id"]: e["handler"] for e in DEMO_TOOL_REGISTRY if e["id"] in INTERNAL_TOOLS}
    
    # 2. Agent tools (Visible to LLM if thin-prompt doesn't hide them)
    agent_tools = []
    from langchain_core.tools import BaseTool
    for t in selected_tools:
        # Wrap everything in a standard check
        lc_tool = t
        if not isinstance(t, BaseTool) and callable(t):
             t_name = getattr(t, 'name', getattr(t, '__name__', str(t)))
             t_desc = getattr(t, 'description', getattr(t, '__doc__', "No description provided."))
             lc_tool = StructuredTool.from_function(func=t, name=t_name, description=t_desc)
        
        t_id = getattr(lc_tool, 'id', getattr(lc_tool, 'name', str(lc_tool))).lower()
        if not any(it in t_id for it in INTERNAL_TOOLS):
            agent_tools.append(lc_tool)

    # --- Performance Optimization: Thin Prompt Visibility ---
    MUST_BE_IN_PROMPT = ["query_capability_inventory", "get_current_weather", "calculate_math"]
    prompt_tools = []
    
    if len(agent_tools) > 5:
        for t in agent_tools:
            t_name = getattr(t, 'name', str(t)).lower()
            if any(cid in t_name for cid in MUST_BE_IN_PROMPT) or any(cid in t_name for cid in ["doc", "pdf", "search", "vision"]):
                prompt_tools.append(t)
        logger.info(f"Thin-Prompt: Using {len(prompt_tools)} tools for LLM reasoning.")
    else:
        prompt_tools = agent_tools
        logger.info(f"Full-Prompt: Using {len(prompt_tools)} tools.")

    _master_agent = ReactMasterAgent(
        definition=definition,
        model_provider=model_provider,
        tools=agent_tools
    )
    # Re-sync tool map after init to ensure names match exactly
    _master_agent.tool_map = {getattr(t, 'name', str(t)): t for t in agent_tools}
    # Add internal tools to tool_map so graph nodes can find them, but they aren't in the Agent's reasoning pool
    for tid, handler in internal_tool_map.items():
        if tid not in _master_agent.tool_map:
            _master_agent.tool_map[tid] = handler if isinstance(handler, BaseTool) else StructuredTool.from_function(func=handler, name=tid, description="INTERNAL")

    # Custom compile with graph persistence
    try:
        from langchain.agents import create_react_agent
    except ImportError:
        from langchain_classic.agents import create_react_agent
        
    from langchain_core.prompts import PromptTemplate
    
    prompt_template = PromptTemplate.from_template(DEMO_AGENT_PROMPT)
    _master_agent.graph = None 
    
    try:
        # Build optimized runnable
        react_runnable = create_react_agent(
            llm=model_provider,
            tools=prompt_tools,
            prompt=prompt_template
        )
        
        # We manually re-bind the nodes to ensure correct tool execution logic
        # Custom scratchpad formatter to avoid dependency issues with moving langchain modules
        def format_scratchpad(intermediate_steps):
            log = ""
            for action, observation in intermediate_steps:
                log += f"Thought: {action.log}\n"
                log += f"Action: {action.tool}\n"
                log += f"Action Input: {action.tool_input}\n"
                log += f"Observation: {observation}\n"
            return log

        async def preprocess_input(state):
            """Initial analysis of user input to categorize intent and extract immediate context."""
            user_input = state.get("input", "")
            if not user_input or not _master_agent:
                return {}

            prompt = f"""Analyze the User Input for intent and key information.
User Input: {user_input}

1. Categorize intent: (greeting, instruction, question, casual, or other)
2. Extract 'hints' (entities, preferences, settings, config).
   For each hint provide: label, description, reasoning.

Format as JSON:
{{
  "intent": "...",
  "hints": [{{ "label": "...", "description": "...", "reasoning": "..." }}]
}}

JSON Result:"""
            try:
                res = await _master_agent.model_provider.ainvoke(prompt)
                content = str(res.content if hasattr(res, 'content') else res).strip()
                if "{" in content and "}" in content:
                    found_json = json.loads(content[content.find("{"):content.rfind("}")+1])
                    new_hints = found_json.get("hints", [])
                    intent = found_json.get("intent", "other")
                    
                    current_hints = state.get("hints", []) or []
                    if new_hints:
                        current_hints.extend(new_hints)
                        logger.info(f"Pre-extracted hints: {new_hints}")
                    
                    meta = state.get("operational_metadata", {}) or {}
                    meta["last_intent"] = intent
                    
                    return {"hints": current_hints, "operational_metadata": meta}
                return {}
            except Exception as e:
                logger.error(f"Pre-processing failed: {e}")
                return {}
        async def run_agent(state):
            """Normal Path: LLM Execution"""
            try:
                # Truncate conversation history to avoid context overflow in local LLMs
                history = state.get("conversation_history", "")
                history_lines = history.strip().split("\n")
                if len(history_lines) > 10:
                    history = "\n".join(history_lines[-10:])
                
                # Format the intermediate steps into a ReAct scratchpad
                intermediate_steps = state.get("intermediate_steps", [])
                scratchpad = format_scratchpad(intermediate_steps)
                
                # Check for loops (too many intermediate steps)
                # Hard limit at 6 to prevent runaway in demo
                if len(intermediate_steps) >= 6:
                    logger.warning(f"CRITICAL: Loop detected for session. Forcing stop at 6 steps.")
                    return {"agent_outcome": AgentFinish(
                        return_values={"output": "I'm having trouble completing this task efficiently. I've stopped to prevent a loop. Is there a simpler way I can help?"},
                        log="Max steps (6) reached. Loop prevention triggered."
                    )}

                # REPETITION GUARD: Check if we are calling the same thing repeatedly
                if len(intermediate_steps) >= 2:
                    last_action = intermediate_steps[-1][0]
                    prev_action = intermediate_steps[-2][0]
                    # If action and input are identical to the previous step, it's a loop
                    if isinstance(last_action, AgentAction) and isinstance(prev_action, AgentAction):
                        if last_action.tool == prev_action.tool and last_action.tool_input == prev_action.tool_input:
                            logger.warning(f"REPETITION DETECTED: {last_action.tool}. Forcing termination.")
                            return {"agent_outcome": AgentFinish(
                                return_values={"output": "I noticed I was repeating the same action. I've stopped to avoid a loop. How else can I assist?"},
                                log="Tool repetition detected."
                            )}

                # Inject current structured state into the prompt
                state_json = json.dumps(state.get("structured_state", {}), indent=2)
                hints_json = json.dumps(state.get("hints", []), indent=2)
                
                chain_input = {
                    "input": state["input"],
                    "conversation_history": history,
                    "structured_state": state_json,
                    "hints_state": hints_json,
                    "agent_scratchpad": scratchpad,
                    "intermediate_steps": intermediate_steps
                }

                # Run the agent chain
                outcome = await react_runnable.ainvoke(chain_input)
                logger.info(f"Agent Outcome: {outcome}")
                return {"agent_outcome": outcome}
            except Exception as e:
                logger.error(f"Execution/Parsing Error: {e}")
                # FALLBACK: If we get a parsing error on a "Final Answer" or if the model just speaks, try to extract it
                err_msg = str(e)
                if "Final Answer:" in err_msg:
                    answer = err_msg.split("Final Answer:")[-1].strip()
                    return {"agent_outcome": AgentFinish(return_values={"output": answer}, log=err_msg)}
                
                # If it tried to call an internalized extraction tool, treat it as a greeting finish
                if "extract_and_remember_hints" in err_msg or "remember_info" in err_msg:
                    return {"agent_outcome": AgentFinish(
                        return_values={"output": "I've noted that! How else can I help you?"},
                        log="Model attempted internalized tool. Falling back to finish."
                    )}
                
                return {"agent_outcome": AgentFinish(
                    return_values={"output": f"I encountered a formatting error: {str(e)}. Please rephrase or try a different approach."},
                    log=f"Parser Error: {e}"
                )}

        async def execute_tool(state):
            current_steps = state.get("intermediate_steps", []) or []
            action = state["agent_outcome"]
            if not isinstance(action, AgentAction):
                return {"intermediate_steps": []}
            tool_name = action.tool
            if not tool_name:
                 return {"intermediate_steps": current_steps + [(action, "Error: No tool name provided.")]}
                 
            tool_obj = _master_agent.tool_map.get(tool_name)
            if not tool_obj:
                # If tool not found in prompt subset, check the full map (dynamic discovery)
                logger.warning(f"Tool '{tool_name}' not found. Available: {list(_master_agent.tool_map.keys())}")
                return {"intermediate_steps": current_steps + [(action, f"Error: Tool '{tool_name}' unknown.")]}
                    
            # Execute tool logic
            try:
                # Specific logic for remember_info to update state directly
                if tool_name == "remember_info":
                    params = action.tool_input
                    if isinstance(params, str):
                        try: params = json.loads(params)
                        except: params = {"key": params, "value": "unknown"}
                    
                    key = params.get("key")
                    value = params.get("value")
                    
                    current_state = state.get("structured_state", {}) or {}
                    current_state[key] = value
                    
                    return {
                        "intermediate_steps": current_steps + [(action, f"Stored {key}={value}")],
                        "structured_state": current_state
                    }

                obs = await tool_obj.ainvoke(action.tool_input) if hasattr(tool_obj, "ainvoke") else tool_obj.invoke(action.tool_input)
                return {"intermediate_steps": current_steps + [(action, str(obs))]}
            except Exception as e:
                return {"intermediate_steps": current_steps + [(action, f"Error executing tool {tool_name}: {str(e)}")]}

        async def update_history_node(state):
            """Appends the current turn to persistent history and CLEAR scratchpad."""
            outcome = state.get("agent_outcome")
            if outcome and hasattr(outcome, "return_values"):
                user_input = state.get("input", "")
                bot_output = outcome.return_values.get("output", "")
                new_history = state.get("conversation_history", "") + f"User: {user_input}\nAssistant: {bot_output}\n"
                return {
                    "conversation_history": new_history,
                    "intermediate_steps": [] # Reset for next turn
                }
            return {"intermediate_steps": []}
            
        async def auto_extract_knowledge(state):
            """Analyses the turn for interesting facts to add to structured_state."""
            user_input = state.get("input", "")
            bot_output = ""
            outcome = state.get("agent_outcome")
            if outcome and hasattr(outcome, "return_values"):
                bot_output = outcome.return_values.get("output", "")
                
            if not user_input or not _master_agent:
                 return {}

            # Optimization: Skip if bot output is a generic greeting
            GREETINGS_OR_HELP = ["hi ", "hello", "how can i help", "ai assistant"]
            if any(g in bot_output.lower() for g in GREETINGS_OR_HELP) and "i am " not in user_input.lower():
                return {}
                 
            # Run a quiet extraction via the LLM
            prompt = f"""You are a memory sync engine. Observe the interaction:
User: {user_input}
Assistant: {bot_output}

Extract NEW or UPDATED hints about the user or context.
For each hint, provide:
- label: A short name/key (e.g. "User Name")
- description: The core fact or preference
- reasoning: Why you labeled this (e.g. "User introduced himself")

Format as a JSON list under the key "hints".
Example: {{"hints": [{{ "label": "User Name", "description": "Siddharth", "reasoning": "Explicit introduction" }}]}}
If nothing new, return {{"hints": []}}.

JSON Result:"""
            try:
                # Direct LLM call for auto-sync
                res = await _master_agent.model_provider.ainvoke(prompt)
                content = str(res.content if hasattr(res, 'content') else res).strip()
                if "{" in content and "}" in content:
                    found_json = json.loads(content[content.find("{"):content.rfind("}")+1])
                    new_hints = found_json.get("hints", [])
                    if new_hints:
                        current_hints = state.get("hints", []) or []
                        # Simplistic merge: could be smarter about updates
                        current_hints.extend(new_hints)
                        logger.info(f"Auto-extracted hints: {new_hints}")
                        return {"hints": current_hints}
                return {}
            except Exception as e:
                logger.error(f"Auto-extraction failed: {e}")
                return {}
        
        # Re-compile logic (simplified for this route)
        from langgraph.graph import StateGraph, END
        from common_lib.modules.orchestration.agent.react_master_agent import ReActState, AgentAction, AgentFinish
        
        wf = StateGraph(ReActState)
        wf.add_node("preprocess_input", preprocess_input)
        wf.add_node("agent_thinking", run_agent)
        wf.add_node("execute_tool", execute_tool)
        wf.add_node("finalize_turn", update_history_node)
        wf.add_node("auto_extract", auto_extract_knowledge)
        wf.set_entry_point("preprocess_input")
        
        wf.add_edge("preprocess_input", "agent_thinking")
        
        def router(state):
            if isinstance(state["agent_outcome"], AgentFinish):
                return "auto_extract" # Intermediate step before finalizing
            return "execute_tool"
            
        wf.add_conditional_edges("agent_thinking", router)
        wf.add_edge("execute_tool", "agent_thinking")
        wf.add_edge("auto_extract", "finalize_turn")
        wf.add_edge("finalize_turn", END)
        
        # Enable persistence
        _master_agent.graph = wf.compile(checkpointer=_checkpointer)
    except Exception as e:
        logger.error(f"Failed performance-optimized compile: {e}")
        # Build standard graph with persistence
        _master_agent.set_checkpointer(_checkpointer)
        _master_agent._compile_graph()

    # --- Update Local Active Config for UI ---
    global _active_session_config
    # Try to reuse existing session_id if available (persistence-friendly)
    curr_id = _active_session_config.get("session_id") if _active_session_config else None
    
    _active_session_config = {
        "model_path": model_path or os.getenv("LOCAL_LLM_MODEL_PATH", "default"),
        "agent_id": agent_id,
        "agent_display_name": definition.identity.display_name,
        "tools": active_tool_meta,
        "tool_count": tool_count,
        "workflow_count": workflow_count,
        "session_id": curr_id or f"session-{datetime.now().strftime('%Y%m%d%H%M')}-{agent_id[:4]}"
    }
    logger.info(f"Deployed Agent Active Config: Ready for thread {_active_session_config['session_id']}")

# Initial load
try:
    load_agent()
except Exception as e:
    logger.error(f"Initial agent load failed: {e}")

class DeployRequest(BaseModel):
    model_path: Optional[str] = None
    provider: Optional[str] = "local_llama"
    agent_id: Optional[str] = "demo_master_agent"
    tool_ids: Optional[list] = None  # None = use all available tools

@router.get("/available_tools")
async def get_available_tools():
    """Returns all tools that can be selected, grouped by category."""
    groups = {}
    
    # 1. Add hardcoded tools
    for t in DEMO_TOOL_REGISTRY:
        cat = t.get("category", "demo")
        if cat not in groups:
            groups[cat] = []
        groups[cat].append({
            "id": t["id"],
            "name": t["name"],
            "description": t["description"]
        })
        
    # 2. Add dynamic tools if registry is available
    if _engine_manager and _engine_manager.registry_svc:
        dynamic_tools = _engine_manager.registry_svc.get_tools_by_category()
        for cat, tools in dynamic_tools.items():
            if cat not in groups:
                groups[cat] = []
            for t in tools:
                # Avoid duplicates with hardcoded
                if any(ext["id"] == t["id"] for ext in groups[cat]):
                    continue
                
                # Segregate: Filter out workflows from the tool list
                if (t.get("metadata") or {}).get("entity_type") == "workflow" or t.get("category") == "workflows":
                    continue
                    
                groups[cat].append({
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"]
                })
                
    # Format for frontend
    result = []
    for cat_id, tools in groups.items():
        result.append({
            "id": cat_id,
            "name": cat_id.replace("_", " ").title(),
            "tools": tools
        })
        
    return sorted(result, key=lambda x: x["name"])

@router.get("/available_workflows")
async def get_available_workflows():
    """Returns all workflow definitions grouped by category."""
    try:
        workflows = common_memory.list_workflow_definitions()
        groups = {}
        
        for w in workflows:
            artifacts = w.get("artifacts", {})
            yaml_path = artifacts.get("yaml_path", "")
            
            # Categorize by parent folder in templates/workflows/
            # Expected path: workflows/<category_name>/<filename>.yaml
            category = "General"
            if yaml_path and "/" in yaml_path:
                parts = yaml_path.split("/")
                # If path starts with workflows/, the next part is the category
                if parts[0] == "workflows" and len(parts) >= 3:
                    category = parts[1].replace("_", " ").title()
                elif len(parts) >= 2:
                    # Fallback to direct parent if not in workflows/ subfolder
                    category = parts[-2].replace("_", " ").title()
            
            if category not in groups:
                groups[category] = []
                
            groups[category].append({
                "id": w["id"],
                "name": w.get("name") or w["id"].replace("_", " ").title(),
                "description": w.get("definition", {}).get("description", "Workflow execution graph.")
            })
            
        result = []
        for cat_name, entries in groups.items():
            result.append({
                "id": f"wf_{cat_name.lower().replace(' ', '_')}",
                "name": f"{cat_name} (Workflows)",
                "items": entries,
                "type": "workflow"
            })
        
        return sorted(result, key=lambda x: x["name"])
    except Exception as e:
        logger.error(f"Failed to fetch workflows: {e}")
        return []

@router.get("/available_config")
async def get_available_config():
    if not _engine_manager:
        return {"models": [], "agents": []}
    return {
        "models": _engine_manager.list_available_models(),
        "agents": _engine_manager.list_available_agents()
    }

@router.get("/session_info")
async def get_session_info():
    if not _engine_manager:
        return {"status": "inactive"}
    base = _engine_manager.get_session_info()
    # Overlay the demo-layer config (tools, system_prompt, persona)
    return {**base, **_active_session_config}


@router.post("/deploy")
async def deploy_config(req: DeployRequest):
    try:
        load_agent(
            model_path=req.model_path,
            provider=req.provider,
            agent_id=req.agent_id,
            tool_ids=req.tool_ids
        )
        return {"status": "success", "info": await get_session_info()}
    except Exception as e:
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}

class MessageRequest(BaseModel):
    message: str
    session_id: str

async def stream_agent_generator(request_data: MessageRequest) -> AsyncGenerator[str, None]:
    try:
        if not _master_agent or not _master_agent.graph:
             yield f"data: {json.dumps({'event_type': 'error', 'content': 'Agent not loaded. Click Deploy first.'})}\n\n"
             return

        # Prepare initial turn state
        initial_input = {
            "input": request_data.message,
            "intermediate_steps": []
        }
        
        # If it's the first turn for this thread, sync the operational metadata
        current_state = _master_agent.graph.get_state({"configurable": {"thread_id": request_data.session_id}})
        if not current_state.values.get("operational_metadata"):
             initial_input["operational_metadata"] = {
                 "agent_name": _active_session_config.get("agent_display_name", "Master Agent"),
                 "model": _active_session_config.get("model_path", "unknown"),
                 "deployed_at": datetime.now().isoformat(),
                 "status": "active"
             }

        stream = _master_agent.graph.astream_events(
            initial_input,
            config={
                "configurable": {"thread_id": request_data.session_id},
                "recursion_limit": 25
            },
            version="v2"
        )
        
        final_answer = None
        step = 0

        def ts() -> str:
            return datetime.now().strftime("%H:%M:%S.%f")[:-3]

        def emit_trace(category: str, title: str, body: str = "", metadata: dict = None) -> str:
            nonlocal step
            step += 1
            ts_str = ts()
            
            # Terminal log with category-specific colors
            prefix = f"[{ts_str}] Step {step}"
            if category == "think":
                logger.info(f"{prefix} - {BOLD}{BLUE}THINK{RESET}: {title}")
            elif category == "tool_call":
                logger.info(f"{prefix} - {BOLD}{GREEN}TOOL CALL{RESET}: {title}")
            elif category == "tool_result":
                logger.info(f"{prefix} - {BOLD}{GREEN}TOOL RESULT{RESET}: {title}")
            elif category == "error":
                logger.info(f"{prefix} - {BOLD}{RED}ERROR{RESET}: {title}")
            elif category == "decision":
                logger.info(f"{prefix} - {BOLD}{CYAN}DECISION{RESET}: {title}")
            else:
                logger.info(f"{prefix} - {GRAY}{title}{RESET}")

            def sanitize(val):
                """Non-recursive shallow sanitize for top-level metadata dict."""
                if isinstance(val, dict):
                    return {str(k): (v if isinstance(v, (str, int, float, bool, type(None))) else str(v)) for k, v in val.items()}
                return str(val)

            payload = {
                "event_type": "trace",
                "step": step,
                "ts": ts_str,
                "category": category,
                "title": title,
                "body": body,
                "metadata": sanitize(metadata) if isinstance(metadata, dict) else {}
            }
            # Still use default=str as a final safety net for any nesting
            return f"data: {json.dumps(payload, default=str)}\n\n"

        # Emit initial trace entry with version marker
        logger.info(f"{BOLD}{GREEN}>>> [DEMO ROUTE {VERSION_ID}] Starting new stream <<< {RESET}")
        yield emit_trace("transition", f"▶ Agent started ({VERSION_ID})", f'Input: "{request_data.message}"')

        accumulated_thought = ""

        async for event in stream:
            kind = event.get("event", "")
            name = event.get("name", "")
            
            # ── LLM starts generating ──────────────────────────────────────
            if kind == "on_llm_start" or kind == "on_chat_model_start":
                inputs = event.get("data", {}).get("input", {})
                prompt_preview = ""
                if isinstance(inputs, dict):
                    msgs = inputs.get("messages", [])
                    if msgs:
                        last = msgs[-1] if isinstance(msgs[-1], list) else msgs
                        for m in (last if isinstance(last, list) else [last]):
                            content = getattr(m, "content", None) or (m.get("content", "") if isinstance(m, dict) else "")
                            if content:
                                prompt_preview = str(content)[:500]
                yield emit_trace("transition", f"🧠 LLM invoked: {name or 'model'}", prompt_preview)
            
            # ── LLM streaming token ────────────────────────────────────────
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                content = getattr(chunk, "content", None) or ""
                if content:
                    accumulated_thought += content
                    # Stream to chat bubbles
                    yield f"data: {json.dumps({'event_type': 'thought', 'content': str(content)}, default=str)}\n\n"
            
            # ── LLM finished one generation ────────────────────────────────
            elif kind == "on_chat_model_end":
                if accumulated_thought:
                    yield emit_trace("think", "💭 Model reasoning", accumulated_thought.strip())
                    accumulated_thought = ""

            # ── Tool about to be called ────────────────────────────────────
            elif kind == "on_tool_start":
                tool_input = event.get("data", {}).get("input", "")
                if not isinstance(tool_input, str):
                    tool_input = json.dumps(tool_input, default=str)
                yield f"data: {json.dumps({'event_type': 'tool_start', 'content': f'🔧 Using tool: {name}', 'tool_input': tool_input}, default=str)}\n\n"
                yield emit_trace(
                    "tool_call",
                    f"🔧 Tool called: {name}",
                    tool_input,
                    {"tool_name": name}
                )
                
            # ── Tool returned ──────────────────────────────────────────────
            elif kind == "on_tool_end":
                output = event.get("data", {}).get("output", "")
                if not isinstance(output, str):
                    output = json.dumps(output, default=str)
                yield f"data: {json.dumps({'event_type': 'tool_end', 'content': str(output)}, default=str)}\n\n"
                yield emit_trace(
                    "tool_result",
                    f"📥 Tool result: {name}",
                    str(output),
                    {"tool_name": name}
                )

            # ── Chain/node transitions ─────────────────────────────────────
            elif kind == "on_chain_start":
                # STRICT FILTER: Only show actual graph nodes
                ALLOWED_NODES = ["preprocess_input", "agent_thinking", "execute_tool", "auto_extract", "finalize_turn", "deploy_config"]
                if name in ALLOWED_NODES:
                    inputs = event.get("data", {}).get("input", {})
                    input_str = json.dumps(inputs, indent=2, default=str) if isinstance(inputs, dict) else str(inputs)
                    title_map = {
                        "preprocess_input": "🔍 Analyzing User Input",
                        "agent_thinking": "🏢 Agent Reasoning",
                        "execute_tool": "🔧 Executing Tool",
                        "auto_extract": "🧠 Extracting Knowledge",
                        "finalize_turn": "💾 Saving History"
                    }
                    yield emit_trace("transition", title_map.get(name, f"→ Entering node: {name}"), f"Input: {input_str[:500]}...")

            elif kind == "on_chain_end":
                data = event.get("data", {})
                output = data.get("output", {})
                
                # Check for agent outcome (Final Answer)
                if isinstance(output, dict):
                    agent_outcome = output.get("agent_outcome")
                    if agent_outcome and hasattr(agent_outcome, "return_values"):
                        # Extract answer if available
                        ans = agent_outcome.return_values.get("output", "")
                        if ans: final_answer = ans
                
                # STRICT FILTER: Only show actual graph nodes
                ALLOWED_NODES = ["preprocess_input", "agent_thinking", "execute_tool", "auto_extract", "finalize_turn", "deploy_config"]
                if name in ALLOWED_NODES:
                    output_str = json.dumps(output, indent=2, default=str) if isinstance(output, dict) else str(output)
                    yield emit_trace("transition", f"🏁 Exiting node: {name}", f"Output: {output_str[:1000]}")

            # ── Error Handling ─────────────────────────────────────────────
            elif kind in ("on_llm_error", "on_tool_error", "on_chain_error"):
                error = event.get("data", {}).get("error", "Unknown error")
                yield emit_trace("error", f"❌ Error in {name or kind}", str(error))
                logger.error(f"Event error in {name}: {error}")
        
        # Emit the final bot answer
        if final_answer:
            yield emit_trace("decision", "✅ Final Answer", str(final_answer))
            yield f"data: {json.dumps({'event_type': 'agent_complete', 'content': str(final_answer)}, default=str)}\n\n"
        else:
            # If we reached the end without a final answer but no exception was raised, 
            # might be a graph routing issue or early termination.
            yield emit_trace("error", "⚠️ Agent terminated without final answer")
            yield f"data: {json.dumps({'event_type': 'agent_complete', 'content': ''}, default=str)}\n\n"

    except Exception as e:
        logger.error(traceback.format_exc())
        error_event = json.dumps({"event_type": "error", "content": f"Error: {e}"}, default=str)
        yield f"data: {error_event}\n\n"

@router.get("/session_state/{session_id}")
async def get_session_state(session_id: str):
    """Retrieve the current internal state of the agent for a given session."""
    if not _master_agent or not _master_agent.graph:
        return {"error": "Agent not loaded"}
    
    config = {"configurable": {"thread_id": session_id}}
    state = _master_agent.graph.get_state(config)
    
    # Return a clean version of the state
    return {
        "session_id": session_id,
        "history": state.values.get("conversation_history", ""),
        "intermediate_steps": state.values.get("intermediate_steps", []),
        "structured_state": state.values.get("structured_state", {}),
        "hints": state.values.get("hints", []),
        "operational_metadata": state.values.get("operational_metadata", {}),
        "last_input": state.values.get("input", ""),
        "updated_at": str(state.config.get("configurable", {}).get("checkpoint_id", "initial"))
    }

class StateUpdateRequest(BaseModel):
    history: Optional[str] = None
    intermediate_steps: Optional[list] = None
    structured_state: Optional[dict] = None
    hints: Optional[list] = None
    operational_metadata: Optional[dict] = None

@router.post("/session_state/{session_id}")
async def update_session_state(session_id: str, req: StateUpdateRequest):
    """Manually override the agent's memory/history."""
    if not _master_agent or not _master_agent.graph:
        return {"error": "Agent not loaded"}
    
    config = {"configurable": {"thread_id": session_id}}
    updates = {}
    if req.history is not None:
        updates["conversation_history"] = req.history
    if req.intermediate_steps is not None:
        updates["intermediate_steps"] = req.intermediate_steps
    if req.structured_state is not None:
        updates["structured_state"] = req.structured_state
    if req.hints is not None:
        updates["hints"] = req.hints
    if req.operational_metadata is not None:
        updates["operational_metadata"] = req.operational_metadata
        
    try:
        # Use LangGraph's update_state to injection manual context/corrections
        _master_agent.graph.update_state(config, updates)
        return {"status": "success", "message": "Memory updated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/stream_message")
async def stream_message(req: MessageRequest):
    return StreamingResponse(
        stream_agent_generator(req),
        media_type="text/event-stream"
    )
