"""
agents/runtime/tools/builtins.py
----------------------------------
Built-in @tool definitions for the agent runtime.

All context-dependent tools use the ``RuntimeContext`` dataclass instead of
module-level globals, making them safe to instantiate multiple times with
different configurations — which is exactly what we need when running
multiple independent custom agents concurrently.

Public API:
    build_builtin_tools(ctx: RuntimeContext) -> List[BaseTool]
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Context container — the only way tools receive session context.
# Adding new context fields here (e.g. skill_registry, prompt_store) will
# support future skill/workflow runtimes without touching the API surface.
# ---------------------------------------------------------------------------

@dataclass
class RuntimeContext:
    """Runtime context passed to context-aware tools at load time."""
    session_config:  Dict[str, Any] = field(default_factory=dict)
    engine_manager:  Optional[Any]  = None
    model_provider:  Optional[Any]  = None
    tool_registry:   List[Dict]     = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stateless tools
# ---------------------------------------------------------------------------

@tool
def get_current_weather(location: str) -> str:
    """Get the current weather in a given location."""
    loc = location.lower()
    if "san francisco" in loc:
        return "It's 60°F and foggy."
    if "new york" in loc:
        return "It's 80°F and sunny."
    return "It's 72°F and pleasant."


@tool
def calculate_math(expression: str) -> str:
    """Safely evaluate a numeric math expression.

    ONLY pass valid math like '10 + 5' or 'max(10, 20)'.
    Do NOT pass words or sentences.
    """
    if not re.search(r"[0-9+\-*/().]", expression):
        return "Error: Expression does not look like math."
    try:
        safe = {"abs": abs, "round": round, "min": min, "max": max}
        return str(eval(expression, {"__builtins__": None}, safe))  # noqa: S307
    except Exception as exc:
        return f"Error: {exc}"


@tool
def remember_info(key: str, value: Any) -> str:
    """Store a key/value fact or preference in the agent's structured state."""
    return f"Remembered: {key} = {value}"


# ---------------------------------------------------------------------------
# Context-aware tool factories
# ---------------------------------------------------------------------------

def _make_capability_query_tool(ctx: RuntimeContext):
    """Return a query_capability_inventory tool bound to *ctx*."""

    @tool
    def query_capability_inventory(query: str = "current") -> str:
        """Search and discover tools, skills, and workflows available to this agent.

        Pass an exact tool ID for the full schema, or keywords (e.g. 'pdf',
        'image', 'summarise') to find matching capabilities.
        """
        query_lc = (query or "current").lower().strip().strip("'\"")
        is_search = query_lc not in {"current", "session", "active", "all"}
        all_caps: List[Dict] = []

        # Builtins
        for t in ctx.tool_registry:
            all_caps.append({
                "id": t["id"], "name": t["name"],
                "description": t["description"], "type": "tool", "source": "builtin",
            })

        # Dynamic registry tools
        em = ctx.engine_manager
        if em and getattr(em, "registry_svc", None):
            try:
                for _cat, tools in em.registry_svc.get_tools_by_category().items():
                    for t in tools:
                        all_caps.append({
                            "id": t["id"], "name": t["name"],
                            "description": t["description"],
                            "type": t.get("type", "tool"), "source": "registry",
                            "schema": t.get("capability", {}).get("arguments", []),
                        })
            except Exception:
                pass

        # Workflows from common_memory
        try:
            from app.core.common_lib_integration import common_memory
            for w in common_memory.list_workflow_definitions():
                all_caps.append({
                    "id": w["id"], "name": w.get("name") or w["id"],
                    "description": "Workflow / composite process",
                    "type": "workflow", "source": "memory",
                    "schema": w.get("inputs", []),
                })
        except Exception:
            pass

        whitelist    = ctx.session_config.get("whitelist", [])
        use_disc     = ctx.session_config.get("use_mcp_discovery", False)
        global_srch  = ctx.session_config.get("global_search_enabled", False)

        if is_search:
            keywords = [k for k in query_lc.replace("-", " ").split() if len(k) > 1]
            exact = next((c for c in all_caps if c["id"].lower() == query_lc), None)
            if exact:
                enabled = exact["id"] in whitelist or not use_disc
                label   = "[ENABLED]" if enabled else "[AVAILABLE — ADMIN ACTION REQUIRED]"
                out     = f"### {label} {exact['name']} (`{exact['id']}`)\n"
                out    += f"**Description**: {exact['description']}\n"
                schema = exact.get("schema")
                if schema and isinstance(schema, list):
                    out += "**Arguments**:\n"
                    for arg in schema:
                        out += f"- `{arg.get('name')}` ({arg.get('type')}): {arg.get('description')}\n"
                return out

            enabled_m, available_m = [], []
            for cap in all_caps:
                text = f"{cap['id']} {cap['name']} {cap['description']}".lower()
                if any(k in text for k in keywords):
                    if cap["id"] in whitelist or not use_disc:
                        enabled_m.append(cap)
                    elif global_srch:
                        available_m.append(cap)

            if not enabled_m and not available_m:
                return f"No capabilities found matching '{query}'."

            out = f"### Discovery Results for '{query}'\n"
            if enabled_m:
                out += "\n#### [ENABLED]\n"
                out += "".join(f"- **{m['name']}** (`{m['id']}`): {m['description']}\n" for m in enabled_m[:8])
            if available_m:
                out += "\n#### [AVAILABLE — ADMIN ACTION REQUIRED]\n"
                out += "".join(f"- **{m['name']}** (`{m['id']}`): {m['description']}\n" for m in available_m[:8])
            return out

        # Default: list active session tools
        agent_name   = ctx.session_config.get("agent_display_name", "Agent")
        active_tools = ctx.session_config.get("tools", [])
        out = f"### Active Capabilities for '{agent_name}'\n"
        if not active_tools:
            return out + "No tools are currently active."
        out += "".join(
            f"- **{t['name']}** (`{t['id']}`): {t['description'][:100]}\n"
            for t in active_tools
        )
        return out

    return query_capability_inventory


def _make_hint_extractor_tool(ctx: RuntimeContext):
    """Return an extract_and_remember_hints tool bound to *ctx*."""

    @tool
    async def extract_and_remember_hints(text: str) -> str:
        """Analyse text to extract user names, preferences, and context labels."""
        if not ctx.model_provider:
            return "Error: model provider not initialised."
        prompt = (
            "Analyse the interaction and extract hints about the user.\n"
            "Return JSON: {\"hints\": [{\"label\": \"...\", \"description\": \"...\", \"reasoning\": \"...\"}]}\n\n"
            f"Interaction: {text}\n\nJSON:"
        )
        try:
            res     = await ctx.model_provider.ainvoke(prompt)
            content = str(getattr(res, "content", res)).strip()
            if "{" in content:
                raw = json.loads(content[content.find("{") : content.rfind("}") + 1])
                return f"Hints extracted:\n{json.dumps(raw.get('hints', []), indent=2)}"
            return "No clear hints extracted."
        except Exception as exc:
            return f"Extraction failed: {exc}"

    return extract_and_remember_hints


# ---------------------------------------------------------------------------
# Public factory — call this at load-agent time
# ---------------------------------------------------------------------------

def build_builtin_tools(ctx: RuntimeContext) -> List[Any]:
    """Return the complete wired list of LangChain tool objects for *ctx*."""
    return [
        get_current_weather,
        calculate_math,
        remember_info,
        _make_capability_query_tool(ctx),
        _make_hint_extractor_tool(ctx),
    ]
