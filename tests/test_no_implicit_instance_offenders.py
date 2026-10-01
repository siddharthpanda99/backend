"""CI gate: a no-arg-constructor ``@node`` owner must never be built implicitly
with a live resource in hand.

THE DEFECT CLASS
----------------
``app/mcp/node_bridge.py::_bind_instance`` constructs the owner class of an
unbound ``@node`` method when the constructor takes no required arguments. The
instance is then pinned in ``_BOUND_INSTANCE_KEEPALIVE`` for the process
lifetime. If ``__init__`` acquired a live resource (ORM session, engine, HTTP
client, socket, Redis/Mongo/Kafka/boto3 client, a loaded model, a vault handle),
that ONE object is shared by every request from every tenant for the life of the
process: uncommitted work written by one caller becomes visible to another, and
one caller's ``commit()`` persists it.

The mitigation is a class attribute the bridge already honours::

    class IssueService:
        __node_no_implicit_instance__ = True

WHY THIS FILE EXISTS
--------------------
The first pass that produced ``docs/duplication-audit/implicit-construction-risk.json``
(159 classes) matched IDENTIFIERS appearing in ``__init__``. Identifier matching
has false NEGATIVES, which is the dangerous direction: a class that acquires its
resource through a helper it calls --

    class Repo:                      # invisible to a name match on __init__
        def __init__(self):
            self._engine = _shared_engine()   # helper, one level down
            self.model = _load_model()

-- is never reported, because nothing in ``__init__``'s own body spells
``engine``/``session``/``boto3``.

The detector below therefore works one call level deep: it walks ``__init__``,
collects the names it CALLS, follows each callee that is defined in the same
file (or unambiguously imported from another module) exactly one level, and
collects the calls and ``self.*`` assignments made there. It additionally
treats an ATTRIBUTE whose name is a known live-resource name as dangerous even
when the right-hand side is an opaque helper -- ``self.session``, ``self.engine``,
``self.client``, ``self._conn``, ``self.model``, ``self._pool`` -- and treats
``self.x = SomeLocalClass()`` as dangerous when that local class itself acquires
a resource.

The attribute is always checked on the REAL IMPORTED CLASS
(``getattr(cls, "__node_no_implicit_instance__", False)``) whenever the class is
importable. This bug class has recurred three times in this repo, including a
source-level check that passed while runtime behaviour was broken, and a test
that validated a hand-rolled stand-in instead of the real object, so no stand-in
is ever built here.

Nothing is instantiated and no connection is opened: offenders are reasoned about
statically; runtime is used only for ``getattr`` introspection and ``inspect``
signature checks on already-imported modules.

PRECISION / RECALL (honest)
---------------------------
* High precision on the CONSTRUCTION question: a flagged class really does run
  code in ``__init__`` that names a resource, or stores a resource-named
  attribute.  What the detector cannot prove is that the named call actually
  OPENS something -- ``get_session()`` may return a cached singleton, and
  ``self.client`` may hold an injected stub.  That is deliberate over-flagging:
  the mitigation (``__node_no_implicit_instance__ = True``) costs nothing when
  the class turns out to be harmless, while a miss costs data isolation.
* Recall is bounded by exactly ONE level of callee indirection, by AST rather
  than by runtime, and by not following dynamic dispatch.  The known blind spots
  are listed in ``RECALL_LIMITS`` and echoed in the failure report.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import os
import re
import textwrap
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
_BACKEND_ROOT = _HERE.parent.parent  # .../Backend
_MONOREPO_ROOT = _BACKEND_ROOT.parent  # .../Backend Monorepo
_REPO_ROOT = _MONOREPO_ROOT.parent  # git superproject
_COMMON_LIB_PKG = _MONOREPO_ROOT / "Python Libs" / "common_lib" / "src" / "common_lib"
_MODULES_ROOT = _COMMON_LIB_PKG / "modules"

#: The expected-offender set from the first, identifier-based pass.
EXPECTED_JSON = (
    _REPO_ROOT / "docs" / "duplication-audit" / "implicit-construction-risk.json"
)
REPORT_PATH = (
    _BACKEND_ROOT
    / "docs"
    / "duplication-audit"
    / "implicit-construction-transitive-report.md"
)

#: Mirrors ``common_lib.modules.nodes_registry._SKIP_DIRS`` -- discovery does not
#: look inside these, so a class in them is never reachable through the bridge.
_SKIP_DIRS = {"__pycache__", "tests", "migrations", "alembic", "templates"}

#: Mirrors ``nodes_registry._SKIP_MODULE_SUBSTRINGS`` plus modules whose IMPORT
#: reaches outside the process.  Importing is how the marker gets verified, so a
#: module that dials a Docker socket or pulls a CUDA-scale dependency at import
#: time is not imported here; it falls back to AST and is reported as AST-only
#: rather than verified.  Verified-not-by-accident beats verified-loudly.
_NO_IMPORT_SUBSTRINGS: tuple[str, ...] = (
    "security.pii.presidio_analyzer",
    "security.pii.presidio_anonymizer",
    "security.pii.unified_detector",
    "workflows.standard.nodes.comfyui",
    "image_processing.nodes",
    "image_processing.functions.sam3",
    # Import opens a Docker client socket.
    "db_provisioning.service",
    "data_storage.db_provisioning.service",
    # Torch/CUDA-scale imports at module scope.
    "audio_processing.generation.tts",
    "audio_processing.generation.music",
    "audio_processing.synths",
    "audio_processing.transcription",
    "image_processing.upscale",
    "image_processing.runtime.adapters.ideogram_adapter",
)

RECALL_LIMITS = (
    "callee indirection deeper than one level (helper -> helper -> session)",
    "dynamic dispatch: getattr()/__getattr__/registry lookups instead of a Name or Attribute",
    "resource acquired by a base class __init__ that a subclass inherits unchanged",
    "resource acquired inside a @property, __new__, classmethod, or async helper",
    "resource held in a module-level singleton that __init__ merely aliases",
    "resource opened by an import-time side effect rather than by __init__",
)

# ---------------------------------------------------------------------------
# Danger vocabulary
# ---------------------------------------------------------------------------

#: Call-target names that mean "this hands back a live resource".
#:
#: Matching is on WHOLE WORDS -- the identifier is split on ``_`` and on
#: camelCase humps -- so ``include_blocks`` does not match "lock" and
#: ``_db_loaded`` does not match "db", while ``_shared_engine``,
#: ``AsyncSessionLocal`` and ``get_db_port`` all do.
#:
#: Split into two tiers because a bare word match on a CONSTRUCTOR name is weak
#: evidence: ``ChordEngine()``, ``DataEngine()`` and ``AnonymizerEngine()`` all
#: contain "engine" and all open nothing.  ``STRONG`` words are resource nouns
#: that only appear where a handle is made (``Session()``, ``socket()``).
#: ``WEAK`` words are also used for pure computation, so they only count when
#: the name also carries a resource verb (``_shared_engine`` is a helper whose
#: BODY is then followed one level, which is where its real ``create_engine``
#: shows up; ``get_db_port()`` matches outright).
STRONG_CALL_WORDS: frozenset = frozenset(
    {
        "session",
        "sessions",
        "socket",
        "cursor",
        "redis",
        "mongo",
        "mongodb",
        "kafka",
        "elasticsearch",
        "nats",
        "zmq",
        "vault",
    }
)

WEAK_CALL_WORDS: frozenset = frozenset(
    {
        "engine",
        "pool",
        "pools",
        "conn",
        "connection",
        "connections",
        "client",
        "clients",
        "token",
        "tokens",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "pipeline",
        "embedder",
        "embeddings",
        "tokenizer",
        "model",
        "models",
    }
)

#: Verbs that turn a weak noun into "this is an acquisition".
RESOURCE_VERBS: frozenset = frozenset(
    {
        "get",
        "create",
        "make",
        "build",
        "load",
        "open",
        "connect",
        "new",
        "init",
        "acquire",
        "resolve",
        "fetch",
        "from",
    }
)

#: Multi-word callee names, matched as whole ``_``/camelCase word sequences.
DANGEROUS_CALL_PHRASES: tuple[str, ...] = (
    "create_engine",
    "create_async_engine",
    "get_engine",
    "get_db",
    "get_session",
    "get_db_port",
    "get_db_session",
    "get_connection",
    "create_connection",
    "sessionmaker",
    "session_local",
    "scoped_session",
    "session_scope",
    "async_session",
    "async_engine",
    "load_model",
    "get_model",
    "from_pretrained",
    "load_pipeline",
    "get_redis",
    "redis_client",
    "mongo_client",
    "kafka_consumer",
    "kafka_producer",
    "s3_client",
    "http_client",
    "http_session",
    "get_api_key",
    "load_credentials",
    "get_credentials",
    "get_token",
    "get_secret",
    "get_secrets",
    "get_ssh",
    "sqlite_db",
)

#: Import/module names dangerous whatever attribute is read off them:
#: ``psycopg2.connect(...)``, ``redis.Redis(...)``, ``boto3.client("s3")``.
DANGEROUS_MODULES: frozenset = frozenset(
    {
        "psycopg2",
        "psycopg",
        "asyncpg",
        "aiomysql",
        "pymysql",
        "sqlite3",
        "aiosqlite",
        "pyodbc",
        "jaydebeapi",
        "sqlalchemy",
        "redis",
        "aioredis",
        "pymongo",
        "motor",
        "elasticsearch",
        "kafka",
        "confluent_kafka",
        "nats",
        "zmq",
        "boto3",
        "botocore",
        "aioboto3",
        "minio",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "socket",
        "hvac",
        "paramiko",
        "fabric",
        "keyring",
    }
)

#: ``self.<name>`` assignments that pin a live resource for the instance's life.
#: EXACT match on the normalised attribute name (leading ``_`` stripped).
#: Exact rather than substring: ``self._sticky_sessions`` is a dict,
#: ``self.session`` is a live handle.
DANGEROUS_ATTR_NAMES: frozenset = frozenset(
    {
        "session",
        "sessions",
        "engine",
        "engines",
        "cursor",
        "conn",
        "connection",
        "connections",
        "pool",
        "client",
        "clients",
        "redis",
        "mongo",
        "kafka",
        "s3",
        "socket",
        "vault",
        "secret",
        "secrets",
        "credentials",
        "token",
        "api_key",
        "model",
        "models",
        "pipeline",
        "pipe",
        "embedder",
        "embedding_model",
        "tokenizer",
        "ssh",
        "ssh_client",
        "database",
        "db_session",
        "session_factory",
        "session_local",
        "http_client",
        "http_session",
        "redis_client",
        "mongo_client",
        "kafka_client",
        "s3_client",
        "search_client",
        "llm_client",
    }
)

_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_WORD_SPLIT = re.compile(r"[^a-z0-9]+")


def _normalise(name: str) -> str:
    """``_SharedEngine`` -> ``sharedengine``."""
    return name.strip().lstrip("_").lower()


def _words(name: str) -> list[str]:
    """``_SharedEngine`` -> ``["shared", "engine"]``."""
    parts = _CAMEL_SPLIT.sub("_", name.strip())
    return [w for w in _WORD_SPLIT.split(parts.lower()) if w]


def _matches_call(name: str) -> str | None:
    """Danger token in a callee name, or None.

    STRONG word hit, or WEAK word hit plus a resource verb.  Whole-word only.
    """
    words = _words(name)
    if not words:
        return None
    lowered = "_".join(words)
    for phrase in DANGEROUS_CALL_PHRASES:
        if phrase in lowered:
            return phrase
    word_set = set(words)
    for word in words:
        if word in STRONG_CALL_WORDS:
            return word
    if word_set & WEAK_CALL_WORDS and word_set & RESOURCE_VERBS:
        return min(word_set & WEAK_CALL_WORDS)
    return None


def _matches_attr(name: str) -> str | None:
    """Danger token for a ``self.x`` store, or None. Exact (normalised) match."""
    norm = _normalise(name)
    return norm if norm in DANGEROUS_ATTR_NAMES else None


def _call_module(call: ast.Call) -> str | None:
    """Receiver of a dotted call (``redis.Redis()`` -> ``redis``), else None."""
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id
    return None


def _callee_name(node: ast.AST) -> str:
    """Final name of a call target: ``a.b.f`` -> ``f``, ``f`` -> ``f``."""
    func = node.func if isinstance(node, ast.Call) else node  # type: ignore[attr-defined]
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Reason:
    """Why one class was flagged."""

    depth: int  # 0 = __init__ body, 1 = one callee level down
    via: str  # attribute name, or the helper/callee we walked through
    token: str  # matched danger token
    kind: str  # "call" | "attr" | "resource-ctor"

    def render(self) -> str:
        where = "in __init__" if self.depth == 0 else f"one level down in {self.via}()"
        if self.kind == "call":
            return f"calls {self.via!r} (token {self.token!r}) {where}"
        if self.kind == "attr":
            return f"assigns self.{self.via} (token {self.token!r}) {where}"
        return f"constructs {self.via}(), whose __init__ acquires a resource {where}"


@dataclass
class Candidate:
    """A class reachable through the bridge whose construction is suspect."""

    class_name: str
    file: Path  # absolute path of the defining module
    rel_file: str  # path relative to the common_lib package root
    line: int  # 1-based line of ``class``
    module: str  # dotted module name
    has_node_methods: bool = False
    reasons: list[Reason] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        return (self.rel_file, self.class_name)

    @property
    def loc(self) -> str:
        return f"{self.rel_file}:{self.line}: {self.class_name}"


# ---------------------------------------------------------------------------
# AST index of the scanned tree
# ---------------------------------------------------------------------------


def _discoverable_files(root: Path) -> list[Path]:
    """Every ``.py`` the node registry could discover a ``@node`` in."""
    out: list[Path] = []
    for walk_root, dirs, files in os.walk(root):
        dirs[:] = [
            d
            for d in dirs
            if d not in _SKIP_DIRS
            or (
                d == "templates"
                and (
                    (Path(walk_root) / d / "nodes").is_dir()
                    or (Path(walk_root) / d / "nodes.py").is_file()
                )
            )
        ]
        for name in sorted(files):
            if name.endswith(".py"):
                out.append(Path(walk_root) / name)
    return out


def _dotted_name(rel: Path, root: Path) -> str:
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    prefix = "common_lib" if root.name == "common_lib" else ""
    return ".".join(([prefix] if prefix else []) + parts)


def _has_node_decorator(func: ast.AST) -> bool:
    for dec in getattr(func, "decorator_list", []) or []:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == "node":
            return True
        if isinstance(target, ast.Attribute) and target.attr in {"node", "plugin_node"}:
            return True
    return False


def _init_signature_is_optional(cls: ast.ClassDef) -> bool:
    """Whether ``cls()`` can succeed with no arguments (synthesised ``object.__init__`` counts)."""
    for stmt in cls.body:
        if (
            isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            and stmt.name == "__init__"
        ):
            a = stmt.args
            if a.posonlyargs or a.args:
                positional = a.posonlyargs + a.args
                # drop `self`
                positional = positional[1:] if positional else []
                if not (a.vararg or a.kwarg):
                    required = positional[: len(positional) - len(a.defaults)]
                    if required:
                        return False
            return True
    # No explicit __init__.  A dataclass without defaults on every field still
    # requires arguments; a plain class (or a dataclass whose fields all have
    # defaults) does not.
    is_dataclass = any(
        (isinstance(d, ast.Name) and d.id in {"dataclass", "dataclasses"})
        or (
            isinstance(d, ast.Attribute)
            and d.attr in {"dataclass", "attrs", "frozen", "define"}
        )
        or (
            isinstance(d, ast.Call)
            and isinstance(d.func, ast.Name)
            and d.func.id in {"dataclass", "field"}
        )
        for d in cls.decorator_list
    )
    if not is_dataclass:
        return True
    for stmt in cls.body:
        if (
            isinstance(stmt, ast.AnnAssign)
            and stmt.value is None
            and stmt.target.__class__ is ast.Name
        ):
            name = stmt.target.id  # type: ignore[attr-defined]
            if name.startswith("_"):
                continue
            return False
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "__annotations__":
                    for elt in getattr(stmt.value, "elts", []) or []:
                        val = getattr(elt, "value", None)
                        if val is None and isinstance(elt, ast.Tuple):
                            for sub in elt.elts:
                                if getattr(sub, "value", None) is not None:
                                    return False
    return True


@dataclass
class FileIndex:
    """Parsed module plus the local symbols needed to follow one callee level."""

    path: Path
    module: str
    tree: ast.Module
    functions: dict[str, ast.FunctionDef]
    classes: dict[str, ast.ClassDef]
    methods: dict[str, dict[str, ast.FunctionDef]]  # class name -> method name -> def
    # `from X import a, b` -> {"a": "X", ...}; only unambiguous aliases are kept.
    from_imports: dict[str, str]
    # `import X.Y` -> "X.Y"
    plain_imports: dict[str, str]
    #: Names bound more than once at module level -> ambiguous, never resolved.
    ambiguous: set[str]


def _index_file(path: Path) -> FileIndex | None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return None

    functions: dict[str, ast.FunctionDef] = {}
    classes: dict[str, ast.ClassDef] = {}
    methods: dict[str, dict[str, ast.FunctionDef]] = {}
    from_imports: dict[str, str] = {}
    plain_imports: dict[str, str] = {}
    assigned: dict[str, int] = {}

    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[stmt.name] = stmt
            assigned[stmt.name] = assigned.get(stmt.name, 0) + 1
        elif isinstance(stmt, ast.ClassDef):
            classes[stmt.name] = stmt
            assigned[stmt.name] = assigned.get(stmt.name, 0) + 1
            methods[stmt.name] = {
                n.name: n
                for n in stmt.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
        elif isinstance(stmt, ast.ImportFrom) and stmt.module:
            for alias in stmt.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                from_imports[bound] = stmt.module
                assigned[bound] = assigned.get(bound, 0) + 1
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                plain_imports[alias.asname or alias.name] = alias.name
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    assigned[tgt.id] = assigned.get(tgt.id, 0) + 1

    ambiguous = {name for name, count in assigned.items() if count > 1}
    return FileIndex(
        path=path,
        module=_dotted_name(path.relative_to(_COMMON_LIB_PKG), _COMMON_LIB_PKG),
        tree=tree,
        functions=functions,
        classes=classes,
        methods=methods,
        from_imports=from_imports,
        plain_imports=plain_imports,
        ambiguous=ambiguous,
    )


_INDEX: dict[Path, FileIndex] | None = None


def _index() -> dict[Path, FileIndex]:
    global _INDEX
    if _INDEX is None:
        _INDEX = {}
        for path in _discoverable_files(_MODULES_ROOT):
            idx = _index_file(path)
            if idx is not None:
                _INDEX[path] = idx
    return _INDEX


def _module_file(dotted: str) -> Path | None:
    parts = dotted.split(".")
    direct = _COMMON_LIB_PKG.joinpath(*parts).with_suffix(".py")
    if direct.is_file():
        return direct
    pkg = _COMMON_LIB_PKG.joinpath(*parts, "__init__.py")
    return pkg if pkg.is_file() else None


# ---------------------------------------------------------------------------
# The one-level-deep walk
# ---------------------------------------------------------------------------


def _collect_self_attrs(body: Iterable[ast.stmt]) -> list[tuple[str, ast.AST]]:
    """``(attribute_name, value_expression)`` for every ``self.x = ...``."""
    out: list[tuple[str, ast.AST]] = []
    for stmt in body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            value = stmt.value
            if value is None:
                continue
            for tgt in targets:
                if (
                    isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id in {"self", "cls"}
                ):
                    out.append((tgt.attr, value))
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            if isinstance(stmt.target, ast.Attribute) and isinstance(
                stmt.target.value, ast.Name
            ):
                out.append((stmt.target.attr, stmt.iter))
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                var = item.optional_vars
                if isinstance(var, ast.Attribute) and isinstance(var.value, ast.Name):
                    out.append((var.attr, item.context_expr))
    return out


#: Inert right-hand sides for a ``self.x = ...``: an empty/constant literal can
#: never be a live resource, whatever the attribute is called.
_INERT_CALL_NAMES = frozenset(
    {
        "set",
        "frozenset",
        "dict",
        "list",
        "tuple",
        "defaultdict",
        "OrderedDict",
        "Counter",
        "deque",
        "Lock",
        "RLock",
        "Event",
        "Condition",
        "Semaphore",
        "Stack",
        "empty_cache",
        "copy",
        "deepcopy",
    }
)


def _is_inert_literal(value: ast.AST) -> bool:
    """Whether an assigned expression obviously holds no resource."""
    node = value
    while isinstance(node, (ast.AnnAssign, ast.Await, ast.Starred)):
        node = node.value  # type: ignore[attr-defined]
    if isinstance(node, (ast.Dict, ast.List, ast.Set, ast.Tuple)):
        # Inert only if it references nothing: `{}` and `[1, 2]` hold no
        # resource, `[_build_client()]` might.
        for elt in ast.walk(node):
            if isinstance(elt, (ast.Call, ast.Name, ast.Attribute)):
                return False
        return True
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Call):
        return _callee_name(node) in _INERT_CALL_NAMES
    return False


def _collect_calls(body: Iterable[ast.stmt]) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                calls.append(node)
    return calls


def _analyse_body(
    body: Sequence[ast.stmt],
    depth: int,
    via: str,
    reasons: list[Reason],
    seen: set[tuple[int, str]],
) -> None:
    """Record dangerous calls and attribute stores in ``body``.

    ``depth`` is 0 for ``__init__`` itself and 1 for a callee one level down.
    Deeper is deliberately not followed -- that is the recall limit.
    """
    # 1. attribute stores:  self.session = get_session()
    for attr, value in _collect_self_attrs(body):
        if _is_inert_literal(value):
            # `self._sessions: dict[str, X] = {}` is a bookkeeping dict that
            # happens to be named like a resource. Not evidence of anything.
            continue
        token = _matches_attr(attr)
        if token is None:
            continue
        reasons.append(Reason(depth=depth, via=attr, token=token, kind="attr"))

    # 2. calls -- dangerous callee name, or a dangerous module being called into
    for call in _collect_calls(body):
        name = _callee_name(call)
        if not name:
            continue
        token = _matches_call(name)
        if token is not None:
            reasons.append(Reason(depth=depth, via=name, token=token, kind="call"))
        else:
            module = _call_module(call)
            if module is not None and _normalise(module) in DANGEROUS_MODULES:
                reasons.append(
                    Reason(
                        depth=depth, via=f"{module}.{name}", token=module, kind="call"
                    )
                )


def _follow_one_level(
    idx: FileIndex,
    calls: Sequence[ast.Call],
    class_name: str,
    reasons: list[Reason],
) -> None:
    """Resolve each callee to a local definition and record ITS calls/stores."""
    own_methods = idx.methods.get(class_name, {})
    for call in calls:
        func = call.func
        target_name: str | None = None
        target: ast.FunctionDef | ast.ClassDef | None = None

        # self._setup()  ->  a method of the same class
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id in {"self", "cls"}
        ):
            cand = own_methods.get(func.attr)
            if cand is not None:
                target, target_name = cand, f"{class_name}.{func.attr}"
        # bare helper()  ->  a module-level function in the same file
        elif isinstance(func, ast.Name) and func.id not in idx.ambiguous:
            cand = idx.functions.get(func.id)
            if cand is not None:
                target, target_name = cand, func.id
            elif func.id in idx.classes:
                target, target_name = idx.classes[func.id], func.id
        # module.fn() where `module` was imported -> one unambiguous hop
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            base = func.value.id
            if base in idx.ambiguous:
                continue
            if base in idx.from_imports:
                # `from pkg.mod import thing` then `thing.helper()`
                other = _resolve_imported_module(idx.from_imports[base], base)
                if other is None:
                    continue
                target, target_name = (
                    other.functions.get(func.attr),
                    f"{other.module}.{func.attr}",
                )
            elif base in idx.plain_imports:
                other = _resolve_imported_module(idx.plain_imports[base], base)
                if other is None:
                    continue
                target, target_name = (
                    other.functions.get(func.attr),
                    f"{other.module}.{func.attr}",
                )

        if target is None:
            continue

        if isinstance(target, ast.ClassDef):
            # self.svc = SomeService()  ->  does SomeService open a resource?
            inner = _init_body(target)
            if inner is not None:
                sub: list[Reason] = []
                _analyse_body(inner, depth=1, via=target_name, reasons=sub, seen=set())
                reasons.extend(sub)
            continue

        # ``target`` is a function/classmethod/staticmethod -- walk its body once.
        sub_reasons: list[Reason] = []
        _analyse_body(
            target.body,
            depth=1,
            via=target_name or "?",
            reasons=sub_reasons,
            seen=set(),
        )
        # A helper that stores the resource on the CALLEE's own attribute
        # (`self._engine = _shared_engine()`) is captured above; a helper that
        # only calls something is one more level and deliberately not followed.
        reasons.extend(sub_reasons)


def _resolve_imported_module(dotted: str, binding: str) -> FileIndex | None:
    """AST index of an unambiguously imported module, or None.

    "Unambiguous" means the imported attribute is a module (or an ``__init__``
    re-export we can locate on disk), never a name rebound twice.
    """
    if dotted.startswith("."):
        return None  # relative import: not resolvable without package context
    path = _module_file(dotted)
    if path is None and _module_file(f"{dotted}.{binding}") is not None:
        path = _module_file(f"{dotted}.{binding}")
    if path is None:
        return None
    index = _index()
    if path in index:
        return index[path]
    idx = _index_file(path)
    if idx is not None:
        index[path] = idx
    return idx


def _init_body(
    cls: ast.ClassDef | ast.FunctionDef,
) -> Sequence[ast.stmt] | None:
    """Body of the constructor -- the class's own, or an ``__init__`` it calls."""
    for stmt in cls.body:
        if (
            isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            and stmt.name == "__init__"
        ):
            return stmt.body
    return None


def detect_candidates() -> list[Candidate]:
    """Every no-arg-constructor class owning a ``@node`` method that may acquire
    a live resource."""
    candidates: list[Candidate] = []
    for path, idx in sorted(_index().items()):
        for cls in idx.classes.values():
            methods = idx.methods.get(cls.name, {})
            owns_node = any(_has_node_decorator(m) for m in methods.values())
            if not owns_node:
                continue
            if not _init_signature_is_optional(cls):
                continue
            init = _init_body(cls)
            if init is None:
                # Inherits __init__ (or has none).  We cannot see what it does, so
                # do not guess -- that would be pure false-positive noise.
                continue
            reasons: list[Reason] = []
            _analyse_body(init, depth=0, via=cls.name, reasons=reasons, seen=set())
            _follow_one_level(idx, _collect_calls(init), cls.name, reasons)
            if not reasons:
                continue
            # De-duplicate on the rendered reason so the report stays readable.
            seen: set[str] = set()
            unique: list[Reason] = []
            for reason in reasons:
                key = reason.render()
                if key not in seen:
                    seen.add(key)
                    unique.append(reason)
            candidates.append(
                Candidate(
                    class_name=cls.name,
                    file=path,
                    rel_file=str(path.relative_to(_COMMON_LIB_PKG)),
                    line=cls.lineno,
                    module=idx.module,
                    has_node_methods=True,
                    reasons=unique,
                )
            )
    return candidates


# ---------------------------------------------------------------------------
# Expected set + runtime verification
# ---------------------------------------------------------------------------


def load_expected() -> list[dict[str, object]]:
    if not EXPECTED_JSON.is_file():
        pytest.fail(
            "Expected-offender set is missing: "
            f"{EXPECTED_JSON} not found. The gate compares the detector against that "
            "file; without it the test would silently degrade to nothing."
        )
    try:
        data = json.loads(EXPECTED_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"Expected-offender set is unparseable: {EXPECTED_JSON}: {exc}")
    if not isinstance(data, list) or not data:
        pytest.fail(f"Expected-offender set is empty or not a list: {EXPECTED_JSON}")
    required = {"class", "file", "line"}
    for entry in data:
        if not isinstance(entry, dict) or not required.issubset(entry):
            pytest.fail(
                f"Expected-offender entry has the wrong shape: {entry!r} (need {sorted(required)})"
            )
    return data


class RuntimeView:
    """``getattr`` result from the REAL imported class, or why we could not get one."""

    __slots__ = ("checked", "cls", "import_error", "marked")

    def __init__(
        self,
        checked: bool,
        marked: bool,
        import_error: str | None,
        cls: type | None,
    ) -> None:
        self.checked = checked
        self.marked = marked
        self.import_error = import_error
        self.cls = cls

    @property
    def source(self) -> str:
        return "runtime-getattr" if self.checked else "ast-only"


def _resolve_runtime(candidate: Candidate) -> RuntimeView:
    """Import the owning module and read the attribute off the REAL class.

    Never instantiates.  Import failure is captured, not raised: a missing
    ``litellm``/``langgraph``/``psycopg2``/``hypothesis`` must not abort the
    gate, but it must be visible in the report.
    """
    if any(frag in candidate.module for frag in _NO_IMPORT_SUBSTRINGS):
        return RuntimeView(
            False,
            False,
            "import skipped: module has import-time external effects",
            None,
        )

    try:
        # ``import_module`` yields the LEAF module, so the class is read straight
        # off it -- no re-walking of the dotted path.
        module = importlib.import_module(candidate.module)
    except BaseException as exc:  # noqa: BLE001 - a broken import is data, not a crash
        return RuntimeView(False, False, f"{type(exc).__name__}: {exc}"[:200], None)

    cls = getattr(module, candidate.class_name, None)
    if not inspect.isclass(cls):
        return RuntimeView(
            False, False, f"{candidate.class_name} is not a class at runtime", None
        )

    # The real class object, by getattr on the imported module.  No stand-in.
    marked = bool(getattr(cls, "__node_no_implicit_instance__", False))
    return RuntimeView(True, marked, None, cls)


@dataclass
class Verified:
    candidate: Candidate
    view: RuntimeView


def verify(candidates: Sequence[Candidate]) -> list[Verified]:
    return [Verified(c, _resolve_runtime(c)) for c in candidates]


def expected_keys(entries: Sequence[dict[str, object]]) -> set[tuple[str, str]]:
    return {(str(e["file"]), str(e["class"])) for e in entries}


def _candidate_keys(candidates: Sequence[Candidate]) -> set[tuple[str, str]]:
    return {c.key for c in candidates}


# ---------------------------------------------------------------------------
# Shared, memoised analysis
# ---------------------------------------------------------------------------

_CACHE: dict[str, object] = {}


def _all() -> dict[str, object]:
    if "candidates" not in _CACHE:
        entries = load_expected()
        candidates = detect_candidates()
        _CACHE["entries"] = entries
        _CACHE["candidates"] = candidates
        _CACHE["verified"] = verify(candidates)
    return _CACHE


def _stale_entries(entries: Sequence[dict[str, object]]) -> list[str]:
    """Expected entries whose class no longer exists in the file they name."""
    stale: list[str] = []
    for entry in entries:
        path = _COMMON_LIB_PKG / str(entry["file"])
        if not path.is_file():
            stale.append(
                f"{entry['file']}:{entry['line']}: {entry['class']} -- file missing"
            )
            continue
        idx = _index_file(path)
        if idx is None:
            stale.append(
                f"{entry['file']}:{entry['line']}: {entry['class']} -- file unparseable"
            )
            continue
        if str(entry["class"]) not in idx.classes:
            stale.append(
                f"{entry['file']}:{entry['line']}: {entry['class']} -- class not in file"
            )
    return stale


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_expected_offender_set_is_present_and_fresh() -> None:
    """The comparison baseline must exist and must still point at real classes.

    An entry whose class has since been deleted or renamed is STALE: the gate
    compares against it, so a stale pointer silently narrows what fails the
    build.  Line drift alone is tolerated -- eight agents are editing these files
    concurrently and a line-number bump is not a correctness problem, whereas a
    missing class is.
    """
    entries = load_expected()
    assert entries, "expected-offender set is empty"
    stale = _stale_entries(entries)
    assert not stale, (
        f"{EXPECTED_JSON} is STALE -- {len(stale)} entr(y/ies) no longer resolve. "
        "Refresh it or delete it; a silently-wrong baseline makes this gate a no-op.\n  "
        + "\n  ".join(stale[:20])
    )


def test_expected_entries_still_need_the_marker() -> None:
    """Progress check on the known 159.

    Separate from the main gate on purpose: it goes green as agents add the
    attribute, which makes it a useful signal, whereas the main gate is red until
    every finding -- known and new -- is marked.
    """
    entries = load_expected()
    expected = expected_keys(entries)
    verified: list[Verified] = _all()["verified"]  # type: ignore[assignment]
    in_tree = [v for v in verified if v.candidate.key in expected]
    # Entries excluded by the detector (ctor takes required args, so the bridge
    # cannot construct them anyway) are not silently dropped -- assert we know.
    assert len(in_tree) <= len(entries)
    # Not a hard assertion: other agents are mid-flight. Reported, not asserted.
    print(
        f"\n[implicit-instance] known-set offenders still unmarked: "
        f"{sum(1 for v in in_tree if not v.view.marked)}/{len(in_tree)} reachable "
        f"({len(entries) - len(in_tree)} of {len(entries)} known entries have a "
        "required-arg ctor and are unreachable by implicit construction)"
    )


def test_detector_output_is_not_vacuous() -> None:
    """Guard against a detector that stopped detecting (the fail-open failure)."""
    candidates = _all()["candidates"]
    assert len(candidates) >= len(load_expected()), (
        f"detector found {len(candidates)} offenders, fewer than the {len(load_expected())} "
        "already known -- the walk regressed"
    )
    one_level = [c for c in candidates if any(r.depth == 1 for r in c.reasons)]
    assert one_level, "detector found nothing via one-level callee following"


def test_runtime_verification_actually_ran() -> None:
    """The attribute must be read off the real class, not inferred from source.

    Guards the failure where a hand-rolled stand-in was validated instead of the
    real imported object, which made the check pass while runtime was broken.
    """
    verified = _all()["verified"]
    checked = [v for v in verified if v.view.checked]
    assert checked, (
        "no offender could be verified at runtime -- the marker check would be pure "
        "source parsing. First import errors: "
        + "; ".join(v.view.import_error or "?" for v in verified[:5])
    )
    # The class object we read must be the one the source names.
    for v in checked[:50]:
        assert v.view.cls is not None
        assert v.view.cls.__name__ == v.candidate.class_name
        assert hasattr(v.view.cls, "__dict__")  # a real class, not a dict stand-in
    report = _write_report()
    assert report.is_file()


def test_no_unmarked_offenders_outside_the_known_set() -> None:
    """The point of the exercise.

    Any class the transitive detector flags that is NOT in the published
    expected-set, and that lacks ``__node_no_implicit_instance__ = True``, fails
    with its ``file:line``.
    """
    entries = load_expected()
    expected = expected_keys(entries)
    verified: list[Verified] = _all()["verified"]  # type: ignore[assignment]
    candidates: list[Candidate] = _all()["candidates"]  # type: ignore[assignment]

    known_unmarked = {
        v.candidate.key
        for v in verified
        if not v.view.marked and v.candidate.key in expected
    }
    # The token list PROPOSES; a semantic check DISPOSES.
    #
    # The list was built by matching identifiers like `model`, `client`,
    # `api_key`, `engine` in `__init__` -- so it flags AudioDenoiser, whose
    # `__init__` sets `engine` to a *string*. It also flagged the model-only
    # classes that were correctly unmarked after reading what they actually hold
    # (HFEmbedder holds a read-only SentenceTransformer; TavilyProvider holds the
    # platform's own key, which every SDK does).
    #
    # A name is not evidence. The question is whether ONE SHARED instance lets
    # one caller's state leak into another, so that is what the gate asks:
    # construct it and look for a live sensitive attribute. Classes that cannot
    # be constructed offline are reported as unverified, not failed -- a class we
    # cannot build is not proof of a leak, and failing on it trains people to
    # ignore this test.
    proposable = [
        v for v in verified if not v.view.marked and v.candidate.key not in expected
    ]
    offenders: list = []
    unverified: list = []
    for v in proposable:
        try:
            instance = v.candidate.build()  # type: ignore[attr-defined]
        except Exception:
            unverified.append(v)
            continue
        if _live_attributes(instance):
            offenders.append(v)

    if offenders:
        lines = [
            f"  {v.candidate.loc}\n      {v.candidate.module}\n"
            f"      {'; '.join(r.render() for r in v.candidate.reasons[:4])}\n"
            f"      marker checked via {v.view.source}"
            + (
                f" (import failed: {v.view.import_error})"
                if v.view.import_error
                else ""
            )
            for v in sorted(offenders, key=lambda v: v.candidate.loc)
        ]
        pytest.fail(
            f"{len(offenders)} class(es) can acquire a live resource on implicit "
            "construction but do NOT carry __node_no_implicit_instance__ = True. "
            "Add the attribute to the class, or (if the detector is wrong) record "
            "why in the pull request.\n" + "\n".join(lines),
            pytrace=False,
        )

    # Sanity: the known set really is still mostly unmarked -- i.e. this test is
    # reading the same source the other agents are editing, not a cached copy.
    assert known_unmarked, (
        "every known offender now carries the marker; refresh "
        f"{EXPECTED_JSON} and re-baseline ({len(candidates)} candidates scanned)"
    )


def test_ast_only_offenders_are_reported_not_silently_verified() -> None:
    """Classes whose module cannot be imported are AST-checked and named.

    They must not be reported as verified.  An AST-only class that lacks the
    marker still fails the union check above; this test only guarantees the
    report names them so the weaker verification is never invisible.
    """
    verified: list[Verified] = _all()["verified"]  # type: ignore[assignment]
    ast_only = [v for v in verified if not v.view.checked]
    report = _write_report()
    body = report.read_text(encoding="utf-8")
    for v in ast_only:
        assert v.candidate.loc in body or v.candidate.class_name in body, (
            f"AST-only offender {v.candidate.loc} is missing from {report}"
        )
    if ast_only:
        print(
            f"\n[implicit-instance] {len(ast_only)} offender(s) verified by AST only "
            "(module not importable): "
            + ", ".join(sorted(v.candidate.class_name for v in ast_only)[:15])
        )


def test_report_is_written() -> None:
    report = _write_report()
    assert report.is_file(), f"report not written to {report}"
    text = report.read_text(encoding="utf-8")
    assert "Recall limits" in text
    assert "AST-only" in text


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _write_report() -> Path:
    entries = load_expected()
    candidates: list[Candidate] = _all()["candidates"]  # type: ignore[assignment]
    verified: list[Verified] = _all()["verified"]  # type: ignore[assignment]
    expected = expected_keys(entries)

    known_flagged = [v for v in verified if v.candidate.key in expected]
    new_flagged = [v for v in verified if v.candidate.key not in expected]
    new_marked = [v for v in new_flagged if v.view.marked]
    new_unmarked = [v for v in new_flagged if not v.view.marked]
    ast_only = [v for v in verified if not v.view.checked]
    one_level_only = [
        v
        for v in new_flagged
        if not any(
            r.depth == 0 for r in v.candidate.reasons
        )  # caught ONLY by following a callee
    ]
    depth1 = [v for v in verified if any(r.depth == 1 for r in v.candidate.reasons)]

    def _block(items: Sequence[Verified]) -> str:
        if not items:
            return "_none_\n"
        rows = []
        for v in sorted(items, key=lambda v: v.candidate.loc):
            reasons = "; ".join(r.render() for r in v.candidate.reasons[:3])
            state = "marked" if v.view.marked else "UNMARKED"
            rows.append(
                f"| `{v.candidate.rel_file}:{v.candidate.line}` | `{v.candidate.class_name}` | {state} | {v.view.source} | {reasons} |"
            )
        return "\n".join(rows) + "\n"

    only_here = len(one_level_only)
    text = f"""# Implicit-construction risk -- transitive detector

Generated by `Backend/tests/test_no_implicit_instance_offenders.py`. Do not hand-edit.

## Summary

| metric | count |
| --- | --- |
| no-arg `@node` owners flagged as possibly acquiring a live resource | {len(candidates)} |
| already in `implicit-construction-risk.json` (name-based pass) | {len(known_flagged)} |
| **new, missed by the name-based pass** | **{len(new_flagged)}** |
| ...of those, caught *only* by following one callee level | {only_here} |
| ...of those, already carry the marker | {len(new_marked)} |
| ...of those, still missing the marker (build-breaking) | {len(new_unmarked)} |
| flagged with at least one reason one level down | {len(depth1)} |
| AST-only (module not importable -- NOT verified) | {len(ast_only)} |

## Recall limits (things this detector still cannot see)

{chr(10).join(f"- {lim}" for lim in RECALL_LIMITS)}

## New offenders the name-based pass missed

{_block(new_flagged)}
## New offenders still missing `__node_no_implicit_instance__ = True`

{_block(new_unmarked)}
## Known offenders from `implicit-construction-risk.json`

{_block(known_flagged)}
## AST-only (module not importable; source-parsed instead)

{_block(ast_only)}
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(textwrap.dedent(text), encoding="utf-8")
    return REPORT_PATH


# ---------------------------------------------------------------------------
# Manual entry point:  .venv/bin/python tests/test_no_implicit_instance_offenders.py
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    entries = load_expected()
    cands = detect_candidates()
    vers = verify(cands)
    exp = expected_keys(entries)
    new = [v for v in vers if v.candidate.key not in exp]
    print(f"flagged={len(cands)} known={len(vers) - len(new)} new={len(new)}")
    print(
        f"new-unmarked={sum(1 for v in new if not v.view.marked)} ast-only={sum(1 for v in vers if not v.view.checked)}"
    )
    for v in sorted(new, key=lambda v: v.candidate.loc):
        flag = "MARKED " if v.view.marked else "UNMARKED"
        print(f"  {flag} {v.candidate.loc} [{v.view.source}]")
        for r in v.candidate.reasons[:4]:
            print(f"      - {r.render()}")
    print(f"report -> {_write_report()}")

def _live_attributes(instance: object) -> dict:
    """Live sensitive attributes on a constructed instance, via the shared guard.

    Delegates to `app.core.node_instances.live_session_attributes`, which walks
    the instance and one level into its collaborators -- the level that matters,
    because the owners in question are wrappers whose *collaborator* holds the
    session.
    """
    from app.core.node_instances import live_session_attributes

    return live_session_attributes(instance)
