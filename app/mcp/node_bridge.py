"""Dynamic @node → MCP tool bridge.

Registers every discovered @node wrapper as an individual MCP tool so
that AI agents can call backend functionality directly. Uses `exec` to
build functions with the exact parameter names + types from each node's
input_schema, so FastMCP generates proper JSON Schema for the LLM.

Usage:
    from app.mcp.node_bridge import register_dynamic_node_tools
    register_dynamic_node_tools(mcp_instance)   # adds 2000+ tools
"""

import asyncio
import importlib
import logging
import re
from typing import Any, Dict, List, Optional, Union, get_args, get_origin

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("node_bridge")

# ---------------------------------------------------------------------------
# Type-string → Python-type → exec-annotation conversion
# ---------------------------------------------------------------------------

_BASE_TYPES: Dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
    "bytes": bytes,
    "Any": Any,
    "None": type(None),
}


def _parse_type_str(raw: Any) -> Any:
    """Parse an input_schema type string like 'Optional[List[str]]' into a Python type.

    input_schema values can be strings ('str', 'Optional[int]') OR dicts
    with a 'type' key (JSON Schema format). Handle both.
    """
    if isinstance(raw, dict):
        raw = raw.get("type", "str")
    if not isinstance(raw, str):
        return str
    raw = raw.strip()

    if raw.startswith("Optional["):
        inner = raw[9:-1].strip()
        return Optional[_parse_type_str(inner)]
    if raw.startswith("List["):
        inner = raw[5:-1].strip()
        return List[_parse_type_str(inner)]
    if raw.startswith("Dict["):
        inner = raw[5:-1].strip()
        depth = 0
        comma = -1
        for i, c in enumerate(inner):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
            elif c == "," and depth == 0:
                comma = i
                break
        if comma > 0:
            kt = _parse_type_str(inner[:comma])
            vt = _parse_type_str(inner[comma + 1 :])
            return Dict[kt, vt]
        return dict
    if raw.startswith("Tuple["):
        inners = raw[6:-1].split(",")
        args = tuple(_parse_type_str(x.strip()) for x in inners)
        from typing import Tuple

        return Tuple[args]
    return _BASE_TYPES.get(raw, str)


def _type_to_expr(tp: Any) -> str:
    """Convert a Python type object to a string expression safe for exec()."""
    origin = get_origin(tp)
    args = get_args(tp)

    # Python 3.11+ represents Optional[X] as Union[X, None]
    if origin is Union and type(None) in args:
        inners = [a for a in args if a is not type(None)]
        inner_expr = (
            _type_to_expr(inners[0])
            if len(inners) == 1
            else ", ".join(_type_to_expr(a) for a in inners)
        )
        return f"Optional[{inner_expr}]"
    if origin is list:
        inner = args[0] if args else Any
        return f"List[{_type_to_expr(inner)}]"
    if origin is dict:
        kt = args[0] if len(args) > 0 else str
        vt = args[1] if len(args) > 1 else Any
        return f"Dict[{_type_to_expr(kt)}, {_type_to_expr(vt)}]"
    if origin is tuple:
        inners = ", ".join(_type_to_expr(a) for a in args)
        return f"Tuple[{inners}]"

    name = getattr(tp, "__name__", None)
    if name:
        return name
    return "Any"


# ---------------------------------------------------------------------------
# Function resolution
# ---------------------------------------------------------------------------


def _resolve_func(module, qualname: str) -> Any:
    """Resolve a callable from a module by dotted qualname (e.g. Class.method)."""
    parts = qualname.split(".")
    obj = module
    for part in parts:
        obj = getattr(obj, part)
    return obj


def _serialize(val: Any) -> dict:
    """Convert a function return value to a JSON-safe dict."""
    if val is None:
        return {"result": None}
    if isinstance(val, (str, int, float, bool, bytes)):
        return {"result": val}
    if isinstance(val, (list, tuple)):
        return {"result": [_serialize_dictish(v) for v in val]}
    if hasattr(val, "model_dump"):
        return {"result": val.model_dump()}
    if hasattr(val, "dict"):
        return {"result": val.dict()}
    if isinstance(val, dict):
        return {"result": val}
    try:
        return {"result": str(val)}
    except Exception:
        return {"result": repr(val)}


def _serialize_dictish(val: Any) -> Any:
    if hasattr(val, "model_dump"):
        return val.model_dump()
    if hasattr(val, "dict"):
        return val.dict()
    return val


# ---------------------------------------------------------------------------
# Dynamic handler factory
# ---------------------------------------------------------------------------

_EXEC_GLOBALS = {
    "Optional": Optional,
    "List": List,
    "Dict": Dict,
    "Tuple": __import__("typing").Tuple,
    "Any": Any,
    "importlib": importlib,
    "asyncio": asyncio,
    "_resolve_func": _resolve_func,
    "_serialize": _serialize,
}


def _build_handler(node_info) -> Optional[Any]:
    """Build an async handler function with proper typed signature for a @node.

    Uses exec() to create a function whose parameter names + type annotations
    match the node's input_schema. Returns None if the module cannot be resolved.
    """
    node_mod = node_info.module
    node_qualname = node_info.qualname
    params = node_info.input_schema or {}

    # Parse + sort: required params first, optional params last (Python syntax requirement)
    typed_params: List[tuple] = []
    for k, v in params.items():
        py_type = _parse_type_str(v)
        origin = get_origin(py_type)
        p_args = get_args(py_type)
        is_opt = (origin is Optional) or (origin is Union and type(None) in p_args)
        typed_params.append((k, py_type, is_opt))
    typed_params.sort(key=lambda x: (1 if x[2] else 0, x[0]))

    param_defs: List[str] = []
    for k, py_type, is_opt in typed_params:
        expr = _type_to_expr(py_type)
        if is_opt:
            param_defs.append(f"{k}: {expr} = None")
        else:
            param_defs.append(f"{k}: {expr}")

    params_code = ", ".join(param_defs)

    # Build kwargs explicitly from parameter names (never dict(locals()),
    # which would leak internal `_node_mod`/`_node_func` variables into the
    # call and break every generated handler).
    kwarg_expr = ", ".join(f"'{k}': {k}" for k in (t[0] for t in typed_params))

    safe_mod = node_mod.replace("'", "\\'")
    safe_qualname = node_qualname.replace("'", "\\'")

    body = f"""async def _handler({params_code}):
    try:
        _node_mod = importlib.import_module('{safe_mod}')
        _node_func = _resolve_func(_node_mod, '{safe_qualname}')
        _kwargs = {{{kwarg_expr}}}
        if asyncio.iscoroutinefunction(_node_func):
            result = await _node_func(**_kwargs)
        else:
            result = _node_func(**_kwargs)
        return _serialize(result)
    except Exception as _e:
        return {{'error': str(_e)}}"""

    local_vars: Dict[str, Any] = {}
    try:
        exec(body, _EXEC_GLOBALS, local_vars)
    except Exception as e:
        logger.warning("Failed to build handler for %s: %s", node_info.name, e)
        return None
    return local_vars["_handler"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_dynamic_node_tools(mcp: FastMCP, limit: Optional[int] = None) -> int:
    """Discover and register every @node wrapper as an individual MCP tool.

    Args:
        mcp: FastMCP server instance.
        limit: Optional cap on how many nodes to register (for testing).

    Returns:
        Number of tools successfully registered.
    """
    try:
        from common_lib.modules.nodes_registry import discover_nodes as _discover
    except ImportError as e:
        logger.error("Cannot import discover_nodes: %s", e)
        return 0

    raw_nodes = _discover()
    logger.info("Discovered %s @node wrappers", len(raw_nodes))

    # Collect existing tool names to avoid duplicates
    try:
        import asyncio

        existing = {t.name for t in asyncio.run(mcp.list_tools())}
    except Exception:
        existing = set()

    count = 0
    skipped = 0
    for node_info in raw_nodes[:limit]:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-.]", "_", node_info.name.replace(" ", "_"))
        if safe_name in existing:
            skipped += 1
            continue

        handler = _build_handler(node_info)
        if handler is None:
            skipped += 1
            continue

        try:
            mcp.add_tool(
                fn=handler,
                name=safe_name,
                description=node_info.description or "",
            )
            count += 1
        except Exception as e:
            logger.warning("Failed to register tool '%s': %s", safe_name, e)
            skipped += 1

    logger.info(
        "Registered %s / %s @node wrappers as MCP tools (%s skipped)",
        count,
        len(raw_nodes),
        skipped,
    )
    return count
