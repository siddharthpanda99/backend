"""Regression test for the ``__node_no_implicit_instance__`` opt-out.

Why this exists
---------------
``app/mcp/node_bridge.py::_bind_instance`` will construct an owner class
implicitly when a ``@node`` method belongs to a class whose constructor takes no
required arguments, and then pins that instance in ``_BOUND_INSTANCE_KEEPALIVE``
for the life of the process. A class that opens a DB session, a Redis client or a
socket inside ``__init__`` would therefore share ONE ORM session across every
request from every tenant -- uncommitted work from one caller becomes visible to,
and committed by, another. That is a cross-tenant data leak.

Such a class must declare the opt-out::

    class IssueService:
        __node_no_implicit_instance__ = True  # takes a DB Session

What this test asserts
----------------------
Discovery is GENERIC: it walks every module in ``project_management`` and
``notification``, finds every class that

  * carries a ``@node`` marker (on the class or on any of its methods),
  * the bridge can construct with no arguments, and
  * reaches a resource-opening identifier in its ``__init__``, following one
    level of the call graph,

and requires the opt-out on each. A new service written tomorrow in the same
shape fails here rather than leaking silently in production.

The assertion is made against the REAL imported class objects, not the AST and
not the source text -- a source-level check has already been fooled in this repo
before (an attribute present in the file but not visible to the bridge).

Nothing here connects to a database: it reads class attributes and, where a
class must be instantiated, it uses a temporary SQLite engine or a stub.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib
import pkgutil

import pytest

ATTR = "__node_no_implicit_instance__"

MODULES = ("project_management", "notification")

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
    "KafkaProducer",
    "Client",
    "connect",
)


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
    root = COMMON_LIB_SRC / "modules" / module
    for path in sorted(root.rglob("*.py")):
        yield path


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
    """Every no-arg @node class that reaches a resource opener, both modules."""
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


def _dotted(path: pathlib.Path) -> str:
    rel = path.relative_to(COMMON_LIB_SRC).with_suffix("")
    return "common_lib." + ".".join(rel.parts)


OFFENDERS = find_offenders()


def test_offender_discovery_is_not_empty():
    """Guard the guard: if discovery silently found nothing, every other test
    below would pass for the wrong reason."""
    assert OFFENDERS, (
        "no offenders discovered in project_management/notification -- the "
        "detector has regressed and the remaining assertions are vacuous"
    )
    names = {o["class"] for o in OFFENDERS}
    # known offenders that must be found, by name, in their real files
    assert "RedisBroker" in names, "RedisBroker must be detected"
    assert "EventBus" in names, "EventBus must be detected"
    assert "CoreService" in names, (
        "CoreService (indirect, via registries) must be detected"
    )


def test_every_offender_declares_the_opt_out():
    """The real assertion: resolve each offender from its REAL module object and
    require the opt-out to be visible to the bridge."""
    missing = []
    for off in OFFENDERS:
        modname = _dotted(off["file"])
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:  # pragma: no cover - import env problem
            missing.append(
                f"{modname}.{off['class']}: module not importable ({type(exc).__name__}: {exc})"
            )
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
        "these classes are reachable through the MCP bridge, take no constructor "
        "arguments, and open a resource in __init__ -- without "
        f"{ATTR} = True the bridge would construct one per process and pin it in "
        "_BOUND_INSTANCE_KEEPALIVE, sharing one session across tenants:\n  "
        + "\n  ".join(missing)
    )


def test_bridge_honours_the_attribute_on_a_real_class():
    """Drive the real node_bridge predicate, not a copy of it."""
    node_bridge = pytest.importorskip("app.mcp.node_bridge")
    bus = importlib.import_module("common_lib.modules.notification.bus.service")

    # opted out
    assert node_bridge._opts_out_of_implicit_construction(bus.RedisBroker) is True
    assert node_bridge._opts_out_of_implicit_construction(bus.EventBus) is True

    # not opted out -> still auto-bindable, so the guard is not blanket
    assert node_bridge._opts_out_of_implicit_construction(bus.InMemoryBroker) is False

    # an attribute on the class is what getattr sees -- matching the bridge's own
    # lookup, so a subclass or instance-level value cannot silently diverge
    assert getattr(bus.RedisBroker, ATTR, False) is True


def _fake_node_module(monkeypatch):
    """A real module object holding a @node-marked class, installed as an attribute
    of the notification bus module so ``_bind_instance(module, qualname, func)``
    resolves the owner exactly the way the generated handlers do.

    The class is a stub: it records construction instead of opening anything, so
    no Redis connection and no database session can be created by this test.
    """
    bus = importlib.import_module("common_lib.modules.notification.bus.service")
    built: list[object] = []

    class SpyBroker:
        __node_no_implicit_instance__ = True

        def __init__(self):
            built.append(self)
            self.opened = object()  # stands in for a live session/client

        def do_thing(self):
            return "bound"

    # _looks_unbound only fires for a plain function whose first param is `self`
    def publish(self, topic, message):  # noqa: ARG001 - shape only
        return "bound"

    SpyBroker.publish = publish
    monkeypatch.setattr(bus, "SpyBroker", SpyBroker, raising=False)
    return bus, SpyBroker, publish, built


def test_opted_out_class_is_not_constructed_by_the_bridge(monkeypatch):
    """The behavioural half: with the attribute present the bridge must not build
    an instance, must not add one to the keep-alive list, and must hand back a
    stand-in that raises a diagnosable error instead of a bound method."""
    node_bridge = pytest.importorskip("app.mcp.node_bridge")
    bus, spy_cls, publish, built = _fake_node_module(monkeypatch)

    assert node_bridge._looks_unbound(publish) is True, "probe shape is wrong"

    keep_before = len(node_bridge._BOUND_INSTANCE_KEEPALIVE)
    result = node_bridge._bind_instance(bus, "SpyBroker.publish", publish)

    assert not built, "the bridge constructed a class that opted out"
    assert len(node_bridge._BOUND_INSTANCE_KEEPALIVE) == keep_before, (
        "an opted-out class was pinned in the keep-alive list -- the leak is live"
    )
    assert getattr(result, "__self__", None) is None, "it returned a bound method"
    with pytest.raises(RuntimeError):
        result()

    # and the counterpart: identical class, attribute removed -> it DOES construct
    monkeypatch.delattr(spy_cls, "__node_no_implicit_instance__", raising=False)
    assert node_bridge._opts_out_of_implicit_construction(spy_cls) is False
    bound = node_bridge._bind_instance(bus, "SpyBroker.publish", publish)
    assert len(built) == 1, "without the opt-out the bridge should have constructed it"
    assert getattr(bound, "__self__", None) is not None
    assert bound("t", {}) == "bound"
    assert len(node_bridge._BOUND_INSTANCE_KEEPALIVE) == keep_before + 1
    del node_bridge._BOUND_INSTANCE_KEEPALIVE[keep_before:]
    assert len(node_bridge._BOUND_INSTANCE_KEEPALIVE) == keep_before


def test_opt_out_is_not_blanket(monkeypatch):
    """A stateless no-arg @node class must remain auto-bindable, otherwise the
    opt-out would hide thousands of working tools to guard a handful."""
    node_bridge = pytest.importorskip("app.mcp.node_bridge")
    bus = importlib.import_module("common_lib.modules.notification.bus.service")
    keep_before = len(node_bridge._BOUND_INSTANCE_KEEPALIVE)
    bound = node_bridge._bind_instance(
        bus, "InMemoryBroker.publish", bus.InMemoryBroker.publish
    )
    assert getattr(bound, "__self__", None) is not None, (
        "InMemoryBroker opens nothing and should still bind"
    )
    del node_bridge._BOUND_INSTANCE_KEEPALIVE[keep_before:]
    assert len(node_bridge._BOUND_INSTANCE_KEEPALIVE) == keep_before


def test_no_offender_relies_on_a_constructor_argument():
    """Documents WHY the JSON list is mostly harmless today: 62 of the 86 entries
    require a ``session`` argument, so ``owner()`` raises TypeError and the bridge
    never constructs them. The opt-out is still correct -- it makes the class safe
    if someone later gives the argument a default."""
    from common_lib.modules.project_management.issues.service import IssueService

    sig = inspect.signature(IssueService)
    assert "session" in sig.parameters, "IssueService should still take a session"
    required = [
        p
        for p in sig.parameters.values()
        if p.default is p.empty and p.name not in ("self", "cls")
    ]
    assert required, "IssueService is expected to require its session argument"
    assert getattr(IssueService, ATTR, False) is True
