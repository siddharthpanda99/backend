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
import inspect
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union, get_args, get_origin

from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("node_bridge")


def _existing_tool_names(mcp: FastMCP) -> set:
    """Snapshot the tool names already registered on `mcp`.

    Must work both from plain sync code and from inside a running event loop
    (the FastAPI lifespan calls the registration during startup). A bare
    `asyncio.run()` raises RuntimeError in the latter case, and the previous
    `except Exception: existing = set()` fallback then silently treated the
    server as empty - letting ~19k @node tools overwrite the statically
    registered tools that already owned those names.
    """

    async def _list() -> set:
        return {t.name for t in await mcp.list_tools()}

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_list())
    # A loop is already running in this thread; hand the coroutine to a worker
    # thread that can own a fresh loop.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _list()).result()


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


def _looks_unbound(func: Any) -> bool:
    """True when ``func`` is a plain function whose first parameter is ``self``.

    ``@node`` applied to a method of a class yields a plain function. When the
    MCP bridge resolves ``Class.method`` it gets that unbound function, and
    calling ``func(**kwargs)`` passes the first kwarg as ``self`` — so the body
    never runs and the call raises ``TypeError``.
    """
    if not inspect.isfunction(func):
        return False
    try:
        params = list(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return False
    return bool(params) and params[0] in ("self", "cls")


try:  # optional: the registry is a separate, newer module
    from common_lib.modules.common.instance_registry import (
        describe_unregistered_owner as _DESCRIBE_UNREGISTERED_OWNER,
    )
    from common_lib.modules.common.instance_registry import (
        resolve_instance as _RESOLVE_INSTANCE,
    )
except Exception:  # pragma: no cover - node_bridge must work without it
    _DESCRIBE_UNREGISTERED_OWNER = None
    _RESOLVE_INSTANCE = None


def _bind_instance(module, qualname: str, func: Any) -> Any:
    """Bind an unbound method to a fresh instance of its owning class.

    Measured platform-wide before this existed: of 25 655 generated handlers,
    roughly 13 340 (52%) raised ``TypeError: ... missing 1 required positional
    argument: 'self'`` on every call. Three separate module audits hit it
    independently (notification 202 nodes, observability 218, a 120-handler
    sample 58). Those nodes are decorated, discovered, listed in the registry and
    advertised to agents — and uncallable.

    Every failure mode here returns the ORIGINAL callable, so the worst outcome is
    the pre-existing ``TypeError`` with an unchanged message. It never makes a
    working node worse.

    Enabled by ``MCP_BIND_NODE_INSTANCES=1``; default OFF because instantiating a
    service class may open a DB session or have other side effects, and that is
    not a decision to take implicitly on ~13 000 call sites.
    """
    if not _looks_unbound(func):
        return func

    parts = qualname.split(".")
    if len(parts) < 2:
        return func

    owner, method_name = module, parts[-1]
    try:
        for part in parts[:-1]:
            owner = getattr(owner, part)
    except AttributeError:
        return func

    if not inspect.isclass(owner):
        return func

    # An explicitly registered instance always wins, and is deliberately NOT
    # gated by MCP_BIND_NODE_INSTANCES: supplying an instance is an explicit act
    # by the application. It is also the ONLY path that can serve a class whose
    # constructor requires arguments -- calling the class object raises TypeError
    # before any of its own code runs, so no amount of implicit construction
    # helps those 2 105 nodes.
    instance = _instance_from_registry(owner)
    if (
        instance is None
        and _BINDING_ENABLED()
        and not _opts_out_of_implicit_construction(owner)
    ):
        try:
            instance = owner()
        except Exception:  # noqa: BLE001
            # Fall through to the diagnosable stand-in below rather than
            # returning `func`. Returning the unbound function here would hand
            # the caller the bare "missing 1 required positional argument:
            # 'self'" TypeError -- the exact symptom this path exists to
            # replace -- and would say nothing about why the owner could not be
            # built. `describe_unregistered_owner` names the real cause,
            # including which constructor arguments are required.
            instance = None
    if instance is None:
        return _unavailable(owner, method_name)

    try:
        bound = getattr(instance, method_name)
    except AttributeError:
        return func

    # Keep the instance alive for as long as the process lives: these services
    # may hold a session or a cache, and letting the only reference die would
    # close it. A module-level list is the simplest correct owner.
    _BOUND_INSTANCE_KEEPALIVE.append(instance)
    return bound


def _BINDING_ENABLED() -> bool:
    """Whether implicit construction of an unregistered owner is permitted.

    DEFAULT ON. This was default OFF because instantiating a service class may
    open a DB session or have other side effects, and that is not a decision to
    take implicitly on ~9 500 call sites. Two facts have since changed it:

    1. `instance_registry` is consulted FIRST, so anything the application
       supplies is used regardless of this gate. Only owners nobody registered
       are constructed implicitly.
    2. The dangerous classes take a `session` (or similar) in their constructor,
       so `owner()` raises on them and they are never constructed implicitly at
       all. Measured: 103 owners / 1 028 nodes were refused registration for
       exactly this reason -- a singleton session behind a node reachable from
       every request is a cross-tenant leak, not a bug.

    What remains is a narrower, enumerable case: a NO-ARG class that opens a
    session or socket itself. A blanket-off cannot distinguish those from the
    ~9 400 that are safe, so it hid 9 400 working tools to protect a handful.
    Those classes now opt out explicitly via `__node_no_implicit_instance__`.

    Set MCP_BIND_NODE_INSTANCES=0 for a fully conservative instance.
    """
    return os.environ.get("MCP_BIND_NODE_INSTANCES", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _instance_from_registry(owner: Any) -> Any:
    """Look up an explicitly registered instance for ``owner``, or None."""
    resolve = _RESOLVE_INSTANCE
    return None if resolve is None else resolve(owner)


def _opts_out_of_implicit_construction(owner: Any) -> bool:
    """Whether ``owner`` declares it must not be constructed implicitly.

    Set ``__node_no_implicit_instance__ = True`` on a no-arg class that opens a
    DB session, binds a socket, or otherwise has a side effect in ``__init__``.
    Such a class is reachable through the bridge, so without this it would be
    constructed once per process and pinned alive by the keep-alive list.
    """
    return bool(getattr(owner, "__node_no_implicit_instance__", False))


def _unavailable(owner: Any, method_name: str) -> Any:
    """Stand-in that raises a diagnosable error naming the cause, not the symptom.

    Previously an unbound node surfaced ``TypeError: f() missing 1 required
    positional argument: 'self'``, which names a missing argument and not the
    missing registration.
    """
    describe = _DESCRIBE_UNREGISTERED_OWNER
    detail = (
        describe(owner)
        if describe is not None
        else f"Cannot bind node {owner!r}.{method_name}: no registered instance."
    )

    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(detail)

    _raise.__name__ = method_name
    _raise.__qualname__ = f"{getattr(owner, '__name__', owner)}.{method_name}"
    return _raise


#: Instances created by ``_bind_instance``, retained so they are not garbage
#: collected while their bound method is still reachable through the registry.
_BOUND_INSTANCE_KEEPALIVE: List[Any] = []


def _resolve_callable(module, qualname: str) -> Any:
    """Resolve, then bind to an instance if the target is an unbound method.

    Binding is now attempted for every unbound method, not only when
    MCP_BIND_NODE_INSTANCES is set, because it is a no-op unless a registry
    entry or a permitted implicit construction succeeds. The env var still
    governs the risky half -- constructing an owner nobody registered.
    """
    func = _resolve_func(module, qualname)
    if _looks_unbound(func):
        return _bind_instance(module, qualname, func)
    return func


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
    "_resolve_callable": _resolve_callable,
    "_serialize": _serialize,
}


def _normalise_input_schema(raw) -> dict:
    """Return ``{param_name: type_string}`` from either schema spelling.

    ``@node`` accepts two shapes and they are NOT interchangeable:

      flat    ``input_schema={"kb_id": {"type": "string"}}``
              -> keys are already parameter names.

      object  ``input_schema=input_object(properties={"kb_id": ...})``
              -> a whole JSON-Schema DOCUMENT, whose top-level keys are
                 ``type``/``description``/``properties``/``required``.

    This function used to assume the flat shape. For every node declared with
    ``input_object()`` it therefore built a handler whose signature was
    ``(type, description, properties, required)`` instead of the real
    parameters, so calling it raised
    ``TypeError: unexpected keyword argument 'kb_id'``. The node was decorated,
    discovered, listed in the registry and advertised to agents — and entirely
    uncallable.

    Measured: 1 092 declared node names platform-wide used the object form.

    The fix is to read ``properties`` (and honour ``required``) when the input
    looks like a schema document, and to pass the flat form through untouched.
    """
    if not raw:
        return {}

    # Schema-document form: has a mapping under "properties".
    props = raw.get("properties") if isinstance(raw, dict) else None
    if isinstance(props, dict):
        required = raw.get("required")
        required_set = (
            set(required) if isinstance(required, (list, tuple, set)) else None
        )
        out: dict = {}
        for name, spec in props.items():
            # Copy the spec so marking a param optional cannot mutate the
            # caller's original schema.
            spec = dict(spec) if isinstance(spec, dict) else {"type": "string"}
            if required_set is not None and name not in required_set:
                # Optional: the caller may omit it. Mark it so the signature
                # builder emits a default rather than a required positional.
                spec = {**spec, "_optional": True}
            out[name] = spec
        return out

    return raw


def _build_handler(node_info) -> Optional[Any]:
    """Build an async handler function with proper typed signature for a @node.

    Uses exec() to create a function whose parameter names + type annotations
    match the node's input_schema. Returns None if the module cannot be resolved.
    """
    node_mod = node_info.module
    node_qualname = node_info.qualname
    params = _normalise_input_schema(node_info.input_schema)

    # Parse + sort: required params first, optional params last (Python syntax requirement)
    typed_params: List[tuple] = []
    for k, v in params.items():
        # `_normalise_input_schema` marks params absent from a schema document's
        # `required` list. Those are optional at the call site even though their
        # declared type is not Optional, so honour the marker too — otherwise a
        # schema-document node with a non-required param becomes a required
        # positional the MCP client cannot satisfy.
        declared_optional = isinstance(v, dict) and v.pop("_optional", False)
        v = (
            {kk: vv for kk, vv in v.items() if kk != "_optional"}
            if isinstance(v, dict)
            else v
        )
        py_type = _parse_type_str(v)
        origin = get_origin(py_type)
        p_args = get_args(py_type)
        is_opt = (
            declared_optional
            or (origin is Optional)
            or (origin is Union and type(None) in p_args)
        )
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

    # `executable` defaults to True when the key is absent, so nodes declared
    # before the flag existed are unaffected. Only an explicit False marks a
    # declaration that has no implementation to call.
    # Read the flag from the NodeInfo FIELD, not from metadata.
    #
    # `NodeInfo.metadata` holds only the *inner* user dict
    # (schema_version / node_kind / is_tool_use_safe ...); the enriched metadata
    # that carries `executable` never reaches it. Reading
    # `metadata.get("executable", True)` therefore yielded None -> True for
    # every node, and all 259 `executable=False` markings were inert: the
    # generated handler still called an uncallable declaration and returned a
    # raw TypeError instead of the intended guard.
    #
    # The attribute is the single source of truth
    # (nodes_registry/__init__.py: `executable=bool(meta.get("executable", True))`),
    # so prefer it and fall back to metadata only for older NodeInfo shapes.
    _executable = True
    try:
        _flag = getattr(node_info, "executable", None)
        if _flag is None:
            _meta = getattr(node_info, "metadata", None) or {}
            _flag = _meta.get("executable", True)
        _executable = bool(_flag)
    except Exception:  # noqa: BLE001
        _executable = True
    safe_name = str(getattr(node_info, "name", "") or "").replace("'", "\\'")

    # Bake the guard into the generated source as a literal rather than looking
    # it up at call time. An exec'd function resolves names against the GLOBALS
    # dict, not the locals dict it was defined with, so a `_EXECUTABLE` local
    # raised NameError on every call.
    _non_exec_guard = (
        (
            "    return {\n"
            "        'error': 'not executable',\n"
            "        'reason': (\n"
            f"            '{safe_name} is a declaration (an abstract method, a '\n"
            "            'Protocol/ABC interface, or a type descriptor). It is '\n"
            "            'published so the contract is DISCOVERABLE, but it has no '\n"
            "            'implementation to invoke. Find and call a concrete '\n"
            "            'implementation instead.'\n"
            "        ),\n"
            "        'executable': False,\n"
            "    }\n"
        )
        if not _executable
        else "    pass  # executable\n"
    )

    body = f"""async def _handler({params_code}):
{_non_exec_guard}    try:
        _node_mod = importlib.import_module('{safe_mod}')
        _node_func = _resolve_callable(_node_mod, '{safe_qualname}')
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
        from common_lib.modules.plugins.nodes_registry import (
            discover_nodes as _discover,
        )
    except ImportError as e:
        logger.error("Cannot import discover_nodes: %s", e)
        return 0

    raw_nodes = _discover()
    logger.info("Discovered %s @node wrappers", len(raw_nodes))

    # Flatten to one node per display name, first-wins.
    #
    # The canonical registry keys nodes by (name, module, qualname) so wrappers
    # that share a name across different modules are all retained (that richer
    # list is what the PM-scoped contract depends on). MCP, however, has one flat
    # tool namespace, so it has always been fed a name-unique list: the previous
    # per-module registry copy de-duplicated on `name` at discovery time. This
    # reproduces that flattening here so the registered tool set is unchanged.
    # Iteration order is identical to the old discovery order, so "first" is the
    # same wrapper it used to be.
    unique_nodes: list = []
    seen_names: set = set()
    for node_info in raw_nodes:
        if node_info.name in seen_names:
            continue
        seen_names.add(node_info.name)
        unique_nodes.append(node_info)
    if len(unique_nodes) != len(raw_nodes):
        logger.info(
            "Flattened %s duplicate @node names to %s unique MCP tools",
            len(raw_nodes) - len(unique_nodes),
            len(unique_nodes),
        )
    raw_nodes = unique_nodes

    # Collect existing tool names to avoid duplicates
    try:
        existing = _existing_tool_names(mcp)
    except Exception as e:
        logger.warning("Could not list existing MCP tools (%s); assuming none", e)
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
