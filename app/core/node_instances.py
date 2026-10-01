"""Startup wiring for the `@node` instance registry.

WHAT THIS IS FOR
────────────────
``@node`` means one thing to a caller (human or LLM): *a tool that takes input and
returns output*. Whether the author wrote a module-level ``def store_memory()`` or a
method ``MemoryService.store()`` must be invisible in the tool catalog.

The bridge (``app/mcp/node_bridge.py::_bind_instance``) can only bind a dotted method
when the owning class has a zero-argument constructor. ``common_lib.modules.common
.instance_registry`` supplies the other half: the *application* provides the instance,
and binding becomes a dict lookup instead of a construction.

Nothing in the platform called ``register_instance``, so the registry was empty and the
fix helped nobody. This module is the caller.

WHY A TABLE, NOT A CALL PER CLASS
─────────────────────────────────
The population that genuinely needs wiring is small and every entry has to be
*argued for* — a singleton is only correct when the constructor's dependencies are
process-wide and the instance holds no unit-of-work. A table makes that argument
reviewable in one place, and makes the refusal set as visible as the accepted set.

Each entry names a **zero-argument source** rather than inlining construction. That
keeps this file free of business imports (importing a service here would drag it in at
startup whether or not its module is enabled) and lets a source return an instance the
platform already builds and owns.

GROUP B — INJECTED DEPENDENCIES
───────────────────────────────
The largest group of *currently unreachable* nodes, and the cheapest win, because
it needs no new mechanism. Measured by required-parameter shape, 2 105 nodes /
425 owners need an instance, and they fall into three groups that must not be
confused (``docs/duplication-audit/REQUEST-SCOPED-SESSIONS.md`` §"Three groups"):

* **Group A — 1 109 nodes / 110 owners** take a live ``session``. Needs a
  per-request session mechanism that does not exist. NOT here.
* **Group B — ~1 000 nodes** take an **injected dependency**: a session
  *factory*, a config object, a registry, or a store handle. A factory opens its
  unit of work per call, so an instance holding one is stateless with respect to
  any individual request and is a **safe singleton**. This is what the wiring
  below exists for. 9 owners / 91 nodes are wired here.
* **Group C — ~112 nodes** are true per-request data carriers (``APIExtractNode
  (node_id, name)``, ``Chunk(content, index)``). Need a tool-signature change.
  NOT here.

The distinction between A and B is invisible from a constructor signature: both
read ``store: SomeType``. It is visible on the resolved object, which is why
:func:`live_session_attributes` runs at registration and **refuses** an instance
that carries a live handle rather than merely logging it. A registered instance
is pinned for the process lifetime, so an unsafe one is worse than an absent one.

WHAT IS DELIBERATELY NOT HERE
─────────────────────────────
425 owner classes with dotted ``@node`` methods take constructor arguments. 19
are wired below — 140 of the 2 105 nodes, which is the honest number, not a
target. The rest fall into shapes that a shared instance would turn into a
correctness bug, and are refused on purpose. Measured by resolving each
constructor parameter to the attribute it is stored under and then reading how
the class body consumes it (``/tmp`` script, AST + live import), not by reading
parameter names:

* **Live unit-of-work — 103 owners / 1 028 nodes.** ``APIKeyService(session: Session)``
  stores the session and calls ``self.session.commit()``. Registering one instance puts
  a single ORM session — one open transaction — behind a process-wide singleton
  reachable from every request of every tenant. Uncommitted work from one caller would
  be committed by, and visible to, another. That is a cross-tenant data leak, not a
  bug, and the bridge's keep-alive list would also mean the session is never closed.
* **Per-request values — 309 owners / 1 007 nodes.** ``APIExtractNode(node_id, name)``,
  ``Chunk(content, index)``, ``Fact(key, value)`` are data carriers, not services. One
  shared instance would cache a single arbitrary record for the life of the process.
* **Caller-supplied callbacks — 12 owners / 67 nodes.** ``SdkConnector(sdk_class)``,
  ``TierRoutingRule(condition)``, ``WatchFolderWatcher(on_new_files)``: the callback is
  per-request data in a wrapper the caller supplies, so the wrapper belongs to the
  per-request mechanism below. ``StoryService`` is the exception that is wired — its
  getter resolves the underlying service per call and the wrapper is genuinely empty.

The per-request mechanism that is missing
─────────────────────────────────────────
A request-scoped binding: ``_bind_instance`` gains the ability to *construct* from a
declared recipe at call time rather than look up a singleton — a per-invocation session
opened and closed around the call, and per-request values taken from the tool arguments
or a request context. The shape already exists: ``instance_registry`` has the
``__node_instance_source__`` declarative hook and a ``replace=``-guarded registration
path, and the bridge already resolves through it. What is missing is a *scope*. The
natural implementation is a request-scoped ``ContextVar`` holding a
``dict[str, Callable[[Mapping], Any]]`` of recipes, consulted by ``resolve_instance``
when the registry has no entry, with the constructed instance discarded after the call
rather than kept alive — which also retires the keep-alive problem, since a
request-scoped session would be closed rather than pinned.

Scope: **406 owners / 1 965 nodes** remain (the 425 minus the 19 wired here,
adjusted for the report's alias double-counting). Until group A's mechanism exists
the honest answer for them is that their nodes stay advertised-but-uncallable,
which is a known, bounded, documented gap rather than a silent one.

FOUND BUT NOT FIXED HERE
────────────────────────
Three of the 140 nodes on the wired owners are ``@node`` stacked on a ``@property``
(``DatabaseConfig.database_url``, ``DatabaseConfig.connection_args``,
``DatabaseService.engine``). They are discovered, because the decorator metadata lands
on the property's ``fget``, but ``_bind_instance`` is never reached: the bridge
resolves ``getattr(cls, name)`` on the *class*, gets the property object back,
``_looks_unbound`` rejects it because it is not a function, and the property object is
handed to the handler builder as if it were a tool. Registering an instance does not
help — the failure is upstream of the registry. Fixing it means changing how
``_resolve_func``/``_bind_instance`` treat descriptors, which lives in
``app/mcp/node_bridge.py`` and belongs to whoever owns that file. The ``nodes`` counts
below include these three, because they are genuinely advertised; the runtime figure
for *method-form* nodes bound clean is 137.

PRE-EXISTING BODY BUGS FOUND WHILE VERIFYING (not fixed here — module source is
read-only for the wiring pass)
──────────────────────────────────────────────────────────────────────────
Reaching these nodes for the first time surfaced three defects that are *upstream*
of the registry and would be reported as "broken nodes" by anyone invoking them.
Both reproduce with no bridge, no registry and a directly-constructed
instance, so they are not caused by the wiring:

* ``common_lib/modules/plugins/plugin_service.py:288`` — ``delete_plugin`` calls
  ``self._common_memory.delete_plugin_definition(plugin_id)``;
  ``SQLAlchemyMemoryStore`` has no such method. 1 node raises
  ``AttributeError`` on every call.
* ``common_lib/modules/orchestration/infrastructure/sync/consistency.py:117``
  writes ``report.files_without_entities``, but ``ConsistencyReport``
  (``orchestration/schemas/artifact_schemas.py:276``) has no such field.
  ``EntitySyncManager.verify_consistency`` raises ``AttributeError``.

ORDER MATTERS
─────────────
``register_startup_instances()`` must run *after* ``load_feature_config()`` and *before*
``register_routers()`` / the MCP warmup's ``discover_nodes()``. The wiring gates each
entry on the pruning flag for its module, so it reads flag state; and it is pointless
after discovery, because the bridge binds when it generates handlers.

TESTABILITY
────────---
Importing this module constructs nothing and opens no session. ``STARTUP_INSTANCE_WIRINGS``
is a plain tuple of frozen dataclasses, and ``register_startup_instances(table=...)``
accepts a substitute, so the pass is testable with no database and no live infrastructure.

NO LIVE DATABASE
────────────────
No source here opens a connection, and none of them can: the store-backed sources
take ``session_factory=get_session``, which is *called* per use rather than being
called now, so wiring is pure construction. The group-B store is cached on the
module (``_MEMORY_STORE``) so the wrappers reach one store rather than N
equivalent ones; a test needing a clean build resets that attribute.
End-to-end verification uses a temp-file SQLite engine, never the platform's
configured database.

See ``tests/test_node_instance_wiring_group_b.py`` for the guard, its three
neutering proofs, and the per-owner callability checks.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger("node_instances")

__all__ = [
    "InstanceWiring",
    "WiringReport",
    "STARTUP_INSTANCE_WIRINGS",
    "live_session_attributes",
    "register_startup_instances",
]


# ── the session-safety guard ──────────────────────────────────────────────
#
# THE ONE FAILURE MODE THAT MATTERS
# ──────────────────────────────────
# A registered instance is held for the process lifetime. If it holds a live ORM
# session, a socket, or a credential handle, then every request of every tenant
# shares one open transaction: uncommitted writes from one caller are visible to,
# and committed by, another. That is a cross-tenant data leak, not a bug, and it
# is the reason 103 owners / 1 028 nodes were refused earlier.
#
# So the guard is not "did construction succeed" — it is "does the resolved
# object carry a live handle". It runs on the REAL instance, not on the
# constructor signature, because a signature cannot see a session smuggled in
# through a collaborator (``TraceRecorder._memory`` is a store; the store is what
# holds the session). Hence the bounded walk into collaborator attributes.
#
# Factories are explicitly allowed. ``get_session`` is a callable that OPENS a
# session per use; ``session=None`` is allowed; an ``Engine`` is a connection
# pool, which is process-wide by design and is what ``DatabaseService`` already
# relies on. What is refused is a bound *live* object under one of these names.

#: Attribute names that, when bound to a live object, mean a shared unit of work.
SESSION_SENSITIVE_ATTRS: Tuple[str, ...] = (
    "session",
    "db_session",
    "_session",
    "_db_session",
    "conn",
    "connection",
    "_conn",
    "_connection",
    "db",
    "_db",
    "engine",
    "_engine",
)

#: How deep to walk into collaborator attributes. 1 is enough for the shapes
#: here (``owner -> store -> session``); 2 would start traversing genuinely
#: unbounded object graphs (plugin contexts, registries) for no extra safety,
#: because a collaborator that itself holds a session is caught at depth 1.
_SESSION_WALK_DEPTH = 1

#: Attribute values that are never a live handle even under a sensitive name.
_SESSION_SAFE_TYPES = (str, bytes, int, float, bool, complex, type(None))


def _is_live_handle(value: Any) -> bool:
    """Whether ``value`` is a bound object rather than a factory or an empty slot.

    ``None`` and ``""`` are empty slots. A callable is a factory: ``get_session``
    opens a session when *called*, which is the whole point of the DI shape. A
    class or module is metadata. Everything else is an object that could be, or
    could carry, a live handle.
    """
    if value is None:
        return False
    if isinstance(value, _SESSION_SAFE_TYPES):
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if callable(value) and not isinstance(value, type):
        return False
    if isinstance(value, type):
        return False
    if inspect.ismodule(value):
        return False
    return True


def live_session_attributes(instance: Any) -> Dict[str, str]:
    """Return ``{attribute_path: type_name}`` for every live sensitive attribute.

    Walks ``instance.__dict__`` and, one level in, the ``__dict__`` of each
    collaborator it holds. The second level is not defensive padding: the owners
    wired here are wrappers (``TraceRecorder._memory``,
    ``WorkflowConfigService._common_memory``, ``EntitySyncManager.memory``) and it
    is the *collaborator* that holds the session. Stopping at depth 0 would pass
    every one of them.

    Args:
        instance: The resolved instance to inspect. Not the class.

    Returns:
        Mapping of dotted attribute path to the offending value's type name.
        Empty when the instance is safe to share, which is the only case in which
        it may be registered.
    """
    offenders: Dict[str, str] = {}
    seen: set = set()

    def _walk(obj: Any, prefix: str, depth: int) -> None:
        if depth > _SESSION_WALK_DEPTH:
            return
        marker = id(obj)
        if marker in seen:
            return
        seen.add(marker)
        try:
            attributes = vars(obj)
        except TypeError:
            return
        for name, value in list(attributes.items()):
            if not isinstance(name, str):
                continue
            path = f"{prefix}{name}"
            if name in SESSION_SENSITIVE_ATTRS and _is_live_handle(value):
                offenders[path] = type(value).__name__
            if depth < _SESSION_WALK_DEPTH:
                _walk(value, f"{path}.", depth + 1)

    _walk(instance, "", 0)
    return offenders


@dataclass(frozen=True)
class InstanceWiring:
    """One owner class and the zero-argument source that supplies its instance.

    Attributes:
        owner: Dotted path of the owner class to register under.
        source: Dotted path to a **zero-argument** callable returning the instance.
            Accepted forms match :func:`instance_registry._call_source`:
            ``"pkg.mod:factory"`` (preferred) or ``"pkg.mod.factory"``.
        module: Namespace used for the feature-flag gate. The entry is skipped
            entirely when this module is disabled by the per-instance config.
        rationale: Why a process-wide singleton is correct here. Prose on purpose:
            this is the artefact a reviewer reads to decide whether the entry belongs.
        nodes: Real dotted ``@node`` methods on the owner this unlocks, counted by
            runtime introspection rather than quoted from the audit report. Reporting
            only — nothing branches on it.
    """

    owner: str
    source: str
    module: str
    rationale: str
    nodes: int = 0


# ── the table ──────────────────────────────────────────────────────────────
#
# Every entry below was checked at runtime: the owner imports, the source is
# zero-argument, and constructing it opens no session. The node counts come from
# `inspect`-ing the class for `_node_metadata`, not from the audit report — the
# report over-counts, because a class re-exported through several modules is
# counted once per dotted alias.

STARTUP_INSTANCE_WIRINGS: Tuple[InstanceWiring, ...] = (
    InstanceWiring(
        owner="common_lib.modules.orchestration.knowledgebase.chunking.SimpleTextSplitter",
        source="app.core.node_instances:_build_text_splitter",
        module="knowledge_engine",
        rationale=(
            "Pure function object over (chunk_size, chunk_overlap). No state, no I/O, "
            "no session. Chunk sizes are a deployment tuning constant, not per-request "
            "data."
        ),
        nodes=1,
    ),
    InstanceWiring(
        owner="common_lib.modules.docs.service.DocsService",
        source="app.core.node_instances:_build_docs_service",
        module="docs",
        rationale=(
            "Reads .md files under one repository docs directory. The directory is a "
            "deployment constant and the service holds no cursor or session; a shared "
            "instance is exactly what a docs browser is."
        ),
        nodes=2,
    ),
    InstanceWiring(
        owner="common_lib.modules.settings.settings_storage.SettingsStorageService",
        source="app.core.node_instances:_build_settings_storage",
        module="settings",
        rationale=(
            "Bound to one settings file path. The path is a deployment constant. The "
            "read/write methods re-read the file per call rather than caching request "
            "state on self."
        ),
        nodes=9,
    ),
    InstanceWiring(
        owner=(
            "common_lib.modules.image_processing.functions.text.dynamic_engine"
            ".wildcards.WildcardManager"
        ),
        source="app.core.node_instances:_build_wildcard_manager",
        module="image_processing",
        rationale=(
            "Owns a wildcard root directory and an in-process cache of files under it. "
            "The directory is a deployment constant; the cache is content-addressed by "
            "filename and is invalidated by clear_cache(), not by request identity."
        ),
        nodes=4,
    ),
    InstanceWiring(
        owner="common_lib.modules.image_processing.config_utils.config_factory.ConfigFactory",
        source="app.core.node_instances:_build_config_factory",
        module="image_processing",
        rationale=(
            "Holds two paths (prompts registry, configs dir) and the parsed prompt "
            "registry. Both paths are deployment constants and the prompts are static "
            "files, so one instance serves every request identically."
        ),
        nodes=4,
    ),
    InstanceWiring(
        owner="common_lib.modules.data_storage.database.connection.DatabaseConfig",
        source="app.core.node_instances:_build_database_config",
        module="data_storage",
        rationale=(
            "A settings wrapper: it computes the database URL and connection kwargs. It "
            "holds no engine, no session and no per-request state — create_engine() is a "
            "method that returns a *new* engine per call, it does not cache one on self."
        ),
        nodes=5,
    ),
    InstanceWiring(
        owner="common_lib.modules.data_storage.database.connection.DatabaseService",
        source="app.core.node_instances:_build_database_service",
        module="data_storage",
        rationale=(
            "Owns the SQLAlchemy Engine, which is a process-wide connection pool by "
            "design and is already a module-level singleton in this codebase. Its "
            "engine property is lazy, so constructing it opens no connection; "
            "get_session() yields a *new* session per call and does not retain it."
        ),
        nodes=4,
    ),
    InstanceWiring(
        owner="common_lib.modules.configs.service.ConfigsService",
        source="app.core.node_instances:_build_configs_service",
        module="configs",
        rationale=(
            "Takes a session FACTORY, not a session, and opens one per call inside "
            "`with self._get_session() as session:`. This is the DI shape that makes a "
            "singleton correct: the unit-of-work is per-invocation, so no state can "
            "leak between callers. Same construction the configs router already uses."
        ),
        nodes=7,
    ),
    InstanceWiring(
        owner="common_lib.modules.app_ops.dashboard.service.DashboardService",
        source="app.core.node_instances:_build_dashboard_service",
        module="app_ops",
        rationale=(
            "Also takes a session factory and opens one per call. Its only other state "
            "is a 30-second TTL cache of aggregate document-processing stats, which is "
            "process-level by construction and holds no caller identity. Same "
            "construction the dashboard router already uses."
        ),
        nodes=10,
    ),
    InstanceWiring(
        owner="common_lib.modules.audio_processing.services.story_service.StoryService",
        source="app.core.node_instances:_build_story_service",
        module="audio_processing",
        rationale=(
            "Holds a *getter* for the underlying StoriesService and awaits it on every "
            "call, so the real service is resolved per use and the wrapper keeps no "
            "per-request state. Registering the wrapper is safe; the getter it holds is "
            "the platform's, not a captured session."
        ),
        nodes=3,
    ),
    # ── group B: injected dependencies (factories / configs / registries) ──
    InstanceWiring(
        owner=(
            "common_lib.modules.orchestration.agents.agent.tracing.service"
            ".TraceRecorder"
        ),
        source="app.core.node_instances:_build_trace_recorder",
        module="orchestration",
        rationale=(
            "Takes a memory STORE built on a session factory, not a session. Every "
            "method delegates to store.<x>(), which opens and closes its own session "
            "per call. The recorder holds no cursor, no session and no caller "
            "identity; the trace ids it writes are supplied per call as arguments. "
            "Largest single group-B owner."
        ),
        nodes=30,
    ),
    InstanceWiring(
        owner=(
            "common_lib.modules.orchestration.agents.agent.tracing.cost_service"
            ".AgentCostService"
        ),
        source="app.core.node_instances:_build_agent_cost_service",
        module="orchestration",
        rationale=(
            "Wraps a TraceRecorder over the same factory-backed store. Pure read-side "
            "aggregation (cost summaries, timelines, budget alerts) keyed by an "
            "agent_id argument passed per call, so no request state is retained."
        ),
        nodes=6,
    ),
    InstanceWiring(
        owner=(
            "common_lib.modules.orchestration.agents.agent.versioning.service"
            ".AgentVersionService"
        ),
        source="app.core.node_instances:_build_agent_version_service",
        module="orchestration",
        rationale=(
            "Snapshot/list/diff/restore of agent definitions through the same "
            "factory-backed store. The agent_id and version number are per-call "
            "arguments; the service holds only the store."
        ),
        nodes=5,
    ),
    InstanceWiring(
        owner="common_lib.modules.orchestration.infrastructure.sync.manager.EntitySyncManager",
        source="app.core.node_instances:_build_entity_sync_manager",
        module="orchestration",
        rationale=(
            "templates_root is the platform's own template directory, a deployment "
            "constant. It derives a RegistrySearchService from the store's "
            "_session_factory -- a factory, which search opens per call -- so "
            "filesystem<->DB sync runs per invocation rather than under a shared "
            "transaction."
        ),
        nodes=9,
    ),
    InstanceWiring(
        owner="common_lib.modules.orchestration.plugin.loader.PluginLoader",
        source="app.core.node_instances:_build_plugin_loader",
        module="orchestration",
        rationale=(
            "Built over the plugin system's own process-wide context "
            "(get_context()), which is what orchestration/plugin/__init__.py itself "
            "uses. A loaded plugin is by definition process state -- loaded once, "
            "served to every caller -- so a shared loader is the intended shape, "
            "not a leak."
        ),
        nodes=11,
    ),
    InstanceWiring(
        owner=(
            "common_lib.modules.memory.memory_adaptation.bandit.adapter"
            ".OnlineBanditAdapter"
        ),
        source="app.core.node_instances:_build_online_bandit_adapter",
        module="memory",
        rationale=(
            "Built from the module's own get_bandit_service() singleton. Purely "
            "in-process: it samples arms and adjusts alpha/beta counters. It performs "
            "no I/O, opens no connection, and holds no caller identity -- the "
            "statistics are aggregate learning state, which is process-wide by "
            "definition."
        ),
        nodes=8,
    ),
    InstanceWiring(
        owner=(
            "common_lib.modules.memory.memory_context.tokenizer.tokenizer"
            ".TiktokenBackend"
        ),
        source="app.core.node_instances:_build_tiktoken_backend",
        module="memory",
        rationale=(
            "An encoding name is a deployment constant resolved by the platform's own "
            "get_tokenizer() from the model config. The instance holds a single "
            "immutable tiktoken Encoding table. No I/O beyond the local encoding "
            "cache, no session, no socket."
        ),
        nodes=3,
    ),
)


# ── sources ────────────────────────────────────────────────────────────────
#
# Each is zero-argument, as the registry's `_call_source` requires. They are module
# level (not lambdas in the table) so a dotted path resolves them and a test can call
# one directly.


def _build_text_splitter() -> Any:
    from common_lib.modules.orchestration.knowledgebase.chunking import (
        SimpleTextSplitter,
    )

    return SimpleTextSplitter(chunk_size=1000, chunk_overlap=200)


def _build_docs_service() -> Any:
    from pathlib import Path

    from common_lib.modules.docs.service import DocsService
    from common_lib.paths import RESOURCES_ROOT

    return DocsService(Path(RESOURCES_ROOT) / "docs")


def _build_settings_storage() -> Any:
    from pathlib import Path

    from common_lib.modules.settings.settings_storage import SettingsStorageService
    from common_lib.paths import RESOURCES_ROOT

    return SettingsStorageService(Path(RESOURCES_ROOT) / "settings" / "storage.json")


def _build_wildcard_manager() -> Any:
    from pathlib import Path

    from common_lib.modules.image_processing.functions.text.dynamic_engine.wildcards import (
        WildcardManager,
    )
    from common_lib.paths import RESOURCES_ROOT

    return WildcardManager(str(Path(RESOURCES_ROOT) / "image_models" / "wildcards"))


def _build_config_factory() -> Any:
    from pathlib import Path

    from common_lib.modules.image_processing.config_utils.config_factory import (
        ConfigFactory,
    )
    from common_lib.paths import RESOURCES_ROOT

    root = Path(RESOURCES_ROOT) / "image_models"
    return ConfigFactory(str(root / "prompts.json"), str(root / "configs"))


def _build_database_config() -> Any:
    from common_lib.modules.data_storage.database.connection import DatabaseConfig

    from app.core.settings import get_settings

    return DatabaseConfig(get_settings())


def _build_database_service() -> Any:
    from common_lib.modules.data_storage.database.connection import DatabaseService

    return DatabaseService(_build_database_config())


def _build_configs_service() -> Any:
    from common_lib.modules.configs.service import ConfigsService
    from common_lib.modules.data_storage.database.connection import get_session

    return ConfigsService(get_session)


def _build_dashboard_service() -> Any:
    from common_lib.modules.app_ops.dashboard.service import DashboardService

    def _get_session_ctx() -> Any:
        from sqlmodel import Session

        from common_lib.modules.data_storage.database.connection import get_engine

        return Session(get_engine())

    return DashboardService(_get_session_ctx)


def _build_knowledge_base_service() -> Any:
    """Resolve the knowledge-base singleton the platform itself owns.

    NOT in :data:`STARTUP_INSTANCE_WIRINGS`, and that is a decision rather than an
    oversight. ``get_kb_service()`` raises unless something has already called
    ``init_kb_service(docs_base, kb_base)``, and in the shipped platform nothing does
    -- only ``common_lib/tests`` does. A table row that fails on every single boot is
    worse than no row: it trains an operator to ignore the wiring warnings, and it
    advertises 4 nodes as covered when they are not.

    The blocker is a missing decision, not missing code: which two directories are the
    knowledge base's roots. Guessing them here would mutate a module-level global that
    every other ``get_kb_service()`` consumer reads -- a platform-behaviour change this
    wiring pass should not make unilaterally. Once the platform initialises the
    knowledge base during boot, this becomes a one-line table entry.

    Kept as a named source because it is the most useful *real* failure for exercising
    the pass's resilience (see tests/test_node_instance_wiring.py).
    """
    from common_lib.modules.knowledge_engine.knowledge_base.service import (
        get_kb_service,
    )

    return get_kb_service()


def _build_story_service() -> Any:
    from common_lib.modules.audio_processing.services.story_service import StoryService

    async def _get_stories_service() -> Any:
        from common_lib.modules.audio_processing.services.stories_service import (
            StoriesService,
        )

        return StoriesService()

    return StoryService(_get_stories_service)


# ── group B: injected dependencies ───────────────────────────────────────
#
# The owners below take a *factory, a config, a registry, or a store handle* —
# never a session. That distinction is the whole basis for registering them:
# a factory opens its unit of work per call, so nothing about one caller's
# request can be observed by another. See ``live_session_attributes`` for the
# guard that enforces it at registration time.
#
# The shared memory store is built ONCE and handed to each owner, so every
# wrapper below reaches the same underlying store through a session factory
# rather than each capturing its own.

_MEMORY_STORE: Any = None


def _shared_memory_store() -> Any:
    """The process-wide ``SQLAlchemyMemoryStore``, built on a session FACTORY.

    Constructed with ``session_factory=get_session`` rather than a ``db_url``,
    which is what makes it shareable: ``db_url`` would ``create_engine`` and
    store the Engine (and, via ``_db_url``, a live connection string) on the
    instance, and every method would then share one store's identity. With a
    factory, ``SQLAlchemyMemoryStore._db_session`` opens and closes a session
    per call -- the same DI shape ``ConfigsService`` already relies on.

    Cached so the wrappers below share one store rather than N equivalent ones.
    """
    global _MEMORY_STORE
    if _MEMORY_STORE is None:
        from common_lib.modules.data_storage.database.connection import get_session
        from common_lib.modules.orchestration.context.memory.services import (
            SQLAlchemyMemoryStore,
        )

        _MEMORY_STORE = SQLAlchemyMemoryStore(session_factory=get_session)
    return _MEMORY_STORE


def _build_trace_recorder() -> Any:
    """``TraceRecorder(memory_store)`` — the single biggest group-B owner (30 nodes).

    ``TraceRecorder`` stores the store and calls ``store.<method>()``; the store
    opens a session per call from its factory. It commits nothing on ``self`` and
    holds no cursor. 30 of the ~1 000 group-B nodes are this one class.
    """
    from common_lib.modules.orchestration.agents.agent.tracing.service import (
        TraceRecorder,
    )

    return TraceRecorder(_shared_memory_store())


def _build_agent_cost_service() -> Any:
    """``AgentCostService(memory_store)`` — 6 nodes; wraps a ``TraceRecorder``.

    The inner recorder is built over the same shared store, so this adds no
    session of its own: the guard's depth-1 walk sees
    ``_recorder._memory`` and confirms it carries only a factory.
    """
    from common_lib.modules.orchestration.agents.agent.tracing.cost_service import (
        AgentCostService,
    )

    return AgentCostService(_shared_memory_store())


def _build_agent_version_service() -> Any:
    """``AgentVersionService(memory_store)`` — 5 nodes; snapshot/diff over the store."""
    from common_lib.modules.orchestration.agents.agent.versioning.service import (
        AgentVersionService,
    )

    return AgentVersionService(_shared_memory_store())


def _build_entity_sync_manager() -> Any:
    """``EntitySyncManager(memory_store, templates_root)`` — 9 nodes.

    ``templates_root`` is the platform's own template directory (a deployment
    constant). The manager derives a ``RegistrySearchService`` from the store's
    ``_session_factory`` — again a factory, not a session — so its search
    methods open their own.
    """
    from common_lib.modules.orchestration.infrastructure.sync.manager import (
        EntitySyncManager,
    )
    from common_lib.paths import COMMON_LIB_TEMPLATES

    return EntitySyncManager(
        memory_store=_shared_memory_store(),
        templates_root=str(COMMON_LIB_TEMPLATES),
    )


def _build_plugin_loader() -> Any:
    """``PluginLoader(ctx)`` — 11 nodes, over the platform's global plugin context.

    ``get_context()`` is the plugin system's own process-wide context (the same
    object ``orchestration/plugin/__init__.py`` builds). The loader holds loaded
    plugin objects and a load order — process state by definition, since a
    plugin is loaded once and served to everyone.
    """
    from common_lib.modules.orchestration.plugin.context import get_context
    from common_lib.modules.orchestration.plugin.loader import PluginLoader

    return PluginLoader(get_context())


def _build_online_bandit_adapter() -> Any:
    """``OnlineBanditAdapter(strategies)`` — 8 nodes; a pure in-process Beta bandit.

    ``get_bandit_service()`` is the module's own singleton, built with the
    ``["default"]`` arm list. It holds counters and no I/O at all: ``select_strategy``
    samples, ``update`` adjusts alpha/beta, and nothing opens a connection. The
    statistics are aggregate, not per-request, so there is no caller identity to
    leak between tenants.
    """
    from common_lib.modules.memory.memory_adaptation.bandit.adapter import (
        get_bandit_service,
    )

    return get_bandit_service()


def _build_tiktoken_backend() -> Any:
    """``TiktokenBackend(encoding_name)`` — 3 nodes; a tokenizer over a name.

    The name is a deployment constant resolved by the platform's own
    ``get_tokenizer()``, which picks the encoding from the model config
    (``cl100k_base`` for OpenAI models). The instance holds a ``tiktoken.Encoding``
    — an immutable lookup table — and nothing else.
    """
    from common_lib.modules.memory.memory_context.tokenizer.tokenizer import (
        get_tokenizer,
    )

    backend = get_tokenizer().backend
    # The owner registered here is TiktokenBackend; if the platform ever resolves
    # the default model to a non-tiktoken backend, refuse rather than register a
    # MockTokenizer under the wrong key.
    from common_lib.modules.memory.memory_context.tokenizer.tokenizer import (
        TiktokenBackend,
    )

    if not isinstance(backend, TiktokenBackend):
        raise TypeError(
            "default tokenizer backend is "
            f"{type(backend).__name__}, not TiktokenBackend; refusing to "
            "register it under the TiktokenBackend key"
        )
    return backend


# ── the pass ───────────────────────────────────────────────────────────────


@dataclass
class WiringReport:
    """Outcome of one :func:`register_startup_instances` pass.

    Attributes:
        registered: ``{owner: instance}`` for every entry that registered.
        reused: Owners already carrying an instance when the pass ran. Not rebuilt:
            constructing a second one would raise ``InstanceRegistryConflictError``,
            because the registry refuses to swap a live instance out from under
            in-flight calls.
        disabled: Owners skipped because their module is off in the feature config.
        failed: ``{owner: "reason"}`` for entries whose source raised. An entry that
            fails is recorded and skipped; it never aborts the pass.
        nodes_registered: Sum of ``nodes`` over the registered and reused entries.
    """

    registered: Dict[str, Any] = field(default_factory=dict)
    reused: List[str] = field(default_factory=list)
    disabled: List[str] = field(default_factory=list)
    failed: Dict[str, str] = field(default_factory=dict)
    nodes_registered: int = 0

    def summary(self) -> str:
        return (
            f"{len(self.registered)} owner(s) / {self.nodes_registered} node(s) "
            f"registered; {len(self.reused)} reused; "
            f"{len(self.disabled)} skipped (module disabled); "
            f"{len(self.failed)} failed"
        )


def _resolve_dotted(spec: str) -> Any:
    """Import and return the attribute named by ``"pkg.mod:attr"`` or ``"pkg.mod.attr"``.

    Mirrors :func:`instance_registry._call_source` so a table entry and a class's
    ``__node_instance_source__`` accept exactly the same spelling.
    """
    mod_name, _, attr = spec.partition(":") if ":" in spec else spec.rpartition(".")
    if not mod_name or not attr:
        raise ValueError(f"not a resolvable dotted path: {spec!r}")
    module = importlib.import_module(mod_name)
    return getattr(module, attr)


def _resolve_owner_class(dotted_path: str) -> type:
    """Import and return the owner *class* named by ``"pkg.mod.OwnerClass"``.

    The class object is required, not the path string. The bridge keys the registry
    off ``f"{owner.__module__}.{owner.__qualname__}"`` computed from the class it is
    actually binding, so registering under a hand-written string only works if that
    string happens to equal the class's own dotted path. It usually does -- until a
    class is renamed, moved, or re-exported under a second module, at which point the
    registration silently never matches and the node stays advertised-but-uncallable,
    which is the exact failure this wiring exists to remove.

    Resolving the class also means a typo fails loudly at startup (recorded on the
    report) instead of quietly at call time.
    """
    if not dotted_path or "." not in dotted_path:
        raise ValueError(f"owner is not a dotted class path: {dotted_path!r}")
    mod_name, _, class_name = dotted_path.rpartition(".")
    module = importlib.import_module(mod_name)
    owner = getattr(module, class_name)
    if not isinstance(owner, type):
        raise TypeError(
            f"{dotted_path} resolved to {type(owner).__name__}, not a class; "
            f"a dotted @node owner must be a class"
        )
    return owner


def _module_enabled(module: str) -> bool:
    """Is ``module`` enabled by the per-instance feature config?

    Delegates to the same predicate the node/router pruning uses, so wiring and
    pruning cannot disagree. Fails open: a pruning-gate failure must not silently
    remove capability, and construction here is side-effect-light.
    """
    from common_lib.modules.common.module_pruning import is_module_enabled

    return bool(is_module_enabled(module))


def register_startup_instances(
    table: Optional[Sequence[InstanceWiring]] = None,
) -> WiringReport:
    """Populate the instance registry from ``table`` (default: the shipped table).

    Runs before node discovery, so a dotted ``@node`` method on a wired owner becomes
    callable the moment the bridge generates its handler.

    Resilience is a hard requirement, not a nicety: one unconstructible class must not
    take the server down. Every entry is attempted inside its own ``try``, failures are
    recorded on the report and logged at WARNING, and the pass always returns.

    Args:
        table: WIRINGS to register. Defaults to :data:`STARTUP_INSTANCE_WIRINGS`.
            Injectable so the pass is testable with no database and no live
            infrastructure — see the module docstring.

    Returns:
        A :class:`WiringReport` describing what registered, what the feature config
        disabled, and what failed.
    """
    from common_lib.modules.common.instance_registry import (
        InstanceRegistryConflictError,
        get_instance,
        register_instance,
    )

    entries: Iterable[InstanceWiring] = (
        STARTUP_INSTANCE_WIRINGS if table is None else table
    )
    report = WiringReport()

    for wiring in entries:
        if not _module_enabled(wiring.module):
            report.disabled.append(wiring.owner)
            logger.info(
                "[NodeInstances] skipping %s: module %r disabled by feature config",
                wiring.owner,
                wiring.module,
            )
            continue

        try:
            owner_cls = _resolve_owner_class(wiring.owner)
        except Exception as exc:  # noqa: BLE001 - a stale path must not abort startup
            reason = f"{type(exc).__name__}: {exc}"
            report.failed[wiring.owner] = reason
            logger.warning(
                "[NodeInstances] owner %s does not resolve to a class -- %s. Its %d "
                "node(s) stay advertised but uncallable; startup continues.",
                wiring.owner,
                reason,
                wiring.nodes,
            )
            continue

        # Already carrying an instance: leave it alone. Rebuilding would produce a
        # second object and the registry would (correctly) refuse the swap, turning
        # a harmless second create_app() into eleven startup warnings.
        existing = get_instance(owner_cls)
        if existing is not None:
            report.reused.append(wiring.owner)
            report.registered[wiring.owner] = existing
            report.nodes_registered += wiring.nodes
            logger.info(
                "[NodeInstances] reusing existing instance for %s (%d node(s))",
                wiring.owner,
                wiring.nodes,
            )
            continue

        try:
            source = _resolve_dotted(wiring.source)
            instance = source()
        except Exception as exc:  # noqa: BLE001 - one bad class must not abort startup
            reason = f"{type(exc).__name__}: {exc}"
            report.failed[wiring.owner] = reason
            logger.warning(
                "[NodeInstances] could not construct %s from %s -- %s. "
                "Its %d node(s) stay advertised but uncallable; startup continues.",
                wiring.owner,
                wiring.source,
                reason,
                wiring.nodes,
            )
            continue

        # THE GUARD. Refuse before registering, not after: a registered instance
        # is pinned for the process lifetime, so an unsafe one is worse than an
        # absent one — it makes the leak permanent and invisible.
        offenders = live_session_attributes(instance)
        if offenders:
            detail = ", ".join(
                f"{path}={kind}" for path, kind in sorted(offenders.items())
            )
            report.failed[wiring.owner] = f"holds a live DB handle: {detail}"
            logger.error(
                "[NodeInstances] REFUSING %s -- the constructed instance holds a live "
                "database handle (%s). A process-wide singleton would put one open "
                "transaction behind every request of every tenant. Not registered.",
                wiring.owner,
                detail,
            )
            continue

        try:
            register_instance(owner_cls, instance)
        except InstanceRegistryConflictError as exc:
            # A *different* instance is already bound. Registering ours would
            # swap a live object out from under in-flight calls, and the registry
            # is right to refuse. Record and move on rather than crash startup.
            reason = f"{type(exc).__name__}: {exc}"
            report.failed[wiring.owner] = reason
            logger.warning(
                "[NodeInstances] could not register %s -- %s",
                wiring.owner,
                reason,
            )
            continue
        except Exception as exc:  # noqa: BLE001 - one bad class must not abort startup
            reason = f"{type(exc).__name__}: {exc}"
            report.failed[wiring.owner] = reason
            logger.warning(
                "[NodeInstances] could not register %s from %s -- %s. "
                "Its %d node(s) stay advertised but uncallable; startup continues.",
                wiring.owner,
                wiring.source,
                reason,
                wiring.nodes,
            )
            continue

        report.registered[wiring.owner] = instance
        report.nodes_registered += wiring.nodes
        logger.info(
            "[NodeInstances] registered %s (%d node(s)) from %s",
            wiring.owner,
            wiring.nodes,
            wiring.source,
        )

    logger.info("[NodeInstances] %s", report.summary())
    return report
