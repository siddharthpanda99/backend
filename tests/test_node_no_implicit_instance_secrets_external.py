"""Regression test: no no-arg ``@node`` class may hold a live resource implicitly.

Complements ``test_node_no_implicit_instance.py`` (owned by another session,
which covers ``project_management`` and ``notification``) for the
``secrets_manager`` and ``external_platforms`` modules.

Why a second detector
---------------------
The existing detector reads ``__init__`` only. That misses the worst case in
these two modules, where the resource is acquired LAZILY in a helper and cached
on ``self``::

    # external_platforms/writing_studio/service.py
    def _get_session(self) -> Session:
        if self._session is None:
            self._session = get_session_direct()      # self-cached ORM session
        return self._session

    # external_platforms/writing_studio/generator_engine.py
        engine = create_engine(...)
        self._session = SessionLocal()                # self-cached ORM session

    # external_platforms/writing_studio/llm_backend.py
        self._provider = registry.register_provider(...)  # credential handle

    # secrets_manager/keys_management/service.py
        self._engine = get_db_port().get_engine()      # self-cached DB engine

``node_bridge._bind_instance`` constructs the owner ONCE and pins it in
``_BOUND_INSTANCE_KEEPALIVE`` for the life of the process. Any resource cached on
``self`` therefore becomes process-global and is shared by every request from
every tenant: uncommitted work in one caller's ORM transaction becomes visible
to, and committed by, another. So this detector flags two shapes:

  (a) the constructor itself opens a resource, directly or via one callee;
  (b) ANY method caches a resource handle on ``self`` -- the leak survives the
      constructor entirely.

A class whose constructor has a REQUIRED argument is exempt: ``owner()`` raises
``TypeError``, so the bridge never constructs it. Those classes are still asserted
to carry the attribute (see ``ALSO_MARKED``), because in this module family the
convention is already drifting from ``session: Session`` to
``session: Session | None = None`` -- one edit away from becoming live.

Assertions are made against the REAL imported class objects via ``getattr``, not
against the AST or the source text: an attribute can sit inside a class body and
still not be visible to the bridge (a column-0 assignment lands in module scope,
not in the class). Nothing here opens a database, a socket or a vault -- it reads
class attributes, and the only instantiation is of a class whose constructor is
known to be inert.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib

COMMON_LIB_SRC = (
    pathlib.Path(__file__).resolve().parents[2]
    / "Python Libs"
    / "common_lib"
    / "src"
    / "common_lib"
)

MODULES = ("secrets_manager", "external_platforms")

ATTR = "__node_no_implicit_instance__"

#: Identifiers that mean "a live resource or credential handle".
OPEN_SUBSTR = (
    "Session",
    "create_engine",
    "sessionmaker",
    "get_session",
    "get_db_port",
    "get_engine",
    "redis",
    "boto3",
    "requests",
    "httpx",
    "urlopen",
    "socket",
    "MongoClient",
    "psycopg2",
    "pymongo",
    "sqlite3",
    "Client",
    "connect",
)

#: ``self.<name>`` attributes that hold a live resource or credential handle.
#: Matched on the attribute name because the acquisition is often indirect
#: (``self._provider = registry.register_provider(...)``).
HANDLE_ATTR = (
    "session",
    "engine",
    "client",
    "provider",
    "conn",
    "pool",
    "socket",
    "kms",
    "vault",
    "ssh",
    "token",
    "credential",
    "secret",
    "keyring",
)


def _is_opener(name: str | None) -> bool:
    return bool(name) and any(s in name for s in OPEN_SUBSTR)


def _name_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _required_arg_count(fn: ast.FunctionDef) -> int:
    args = fn.args
    pos = list(args.posonlyargs) + list(args.args)
    if pos and pos[0].arg in ("self", "cls"):
        pos = pos[1:]
    n_defaults = len(args.defaults)
    n_required = (len(pos) - n_defaults) if n_defaults else len(pos)
    n_required += sum(
        1
        for arg, default in zip(args.kwonlyargs, args.kw_defaults)
        if default is None and arg.arg not in ("self", "cls")
    )
    return n_required


def _has_node_decorator(cls: ast.ClassDef) -> bool:
    decorators = list(cls.decorator_list)
    for fn in cls.body:
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators.extend(fn.decorator_list)
    for dec in decorators:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if _name_of(target) == "node":
            return True
    return False


def _opened_names(fn: ast.AST | None) -> set[str]:
    if fn is None:
        return set()
    return {n for n in (_name_of(x) for x in ast.walk(fn)) if _is_opener(n)}


def _called_names(fn: ast.AST) -> set[str]:
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            name = _name_of(n.func)
            if name:
                out.add(name)
    return out


def _self_cached_handles(cls: ast.ClassDef) -> list[str]:
    """Methods that assign a live resource or credential handle to ``self``.

    ``self._session = get_session_direct()`` is a process-wide singleton the
    moment the bridge pins the instance -- regardless of which method did it.
    """
    hits: list[str] = []
    for fn in cls.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None or not isinstance(value, ast.Call):
                continue
            for tgt in targets:
                # only `self.<attr> = ...`
                if not (
                    isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"
                ):
                    continue
                attr = tgt.attr
                if any(h in attr.lower() for h in HANDLE_ATTR) or _opened_names(value):
                    hits.append(f"{fn.name}(): self.{attr}")
    return hits


def _module_files(module: str):
    return sorted((COMMON_LIB_SRC / "modules" / module).rglob("*.py"))


def find_offenders() -> list[dict]:
    """Every class the bridge can construct that holds or opens a resource."""
    found: list[dict] = []
    for module in MODULES:
        files = [p for p in _module_files(module) if "__pycache__" not in p.parts]
        trees: dict[pathlib.Path, ast.Module] = {}
        for path in files:
            try:
                trees[path] = ast.parse(path.read_text())
            except SyntaxError:  # pragma: no cover
                continue

        # module-level helpers that open a resource, for the one-level call graph
        helpers: dict[str, set[str]] = {}
        for tree in trees.values():
            for fn in tree.body:
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    opened = _opened_names(fn)
                    if opened:
                        helpers[fn.name] = opened

        for path, tree in trees.items():
            for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                if not _has_node_decorator(cls):
                    continue
                methods = [
                    m
                    for m in cls.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                init = next((m for m in methods if m.name == "__init__"), None)
                if init is not None and _required_arg_count(init) > 0:
                    # owner() raises TypeError: the bridge never constructs it
                    continue

                direct = sorted(_opened_names(init))
                indirect: list[str] = []
                if init is not None:
                    for callee in _called_names(init):
                        if callee in helpers:
                            indirect.append(f"{callee}()")
                        method = next((m for m in methods if m.name == callee), None)
                        if method is not None and _opened_names(method):
                            indirect.append(f"self.{callee}()")

                cached = _self_cached_handles(cls)
                if direct or indirect or cached:
                    found.append(
                        {
                            "module": module,
                            "file": path,
                            "class": cls.name,
                            "line": cls.lineno,
                            "direct": direct,
                            "indirect": sorted(set(indirect)),
                            "cached": cached,
                        }
                    )
    return found


OFFENDERS = find_offenders()

#: Classes marked in this change that the detector above does NOT flag, because
#: their constructor still requires a ``session``. Asserted anyway: this module
#: family is migrating to ``session: Session | None = None``, and such a class
#: becomes a live leak the moment that default lands.
ALSO_MARKED = {
    "secrets_manager": (
        "AuditService",
        "CertificateService",
        "CloudFederationService",
        "DynamicSecretsService",
        "EncryptionService",
        "EngineRegistryService",
        "EventService",
        "ImportExportService",
        "KubernetesService",
        "MonitoringService",
        "PluginService",
        "PolicyEngine",
        "ProxyService",
        "ReplicationService",
        "RotationService",
        "ScanningService",
        "SealService",
        "SshService",
        "VaultService",
    ),
    "external_platforms": (
        "DraftService",
        "ExportService",
        "GenerationHistoryService",
        "PipelineService",
        "SkillsService",
        "ToolInstanceService",
        "WritingProjectService",
    ),
}


def _dotted(path: pathlib.Path) -> str:
    rel = path.relative_to(COMMON_LIB_SRC).with_suffix("")
    return "common_lib." + ".".join(rel.parts)


def _real_class(item: dict):
    """Import the module and return the real class object."""
    mod = importlib.import_module(_dotted(item["file"]))
    return getattr(mod, item["class"], None)


def test_offender_discovery_is_not_empty():
    """Guard the guard: empty discovery would make every other test pass for
    the wrong reason."""
    assert OFFENDERS, (
        "no offenders found in " + ", ".join(MODULES) + " -- the detector is broken"
    )


def test_every_offender_declares_the_opt_out():
    offenders = "\n".join(
        f"  {o['file'].relative_to(COMMON_LIB_SRC)}:{o['line']} {o['class']} "
        f"direct={o['direct']} indirect={o['indirect']} cached={o['cached']}"
        for o in OFFENDERS
    )
    missing = []
    for o in OFFENDERS:
        cls = _real_class(o)
        assert cls is not None, f"{o['class']} not importable from {_dotted(o['file'])}"
        if getattr(cls, ATTR, False) is not True:
            missing.append(f"{o['file'].name}:{o['line']} {o['class']}")
    assert not missing, (
        "these classes can be constructed implicitly by node_bridge and hold a "
        "live resource, so they must declare "
        f"{ATTR} = True:\n" + "\n".join(missing) + "\n\noffenders:\n" + offenders
    )


def test_also_marked_classes_keep_the_opt_out():
    """The required-session classes stay marked; see ALSO_MARKED."""
    missing = []
    for module, names in ALSO_MARKED.items():
        for name in names:
            hits = [
                p for p in _module_files(module) if f"class {name}:" in p.read_text()
            ]
            assert hits, f"{module}.{name} no longer found on disk"
            mod = importlib.import_module(_dotted(hits[0]))
            cls = getattr(mod, name, None)
            assert cls is not None, f"{module}.{name} not importable"
            if getattr(cls, ATTR, False) is not True:
                missing.append(f"{module}.{name} ({hits[0].name})")
    assert not missing, f"lost {ATTR}:\n" + "\n".join(missing)


def test_bridge_would_not_construct_a_marked_no_arg_class():
    """Execution, not source inspection.

    ``BibleService`` is the worst case found: ``_get_session()`` opens an ORM
    session lazily and caches it on ``self``, and ``_bibles`` is a
    process-lifetime cache of project bibles keyed only by ``project_id``. With
    the attribute the real bridge constructs nothing; without it, the real
    bridge constructs one and pins it.
    """
    from app.mcp import node_bridge

    mod = importlib.import_module(
        "common_lib.modules.external_platforms.writing_studio.service"
    )
    cls = mod.BibleService
    func = cls.get_or_create_bible

    assert getattr(cls, ATTR, False) is True, "precondition"

    before = len(node_bridge._BOUND_INSTANCE_KEEPALIVE)
    node_bridge._bind_instance(mod, "BibleService.get_or_create_bible", func)
    grew_with = len(node_bridge._BOUND_INSTANCE_KEEPALIVE) - before
    assert grew_with == 0, (
        f"bridge constructed a marked class anyway (keepalive +{grew_with})"
    )

    delattr(cls, ATTR)
    try:
        before = len(node_bridge._BOUND_INSTANCE_KEEPALIVE)
        bound = node_bridge._bind_instance(
            mod, "BibleService.get_or_create_bible", func
        )
        grew_without = len(node_bridge._BOUND_INSTANCE_KEEPALIVE) - before
    finally:
        setattr(cls, ATTR, True)

    assert grew_without == 1, (
        "falsification leg: with the attribute removed the bridge did NOT "
        f"construct the class (keepalive +{grew_without}), so this test would "
        "pass even if the guard were broken"
    )
    assert inspect_is_method(bound), (
        "falsification leg: expected a bound method from the unmarked class"
    )
    # restore is asserted so a failure above cannot leak the mutation
    assert getattr(cls, ATTR, False) is True


def inspect_is_method(obj) -> bool:
    """True for a bound method -- i.e. the bridge really did construct the owner."""
    return inspect.ismethod(obj)


class _Stateless:
    """Module-level on purpose: the bridge resolves the owner by walking
    ``getattr(module, "ClassName")``, so a class defined inside a test function
    is not reachable as a module attribute and would never be bound."""

    def __init__(self) -> None:
        self.counter = 0

    def ping(self) -> int:
        return 1


def test_opt_out_is_not_blanket(monkeypatch):
    """A class with no resource must still be bindable -- otherwise the opt-out
    would silently hide working tools."""
    import sys

    from app.mcp import node_bridge

    monkeypatch.setattr(
        node_bridge, "_RESOLVE_INSTANCE", lambda owner: None, raising=False
    )
    before = len(node_bridge._BOUND_INSTANCE_KEEPALIVE)
    bound = node_bridge._bind_instance(
        sys.modules[__name__], "_Stateless.ping", _Stateless.ping
    )
    grew = len(node_bridge._BOUND_INSTANCE_KEEPALIVE) - before
    assert grew == 1, "a stateless no-arg class must still be implicitly bound"
    assert bound() == 1


def sys_module():
    import sys

    return sys.modules[__name__]
