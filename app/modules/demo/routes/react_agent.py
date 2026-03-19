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
from app.agentic.master_agent import MasterAgent, format_scratchpad

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
    
    # Normalize query string (strip redundant quotes which LLMs often add)
    query_lc = (query or "current").lower().strip().strip("'").strip('"').strip()
    is_search = query_lc not in ["current", "session", "active", "all"]
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
                            "type": t.get("type", "tool"),
                            "source": "registry",
                            "schema": t.get("capability", {}).get("arguments", [])
                        })
            except Exception: pass
            
        try:
            workflows = common_memory.list_workflow_definitions()
            for w in workflows:
                all_capabilities.append({
                    "id": w['id'], 
                    "name": w.get('name') or w['id'], 
                    "description": "Workflow execution or composite process", 
                    "type": "workflow",
                    "source": "memory",
                    "schema": w.get("inputs", [])
                })
        except Exception: pass

    # 2. If it's a search, filter the results
    if is_search:
        matches = []
        # Support full query match OR keyword match
        keywords = [k for k in query_lc.replace("-", " ").replace(".", " ").split() if len(k) > 1]
        
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

### CURRENT STRATEGY:
{strategy}

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
    tool_ids: list = None,
    system_prompt: str = None,
    guardrails: list = None,
    preload: bool = True
) -> ReactMasterAgent:
    """Dynamically loads or reloads the master agent using the Modular service."""
    global _engine_manager, _master_agent
    
    # 1. Setup Engine & LLM
    if _engine_manager is None:
        class DummyContext:
            def __init__(self):
                self.adapter = None
                self.service = None
        _engine_manager = EngineManager(DummyContext())
    
    env_model = os.getenv("LOCAL_LLM_MODEL_PATH") or os.getenv("LOCAL_HF_MODEL_PATH")
    env_provider = os.getenv("LLM_PROVIDER_TYPE", provider)
    
    _engine_manager.setup(
        target_files=[], 
        model_path=env_model or model_path, 
        provider_type=env_provider,
        preload=preload
    )
    model_provider = LangChainModelAdapter(provider=_engine_manager.main_llm)
    
    # 2. Configure Service (Modular Prompts/Guardrails)
    service = MasterAgent(
        model_provider=model_provider, 
        engine_manager=_engine_manager,
        system_prompt=system_prompt,
        guardrails=guardrails
    )
    
    # 3. Tool Preparation
    selected_tools = []
    active_tool_meta = []
    for e in DEMO_TOOL_REGISTRY:
        if not tool_ids or e["id"] in tool_ids:
            if e.get("handler"):
                selected_tools.append(e["handler"])
                active_tool_meta.append({"id": e["id"], "name": e["name"], "description": e["description"]})
            
    if tool_ids and _engine_manager.registry_svc:
        _engine_manager.sync_registry()
        for tid in tool_ids:
            if any(m["id"] == tid for m in active_tool_meta): continue
            schema = _engine_manager.registry_svc.get_tool(tid)
            if schema:
                lc_tool = tool_schema_to_langchain(schema)
                if lc_tool:
                    selected_tools.append(lc_tool)
                    active_tool_meta.append({"id": tid, "name": schema.name, "description": schema.capability.description})

    # 4. COMPILE LANGGRAPH (Modular Reasoning nodes)
    from langgraph.graph import StateGraph, END
    workflow = StateGraph(ReActState)
    
    workflow.add_node("preprocess_input", service.preprocess_input)
    async def agent_thinking_node(state):
        return await service.run_agent(state, selected_tools)
    
    workflow.add_node("agent_thinking", agent_thinking_node)
    
    async def execute_tool_node(state):
        current_steps = state.get("intermediate_steps", []) or []
        action = state["agent_outcome"]
        if not isinstance(action, AgentAction): return {"intermediate_steps": []}
        t_name = action.tool
        if t_name == "query_capability_inventory":
            obs = service.query_capability_inventory(action.tool_input)
            return {"intermediate_steps": current_steps + [(action, obs)]}
        t_obj = next((t for t in selected_tools if getattr(t, 'name', '') == t_name or getattr(t, '__name__', '') == t_name), None)
        if t_obj:
            try:
                obs = await t_obj.ainvoke(action.tool_input) if hasattr(t_obj, "ainvoke") else t_obj.invoke(action.tool_input)
                if t_name == "remember_info":
                    try:
                        params = action.tool_input
                        if isinstance(params, str): params = json.loads(params)
                        k, v = params.get("key"), params.get("value")
                        if k and v:
                            cur = state.get("structured_state", {}) or {}
                            cur[k] = v
                            return {"intermediate_steps": current_steps + [(action, str(obs))], "structured_state": cur}
                    except: pass
                return {"intermediate_steps": current_steps + [(action, str(obs))]}
            except Exception as e:
                return {"intermediate_steps": current_steps + [(action, f"Error: {str(e)}")]}
        return {"intermediate_steps": current_steps + [(action, f"Error: Tool {t_name} unknown")]}

    workflow.add_node("execute_tool", execute_tool_node)
    
    async def auto_extract_node(state):
        """Hidden node to pick up hints after the bot answers."""
        try:
            user_input = state.get("input", "")
            bot_output = state.get("agent_outcome", {}).return_values.get("output", "")
            if not user_input or not bot_output: return {}
            
            prompt = f"""You are a memory engine. Interaction:
User: {user_input}
Assistant: {bot_output}

Extract NEW or UPDATED hints (label, description, reasoning).
Format as JSON list: {{"hints": [{{ "label": "...", "description": "...", "reasoning": "..." }}]}}
If nothing new, return {{"hints": []}}.

JSON Result:"""
            res = await service.model_provider.ainvoke(prompt)
            content = str(res.content if hasattr(res, 'content') else res).strip()
            if "{" in content:
                found = json.loads(content[content.find("{"):content.rfind("}")+1])
                new_hints = found.get("hints", [])
                if new_hints:
                    cur = state.get("hints", []) or []
                    cur.extend(new_hints)
                    return {"hints": cur}
        except: pass
        return {}

    workflow.add_node("auto_extract", auto_extract_node)
    
    async def finalize_turn_node(state):
        """Update history and clear scratchpad."""
        outcome = state.get("agent_outcome")
        if outcome and hasattr(outcome, "return_values"):
            user_input = state.get("input", "")
            bot_output = outcome.return_values.get("output", "")
            new_history = state.get("conversation_history", "") + f"User: {user_input}\nAssistant: {bot_output}\n"
            return {"conversation_history": new_history, "intermediate_steps": []}
        return {"intermediate_steps": []}
    
    workflow.add_node("finalize_turn", finalize_turn_node)

    # STRUCTURE EDGES
    workflow.set_entry_point("preprocess_input")
    workflow.add_edge("preprocess_input", "agent_thinking")
    workflow.add_conditional_edges("agent_thinking", lambda s: "auto_extract" if isinstance(s["agent_outcome"], AgentFinish) else "execute_tool")
    workflow.add_edge("execute_tool", "agent_thinking")
    workflow.add_edge("auto_extract", "finalize_turn")
    workflow.add_edge("finalize_turn", END)

    # Global compilation
    _master_agent = ReactMasterAgent(
        definition=AgentDefinition(
            identity=AgentIdentity(
                agent_name=agent_id, 
                display_name="Master Agent",
                version="1.0.0",
                status=Status.ACTIVE,
                owner="admin"
            ),
            type=AgentType(
                role=AgentRole.ORCHESTRATOR,
                secondary_roles=[],
                reasoning_level=ReasoningLevel.ANALYTICAL,
                autonomy=AutonomyLevel.BOUNDED
            ),
            system_prompt_override=service.get_formatted_prompt()
        ),
        model_provider=model_provider,
        tools=selected_tools
    )
    _master_agent.graph = workflow.compile(checkpointer=_checkpointer)
    
    global _active_session_config
    _active_session_config = {
        "agent_id": agent_id,
        "tools": active_tool_meta,
        "session_id": f"session-{datetime.now().strftime('%m%d%H%M')}"
    }
    
    logger.info(f"Deployed modular agent '{agent_id}'.")
    return _master_agent


# Initial boot-up load
try:
    from app.core.settings import get_settings
    _settings = get_settings()
    # Always call load_agent to initialize engine_manager/registry, 
    # but only preload model if setting is enabled.
    load_agent(preload=_settings.PRELOAD_LLM)
    if not _settings.PRELOAD_LLM:
        logger.info("Engine initialized; skipping initial LLM preload per settings.")
except Exception as e:
    logger.error(f"Initial agent load check failed: {e}")

class DeployRequest(BaseModel):
    model_path: Optional[str] = None
    provider: Optional[str] = "local_llama"
    agent_id: Optional[str] = "demo_master_agent"
    tool_ids: Optional[list] = None
    system_prompt: Optional[str] = None
    guardrails: Optional[list] = None

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
            tool_ids=req.tool_ids,
            system_prompt=req.system_prompt,
            guardrails=req.guardrails
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
