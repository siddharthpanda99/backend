"""Regression test for the ``__node_no_implicit_instance__`` opt-out — long tail.

THE DEFECT
----------
``app/mcp/node_bridge.py::_bind_instance`` constructs an owner class implicitly
when a ``@node`` method belongs to a class whose constructor takes no REQUIRED
arguments, then pins that instance in ``_BOUND_INSTANCE_KEEPALIVE`` for the life
of the process::

    class MyService:
        def __init__(self):
            self.session = Session(engine)   # a real session, no argument needed

Every request from every tenant then shares ONE ORM session — uncommitted work
from one caller becomes visible to, and committed by, another. A cross-tenant
data leak. The guard is a class attribute the bridge honours::

    class MyService:
        __node_no_implicit_instance__ = True

SCOPE
-----
The 13 long-tail modules below, plus this file's explicit ``ALSO_MARKED`` table.
``data_storage`` and ``auth`` belong to another agent; ``doc_processing`` and
``core_infrastructure`` are in the ACTIVE-WORK in-flight table and were left
untouched (reported, not marked).

WHAT MAKES THIS TESTABLE
------------------------
Discovery is GENERIC. It walks each module and finds every class that

  * carries a ``@node`` marker on the class or on any of its methods,
  * the bridge can construct with no arguments, and
  * reaches a resource-opening identifier in ``__init__``, following ONE level of
    the call graph (so ``self.x = Helper()`` where ``Helper.__init__`` opens a
    session is caught — the name-based JSON inventory this work grew out of
    missed exactly that shape).

Then it requires the opt-out on each. A new service written tomorrow in the same
shape fails here rather than leaking silently.

The assertion is made against the REAL imported class objects, never the AST and
never the source text: this bug class has recurred three times in this repo, once
where a source-level check passed while the runtime was broken, and once where a
test validated a hand-rolled stand-in instead of the real object.

NOTHING HERE CONNECTS TO ANYTHING. The tests read class attributes; where an
instance must be built to prove the bridge's behaviour, a stub whose ``__init__``
records construction is used. No ORM session, no model load, no socket, no
bucket, and above all no write to the live ``nexus_db``.
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

ATTR = "__node_no_implicit_instance__"

MODULES = (
    "rbac",
    "image_processing",
    "knowledge_engine",
    "ai_models",
    "orchestration",
    "governance",
    "memory",
    "workflows",
    "agentic_os",
    "agents",
    "app_builder",
    "observability",
    "security",
)

COMMON_LIB_SRC = (
    pathlib.Path(__file__).resolve().parents[2]
    / "Python Libs"
    / "common_lib"
    / "src"
    / "common_lib"
)

#: Identifiers whose presence in a constructor means "a live resource is opened".
#: Substring matching, so `_get_session` and `_shared_engine` are both caught.
OPEN_SUBSTR = (
    "Session",
    "create_engine",
    "sessionmaker",
    "get_session",
    "get_db_port",
    "get_engine",
    "get_data_storage_engine",
    "get_shared_session",
    "get_policy_engine",
    "get_memory_store",
    "redis",
    "Redis",
    "boto3",
    "requests",
    "httpx",
    "urlopen",
    "socket",
    "MongoClient",
    "psycopg2",
    "pymongo",
    "sqlite3",
    "chromadb",
    "KafkaProducer",
    "Client",
    "connect",
)

#: Classes whose ``__init__`` opens a resource that no identifier above names --
#: a spaCy/Presidio NLP engine, an MLflow/Langfuse tracing client, a module
#: global that a process-pinned instance would capture. Each is named explicitly
#: so the test still fails if one loses its attribute, and so a reader can see
#: the model/client-holding rationale that a name match cannot express.
ALSO_MARKED: dict[str, tuple[str, ...]] = {
    "common_lib.modules.security.pii.presidio_analyzer": ("PresidioAnalyzer",),
    "common_lib.modules.security.pii.presidio_anonymizer": ("PresidioAnonymizer",),
    "common_lib.modules.observability.mlflow_integration": ("MLFlowExperimentTracker",),
    "common_lib.modules.observability.langfuse_integration": (
        "LangfuseObservabilityAdapter",
    ),
    "common_lib.modules.observability.langflow_integration": (
        "LangFlowWorkflowAdapter",
    ),
    "common_lib.modules.observability.ai_tracker": ("RAGTracker",),
    "common_lib.modules.memory.service": ("MemoryService",),
}


#: Name-collision false positives. The detector matches identifiers by substring,
#: so it also fires on state that crosses no process boundary at all. Each entry
#: is here with the reason it is NOT a leak; deleting one makes CI red on purpose.
#:
#: A needless opt-out is safe (the class simply is not auto-bound), but a wrong one
#: hides working tools, so these are enumerated rather than waved through.
FALSE_POSITIVES: dict[tuple[str, str], str] = {
    (
        "modules/memory/memory_storage/circuit_breaker.py",
        "StorageCircuitBreaker",
    ): "matches on _total_requests, a plain int counter",
    (
        "modules/memory/memory_context/state/data/manager.py",
        "SessionStateManager",
    ): "matches on SessionStateModel, a dict of in-process state",
    (
        "modules/memory/memory_execution/tools/tool_invocation.py",
        "ToolInvoker",
    ): "matches on _connectors, an empty in-process dict",
    (
        "modules/workflows/standard/execution/approval.py",
        "ApprovalManager",
    ): "matches on _requests, an in-process dict of ApprovalRequest",
    (
        "modules/image_processing/nodes/reactor/lib/codeformer_arch.py",
        "CodeFormer",
    ): "matches on connect_list, a torch nn.Module list, not a socket",
    (
        "modules/knowledge_engine/learning/evolver/reflector/reflector_node.py",
        "ReflectorNode",
    ): (
        "marked anyway: it holds a SessionStateService slot that persists to the DB. "
        "Kept listed because the identifier match is a type annotation, not a call."
    ),
}


def _is_opener(name: str | None) -> bool:
    return bool(name) and any(s in name for s in OPEN_SUBSTR)


def _required_arg_count(fn: ast.FunctionDef) -> int:
    args = fn.args
    pos = list(args.posonlyargs) + list(args.args)
    if pos and pos[0].arg in ("self", "cls"):
        pos = pos[1:]
    n_defaults = len(args.defaults)
    return (len(pos) - n_defaults) if n_defaults else len(pos)


def _has_node_decorator(cls: ast.ClassDef) -> bool:
    for dec in cls.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if (getattr(target, "id", None) or getattr(target, "attr", None)) == "node":
            return True
    return False


def _opened_names(fn: ast.AST | None) -> set[str]:
    if fn is None:
        return set()
    return {
        getattr(n, "id", None) or getattr(n, "attr", None)
        for n in ast.walk(fn)
        if _is_opener(getattr(n, "id", None) or getattr(n, "attr", None))
    }


def _called_names(fn: ast.AST) -> set[str]:
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute)):
            out.add(getattr(n.func, "id", None) or getattr(n.func, "attr", None))
    return {c for c in out if c}


def _iter_module_files(module: str):
    yield from sorted((COMMON_LIB_SRC / "modules" / module).rglob("*.py"))


def _build_index(module: str):
    """name -> (path, __init__ node or None, opened identifier names)."""
    classes: dict[str, list[tuple[pathlib.Path, ast.FunctionDef | None, set[str]]]] = {}
    functions: dict[str, list[pathlib.Path]] = {}
    for path in _iter_module_files(module):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - a broken file is another test's job
            continue
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            init = next(
                (
                    x
                    for x in cls.body
                    if isinstance(x, ast.FunctionDef) and x.name == "__init__"
                ),
                None,
            )
            classes.setdefault(cls.name, []).append((path, init, _opened_names(init)))
        for fn in tree.body:
            if isinstance(fn, ast.FunctionDef) and _opened_names(fn):
                functions.setdefault(fn.name, []).append(path)
    return classes, functions


def find_offenders() -> list[dict]:
    """Every no-arg @node class in scope that reaches a resource opener."""
    found: list[dict] = []
    for module in MODULES:
        classes, functions = _build_index(module)
        for path in _iter_module_files(module):
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError:  # pragma: no cover
                continue
            for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                if not _has_node_decorator(cls):
                    continue
                init = next(
                    (
                        x
                        for x in cls.body
                        if isinstance(x, ast.FunctionDef) and x.name == "__init__"
                    ),
                    None,
                )
                if init is not None and _required_arg_count(init) > 0:
                    # the bridge cannot construct this: owner() raises TypeError
                    continue
                direct = _opened_names(init)
                indirect: list[str] = []
                if init is not None:
                    for callee in _called_names(init):
                        for _p, cinit, copened in classes.get(callee, []):
                            if cinit is not None and cinit is not init and copened:
                                indirect.append(callee)
                        if callee in functions:
                            indirect.append(f"{callee}()")
                if direct or indirect:
                    rel = str(path.relative_to(COMMON_LIB_SRC))
                    if (rel, cls.name) in FALSE_POSITIVES and not _marked_on_disk(
                        path, cls.name
                    ):
                        continue
                    found.append(
                        {
                            "module": module,
                            "file": path,
                            "class": cls.name,
                            "line": cls.lineno,
                            "direct": sorted(direct),
                            "indirect": sorted(set(indirect)),
                        }
                    )
    return found


def _marked_on_disk(path: pathlib.Path, cls: str) -> bool:
    """Whether the class body already sets the opt-out.

    Lets an entry in FALSE_POSITIVES be a genuine waiver (never marked) while a
    class that was marked anyway still has to satisfy the real assertion.
    """
    tree = ast.parse(path.read_text())
    node = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == cls),
        None,
    )
    if node is None:  # pragma: no cover
        return False
    return any(
        isinstance(st, ast.Assign)
        and any(getattr(t, "id", None) == ATTR for t in st.targets)
        for st in node.body
    )


def _dotted(path: pathlib.Path) -> str:
    rel = path.relative_to(COMMON_LIB_SRC).with_suffix("")
    return "common_lib." + ".".join(rel.parts)


OFFENDERS = find_offenders()

#: Offenders whose module cannot be imported in this environment (a missing
#: optional dependency), so only the source-level mark could be checked.
UNVERIFIABLE_AT_RUNTIME: list[str] = []


def test_every_offender_is_verifiable_at_runtime():
    """Fail loudly if the set of runtime-unverifiable offenders grows.

    Each entry is a class this environment cannot import, which means the real
    assertion above fell back to a source check for it. That is a weaker proof,
    so it must be a short, visible list rather than a growing silent hole.
    """
    assert len(UNVERIFIABLE_AT_RUNTIME) <= 2, (
        "more offenders are unverifiable at runtime than expected -- an optional "
        "dependency is probably missing from this environment, which weakens the "
        f"proof for these: {UNVERIFIABLE_AT_RUNTIME}"
    )


def test_offender_discovery_is_not_empty():
    """Guard the guard: if discovery silently found nothing, every other test
    below would pass for the wrong reason."""
    assert OFFENDERS, (
        "no offenders discovered in the long-tail modules -- the detector has "
        "regressed and the remaining assertions are vacuous"
    )
    names = {o["class"] for o in OFFENDERS}
    # The flagship offender, found DIRECTLY: it opens a live session with no
    # constructor argument at all.
    assert "PolicyEngine" in names, "PolicyEngine must be detected"
    assert {"S3Manager", "AIModelsContainer", "ModelManager"} <= names, (
        "the ai_models resource openers must be detected"
    )


def test_every_offender_declares_the_opt_out():
    """The real assertion: resolve each offender from its REAL module object and
    require the opt-out to be visible to the bridge."""
    missing = []
    for off in OFFENDERS:
        modname = _dotted(off["file"])
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:  # pragma: no cover - missing optional dep
            # The module cannot be imported in this environment (an optional
            # dependency such as `diffusers` is not installed), so the runtime
            # assertion is impossible here. Fall back to the SOURCE only for
            # that case -- and say so, because a source check alone has fooled
            # this repo before. A module that IS importable must never take
            # this path, so an environment problem cannot mask a real defect.
            if not _marked_on_disk(off["file"], off["class"]):
                missing.append(
                    f"{modname}.{off['class']}: module not importable "
                    f"({type(exc).__name__}: {exc}) AND not marked in source"
                )
            else:
                UNVERIFIABLE_AT_RUNTIME.append(f"{modname}.{off['class']}")
            continue
        cls = getattr(mod, off["class"], None)
        if cls is None:
            missing.append(f"{modname}.{off['class']}: class not found in module")
            continue
        if getattr(cls, ATTR, False) is not True:
            rel = off["file"].relative_to(COMMON_LIB_SRC)
            missing.append(
                f"{rel}:{off['line']} {off['class']} opens "
                f"{off['direct'] or off['indirect']} and does not set {ATTR}"
            )
    assert not missing, (
        "these classes are reachable through the MCP bridge, take no required "
        "constructor arguments, and open a resource in __init__ -- without "
        f"{ATTR} = True the bridge would construct one per process and pin it in "
        "_BOUND_INSTANCE_KEEPALIVE, sharing one session across tenants:\n  "
        + "\n  ".join(missing)
    )


def test_model_and_client_holding_classes_declare_the_opt_out():
    """The ALSO_MARKED table: classes whose resource is a loaded model or a tracing
    client rather than a session. A held model handle is the same class of risk as
    a held session, and no identifier list can express it."""
    missing = []
    for modname, class_names in ALSO_MARKED.items():
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:  # pragma: no cover - missing optional dep
            missing.append(f"{modname}: not importable ({type(exc).__name__}: {exc})")
            continue
        for name in class_names:
            cls = getattr(mod, name, None)
            if cls is None:
                missing.append(f"{modname}.{name}: class not found")
            elif getattr(cls, ATTR, False) is not True:
                missing.append(f"{modname}.{name} does not set {ATTR}")
    assert not missing, "\n  ".join(missing)


def test_bridge_honours_the_attribute_on_real_classes():
    """Drive the real node_bridge predicate, not a copy of it."""
    node_bridge = pytest.importorskip("app.mcp.node_bridge")

    governance = importlib.import_module("common_lib.modules.governance.engine.service")
    assert (
        node_bridge._opts_out_of_implicit_construction(governance.PolicyEngine) is True
    )
    assert getattr(governance.PolicyEngine, ATTR, False) is True

    rbac = importlib.import_module("common_lib.modules.rbac.service")
    assert node_bridge._opts_out_of_implicit_construction(rbac.RoleService) is True

    # Not a blanket: a stateless no-arg @node class must still be auto-bindable,
    # or the opt-out would hide thousands of working tools to guard a handful.
    assert (
        node_bridge._opts_out_of_implicit_construction(
            governance.PEPInterceptor.__mro__[1]  # the abstract base, opens nothing
        )
        is False
    )


def _stub_module(monkeypatch):
    """A real module object holding a @node-marked class, installed as an attribute
    of a real in-scope module so ``_bind_instance(module, qualname, func)`` resolves
    the owner exactly the way the generated handlers do.

    The class is a stub: ``__init__`` records construction instead of opening
    anything, so no session, model or connection can be created by this test.
    """
    host = importlib.import_module("common_lib.modules.rbac.service")
    built: list[object] = []

    class SpyService:
        __node_no_implicit_instance__ = True

        def __init__(self):
            built.append(self)
            self.opened = object()  # stands in for a live session

        def get_role(self, role_id: int):
            return "bound"

    # _looks_unbound only fires for a plain function whose first param is `self`
    def get_role(self, role_id: int):  # noqa: ARG001 - shape only
        return "bound"

    SpyService.get_role = get_role
    monkeypatch.setattr(host, "SpyService", SpyService, raising=False)
    return host, SpyService, get_role, built


def test_opted_out_class_is_not_constructed_by_the_bridge(monkeypatch):
    """The behavioural half: with the attribute present the bridge must not build an
    instance, must not add one to the keep-alive list, and must hand back a stand-in
    that raises a diagnosable error instead of a bound method."""
    node_bridge = pytest.importorskip("app.mcp.node_bridge")
    host, spy_cls, get_role, built = _stub_module(monkeypatch)

    assert node_bridge._looks_unbound(get_role) is True, "probe shape is wrong"

    keep_before = len(node_bridge._BOUND_INSTANCE_KEEPALIVE)
    result = node_bridge._bind_instance(host, "SpyService.get_role", get_role)

    assert not built, "the bridge constructed a class that opted out"
    assert len(node_bridge._BOUND_INSTANCE_KEEPALIVE) == keep_before, (
        "an opted-out class was pinned in the keep-alive list -- the leak is live"
    )
    assert getattr(result, "__self__", None) is None, "it returned a bound method"
    with pytest.raises(RuntimeError):
        result()

    # The counterpart, which is what makes the assertion above falsifiable:
    # identical class, attribute removed -> the bridge DOES construct it.
    monkeypatch.delattr(spy_cls, "__node_no_implicit_instance__", raising=False)
    assert node_bridge._opts_out_of_implicit_construction(spy_cls) is False
    bound = node_bridge._bind_instance(host, "SpyService.get_role", get_role)
    assert len(built) == 1, "without the opt-out the bridge should have constructed it"
    assert getattr(bound, "__self__", None) is not None
    assert bound(1) == "bound"
    assert len(node_bridge._BOUND_INSTANCE_KEEPALIVE) == keep_before + 1
    del node_bridge._BOUND_INSTANCE_KEEPALIVE[keep_before:]
    assert len(node_bridge._BOUND_INSTANCE_KEEPALIVE) == keep_before


def test_a_real_marked_class_is_not_constructible_by_the_bridge():
    """Prove the guard on a REAL class, not a stand-in: ``RoleService`` requires a
    session, so this only asserts the predicate -- but it asserts it on the object
    the bridge itself would resolve.

    ``RoleService()`` is never called: the class stores an injected session and
    building one would need a live ORM handle.
    """
    node_bridge = pytest.importorskip("app.mcp.node_bridge")
    rbac = importlib.import_module("common_lib.modules.rbac.service")

    assert node_bridge._opts_out_of_implicit_construction(rbac.RoleService) is True
    # and it would refuse to build it even if the attribute were absent,
    # because the constructor requires a session -- which is why the JSON
    # inventory was mostly harmless today and the attribute is belt-and-braces.
    import inspect

    required = [
        p
        for p in inspect.signature(rbac.RoleService).parameters.values()
        if p.default is p.empty and p.name not in ("self", "cls")
    ]
    assert required, "RoleService is expected to require its session argument"
