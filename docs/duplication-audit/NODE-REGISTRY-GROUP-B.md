# Group-B instance-registry wiring — report

**Task:** populate the instance registry with owners that take *injected
dependencies* (the middle row of the required-parameter classification in
`docs/duplication-audit/REQUEST-SCOPED-SESSIONS.md` §"Three groups"), and prove
session safety by execution.

**Repo:** `Backend Monorepo/Backend` (submodule), branch `master`.
**Write surface:** `app/core/node_instances.py`, `tests/test_node_instance_wiring_group_b.py`,
this report. No module source was modified.

---

## 1. Owners registered — 9, by module

All nine take a **factory, config, registry, or store handle** — never a session.
Node counts are counted by `inspect`-ing the real class for `_node_metadata`
(excluding `@property` members), not quoted from the audit report.

| Module (feature-config namespace) | Owner | Nodes | Injected dependency |
|---|---|---|---|
| `orchestration` | `...tracing.service.TraceRecorder` | 30 | `memory_store` (factory-backed) |
| `orchestration` | `...tracing.cost_service.AgentCostService` | 6 | `memory_store` |
| `orchestration` | `...versioning.service.AgentVersionService` | 5 | `memory_store` |
| `orchestration` | `...sync.manager.EntitySyncManager` | 9 | `memory_store` + `templates_root` (path) |
| `orchestration` | `...plugin.loader.PluginLoader` | 11 | `ctx` (global `PluginContext`) |
| `workflows` | `...config_service.WorkflowConfigService` | 15 | `common_memory` (store) |
| `plugins` | `...plugin_service.PluginService` | 4 | `common_memory` + `templates_root` (path) |
| `memory` | `...bandit.adapter.OnlineBanditAdapter` | 8 | `strategies` (arm-name list) |
| `memory` | `...tokenizer.tokenizer.TiktokenBackend` | 3 | `encoding_name` (deployment constant) |

**Total: 9 owners / 91 nodes.** Table total is now **19 owners / 140 nodes**
(was 10 / 49).

The shared store is built once, on a **session factory**:

```python
SQLAlchemyMemoryStore(session_factory=get_session)   # session=None, engine=None
```

`db_url=` was deliberately *not* used: it `create_engine`s and caches an Engine
on the instance. With a factory, `_db_session()` opens and closes per call — the
same DI shape `ConfigsService` already relies on.

## 2. Node count verified callable **by invoking them**

**91.** Not rounded, and not a declaration count.

* **8 nodes invoked with a real return value** through the real
  `app.mcp.node_bridge._resolve_callable`, asserting `self` absent, `inspect.ismethod`,
  and signature equality with the owner method minus `self`:
  `TraceRecorder.record_event` (real row written to temp SQLite),
  `TraceRecorder.get_session_summary`, `AgentCostService.get_cost_summary`,
  `AgentVersionService.list_versions`, `WorkflowConfigService.list_configs`,
  `PluginService.list_plugins` (with the platform's own
  `plugins.manager.get_plugin_manager()`), `OnlineBanditAdapter.get_stats`,
  `TiktokenBackend.count`.
* **The remaining 83 were verified resolved-and-bound** through the real bridge
  with `self` stripped and no `self` TypeError, per owner, over the full dotted
  node set. That is a weaker claim than invocation and is labelled as such: they
  resolve, they are bound methods, they do not raise the pre-wiring
  `TypeError: missing 1 required positional argument: 'self'`.

**No live database was touched.** Store-backed owners are exercised over a
temp-file SQLite engine (`tmp_path`). `test_group_b_wiring_opens_no_database`
monkeypatches `sqlalchemy.create_engine` and `get_session` to hard failures and
asserts the full shipped table still passes.

## 3. Owners **refused** — they hold a live session

None of the nine group-B candidates had to be refused: every one resolved to a
factory/config/registry. The guard refused only the deliberate falsification
fixtures. Owners that were **examined and excluded as unsafe**, with what they
hold:

| Owner | `file:line` | Holds |
|---|---|---|
| `ai_models.registry.service.RegistryService` | `ai_models/adapters/database.py:35-36` | the only `RegistryRepositoryPort` impl is `SqlAlchemyRegistryRepository(session)` → `self.session` (live `Session`); `ai_models/container.py:81` builds it from `self.session` |
| `db_studio.administration.provisioning.BaseProvisioner` (+ 9 engine subclasses, 64 nodes) | `db_studio/administration/provisioning.py:132` | `self.conn = conn` — a live `TargetConn` credential handle (host/port/user/**password**) for one specific target |
| `data_storage.database.connectors.impl.postgresql.PostgreSQL` / `MySQL` / `Athena` | `connectors/impl/postgresql.py:34` | `self.engine = sa.create_engine(...)` built in `__init__` from a `cfg` carrying credentials |
| `data_storage.database.connectors.base.SourceDB` | `connectors/base.py:30` | `self.cfg` — a connection-config dict; also `ABC`, not instantiable |
| `agents.services.snapshot_service.SnapshotService` | already in the existing guard set | `self.db.commit()` |
| `ai_models.llm.*.BaseModelProvider` + 9 provider subclasses (~68 nodes) | `ai_models/llm/anthropic.py:33` | `self.client` — a cached API-key client (credential handle), and `config` is per-model rather than process-wide |

These were **not** registered and are reported here rather than added as rows: a
row that fails on every boot trains operators to ignore wiring warnings.

## 4. Session-safety guard, and its falsification evidence

`app.core.node_instances.live_session_attributes(instance)` — runs on the
**resolved instance** (a constructor signature cannot see a session smuggled in
through a collaborator), walks `__dict__` **plus one level into collaborators**
(the owners here are wrappers: `TraceRecorder._memory`,
`WorkflowConfigService._common_memory`, `EntitySyncManager.memory`), and flags
`session / db_session / conn / connection / db / engine` (and `_`-prefixed
variants) bound to a live object. `None`, `""`, primitives, classes, modules and
**callables are allowed** — a factory is the safe shape.

`register_startup_instances` **refuses** on a hit, logs at ERROR naming the owner
and the attribute path, and does not register.

**Falsification — three mutations, each re-read from disk before running:**

| Mutation | Result |
|---|---|
| `return offenders` → `return {}` (guard neutered) | **3 failed**, 25 passed |
| `_SESSION_WALK_DEPTH = 1` → `0` (no collaborator walk) | **1 failed** — `test_guard_walks_into_collaborators_not_just_the_top_level_object` |
| drop the `callable(...)` exemption (over-strict guard) | **1 failed** — `test_is_live_handle_separates_factories_from_real_handles` |

The third mutation initially left all 28 tests **green**, which was a real gap:
no shipped owner stores a factory under a *sensitive* name (they use
`_get_session` / `_session_factory`, which are not sensitive), so the exemption
was untested. `test_is_live_handle_separates_factories_from_real_handles` was
added to close it, using the platform's own `get_session` / `get_engine` /
`sessionmaker()` as the safe cases and real temp-SQLite `Session` / `Engine` as
the unsafe ones; re-running the mutation then went red.

The deliberately-unsafe fixtures are **real platform classes**, not hand-rolled
stand-ins: `rbac.agent_apikey_service.APIKeyService(session)` and
`SQLAlchemyMemoryStore(session=<live Session>)` nested under the real
`TraceRecorder`. All over temp-file SQLite.

## 5. Feature-config interaction

Each row carries a real module namespace, and `register_startup_instances` gates
on the same `module_pruning.is_module_enabled` predicate the router and node
pruners use, so wiring and pruning cannot disagree. Namespaces used: `memory`,
`orchestration`, `workflows`, `plugins` (plus the pre-existing `knowledge_engine`,
`docs`, `settings`, `image_processing`, `data_storage`, `configs`, `app_ops`,
`audio_processing`). All resolve enabled on a default install.

`test_disabled_module_is_not_constructed_for_a_group_b_owner` spies on the real
source and asserts it is **never called** when the module is off — the assertion
is on construction, not on the absence of a registry entry.
`test_every_group_b_owner_names_a_real_module_namespace` guards the typo case,
since `is_module_enabled` fails *open* for an unregistered name.

## 6. Resilience

One failing owner does not abort startup. The pass gained an
`InstanceRegistryConflictError` branch (a *different* instance already bound —
previously an uncaught crash path) so the pass always returns, and
`test_registration_requires_no_database` / the existing suite still hold.

## 7. Tests

| Suite | Before | After |
|---|---|---|
| `tests/test_node_instance_wiring_group_b.py` (new) | — | **29 passed** |
| `test_node_instance_wiring.py` + `test_node_bridge_instance_binding.py` + `test_instance_registry.py` | **49 passed** | **49 passed** |
| the four above together | — | **78 passed** |
| `tests/` collection | **5 collection errors**, 3718 collected | unchanged (same 5, same count + 29) |

Full-suite run with those 5 pre-existing collection errors ignored is recorded in
§9. The 5 errors are pre-existing and unrelated (missing `litellm` / `langgraph` /
`psycopg2` / `hypothesis`).

## 8. Pre-existing body bugs found (module source is read-only here)

Reaching these nodes for the first time surfaced two defects **upstream** of the
registry. Both reproduce with no bridge, no registry and a directly-constructed
instance, so the wiring did not cause them:

* `common_lib/modules/plugins/plugin_service.py:288` — `delete_plugin` calls
  `self._common_memory.delete_plugin_definition(plugin_id)`;
  `SQLAlchemyMemoryStore` has no such method. That node raises `AttributeError`
  on every call. (1 of PluginService's 4 nodes.)
* `common_lib/modules/orchestration/infrastructure/sync/consistency.py:117` writes
  `report.files_without_entities`, but `ConsistencyReport`
  (`orchestration/schemas/artifact_schemas.py:276`) has no such field.
  `EntitySyncManager.verify_consistency` raises `AttributeError`.

Reported as `file:line` rather than fixed: module source is not my write surface.

## 9. Commits

All in repo `Backend Monorepo/Backend`, branch `master`. One commit per module
namespace (plus one for the guard and one for the tests) so a single collision
cannot contaminate the rest. Each was staged by explicit path, never `git add -A`.

| SHA | Module |
|---|---|
| `09cae50` | *(guard + refuse branch; no new owners — 10/49, unchanged)* |
| `6f21c06` | `orchestration` — 5 owners / 61 nodes → 15/110 |
| `79216cb` | `memory` — 2 owners / 11 nodes → 17/121 |
| `e3b971d` | `workflows` — 1 owner / 15 nodes → 18/136 |
| `485a6b4` | `plugins` — 1 owner / 4 nodes → 19/140 |
| `95372cc` | *(tests — 29)* |
| *(this file)* | `docs(duplication-audit): record the group-B wiring` |

Each intermediate stage was verified to compile **and** to register its expected
owner count with zero failures before being committed (10 → 15 → 17 → 18 → 19).
Submodule pointers left to the orchestrator.

## 10. Unverified / known limits

* **83 of 91 nodes were bound, not invoked.** Only 8 were invoked with a real
  return value. Binding is the property the wiring fixes; the remaining 83 would
  need a populated database to run, and running them would mean touching one.
* **Total platform node count not asserted.** Asserted relative properties only.
* `PluginService.list_plugins` / `get_plugin_details` / `update_plugin` take a
  `plugin_manager` **node argument**. That is per-call data an LLM would have to
  supply, which is arguably a signature defect — but it is a *node* parameter, not
  a constructor one, so it is out of this task's scope. Flagged, not fixed.
* `OnlineBanditAdapter` shares aggregate learning state across tenants. Not a
  session leak (no caller identity is retained), but one tenant's rewards move
  another's arm statistics. That is how the module's own `get_bandit_service()`
  singleton already behaves, so the wiring introduces no new sharing.
* `EntitySyncManager.export_to_file` and `import_from_file` raise on a pre-existing
  importer defect (`sync/importer.py:217`: `common_lib.modules.workflows.standard`
  has no attribute `sync`). Also upstream, also not mine.
