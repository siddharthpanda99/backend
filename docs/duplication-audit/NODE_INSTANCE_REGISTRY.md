# Node Instance Registry — design, blocker, and measurements

**Status:** registry built and tested; **end-to-end binding is BLOCKED** on
`app/mcp/node_bridge.py`, which is owned by a concurrent session and was not
modified.

Machine-readable companion: `node_instance_registry_report.json` (same directory).
Harness: `Backend/scripts/instance_registry_harness.py`.

---

## 1. Verdict on current instance binding

**Binding is OFF by default, and even when ON it cannot bind a class whose
`__init__` takes arguments.**

| Fact | Evidence |
|---|---|
| Gate defaults OFF | `app/mcp/node_bridge.py:234` — `os.environ.get("MCP_BIND_NODE_INSTANCES", "")`; empty string is not in the accepted set, so absent ⇒ OFF. |
| Only unbound methods are touched | `app/mcp/node_bridge.py:157` `_looks_unbound` — requires first param `self`/`cls`. |
| Binding is `owner()`, no args | `app/mcp/node_bridge.py:210` — `instance = owner()`. |
| Failure is swallowed | `app/mcp/node_bridge.py:211` — `except Exception: return func`, so the node stays advertised and uncallable. |
| Resolution is **call-time** | `app/mcp/node_bridge.py:425-426` — the generated handler body calls `_resolve_callable(...)` on every invocation, not once at registration. |

Verified empirically, not just by reading:

```
>>> class Demo:
...     def __init__(self, session, db): ...
>>> Demo()
TypeError: Demo.__init__() missing 2 required positional arguments: 'session' and 'db'
```

So the "~330 nodes" framing understates the problem in one direction and
overstates it in another. The real numbers are below. Note the two failure
modes are **independent**: turning the env var on helps only zero-arg classes.

## 2. The blocker (primary finding)

**There is no seam in `node_bridge.py` that a `common_lib` registry can be
honoured through without editing that file.** Two candidate seams were examined
and both are dead ends:

- **`owner()` at line 210.** Unreachable. For a required-arg constructor Python
  raises `TypeError` while *calling the class object*, before any user code in
  the class body or the registry can run. Line 211 swallows it and returns the
  unbound function. A registry cannot intercept this.
- **Late binding at call time (line 425).** This is the right *timing* and is
  what makes a registry viable in principle — but the handler bakes in
  `module` and `qualname` as string literals and calls `_resolve_callable`,
  which never consults anything outside `node_bridge.py`.

Demonstrated directly: with an instance **registered and available**, the
dotted handler still fails.

```
{'error': "MemoryService.store() missing 1 required positional argument: 'self'"}
```

This is pinned as a `pytest.mark.xfail(strict=True)` test
(`test_registered_instance_would_make_dotted_handler_run`). `strict=True` means
that the moment the blocker is lifted the suite reports XPASS and the marker
must be deleted.

### Minimal proposal for `node_bridge.py` (NOT applied)

In `_bind_instance`, before the `owner()` attempt:

```python
from common_lib.modules.common.instance_registry import resolve_instance

instance = resolve_instance(owner)
if instance is None:
    try:
        instance = owner()          # existing behaviour, unchanged
    except Exception:
        return func
```

Two points that matter to the owner of that file:

1. **The registry lookup should not be behind `MCP_BIND_NODE_INSTANCES`.**
   Registering an instance is an explicit act by application startup; it needs
   no env gate. The gate should continue to govern only *constructing* instances
   that nobody registered, since that is the part with side effects.
2. **On failure, prefer the diagnostic.** `describe_unregistered_owner(owner)`
   returns a message naming the class, its missing constructor arguments, and
   the remedy. Returning that instead of the bare function would convert the
   current misleading `missing 1 required positional argument: 'self'` into an
   actionable error for all ~2,100 affected nodes at zero extra risk.

## 3. The registry

`Python Libs/common_lib/src/common_lib/modules/common/instance_registry.py`

| API | Behaviour |
|---|---|
| `register_instance(owner, instance, *, replace=False)` | Registers by class. Idempotent for the same object. |
| `register_instance_for_path(dotted_path, instance, *, replace=False)` | Registers without importing the owner module. |
| `get_instance(owner)` / `get_instance_for_path(path)` | Pure lookup, returns `None` if absent. |
| `unregister(owner)` | Removes; returns whether anything was removed. |
| `resolve_instance(owner)` | Full resolution: registry, then the declarative source. |
| `describe_unregistered_owner(owner)` | Actionable diagnostic for the error path. |
| `clear_registry()` / `registered_owners()` | Test teardown / introspection. |

Design properties:

- **No import-time side effects.** Defines functions and one `RLock` and
  nothing else. Constructs nothing, opens no session, imports no business
  module.
- **Thread-safe** under a single `RLock` (re-entrant, since registration
  re-enters helpers).
- **Idempotent**, and a *different* instance for the same owner raises
  `InstanceRegistryConflictError` rather than clobbering. A silent clobber
  would swap a live session underneath in-flight calls — a bug that surfaces
  later as an unrelated flaky test. `replace=True` makes the destructive choice
  explicit at the call site.
- **Class and dotted path collapse to one key**, so class-based call sites and
  path-based startup wiring see each other.
- Absolute imports; typed; no relative imports; no new dependencies.

### Declarative hook: `__node_instance_source__`

```python
class MemoryService:
    __node_instance_source__ = "myapp.startup:_memory_service"   # or a 0-arg callable
    def __init__(self, session): ...
```

Resolved **lazily on first use** and memoised into the registry. It is *not*
resolved at import of the owning class, for two reasons that are the whole
reason this design exists:

1. **Import cycle.** A class importing the module holding its instance, while
   that module imports the class to construct the instance, is `ImportError` on
   a partially-initialised module. This is the dominant real failure: a DI
   container imports the services it wires.
2. **Import-time side effects and bloat.** Constructing a service at import
   opens a DB session during module load, before settings, logging, or an event
   loop exist. Node discovery imports hundreds of modules, so this would fire
   hundreds of times in an unspecified order.

A re-entrancy guard raises `InstanceNotRegisteredError` if a declared factory
asks for the instance it is supposed to be producing.

## 4. Measurement (runtime introspection, not grep)

Produced by `scripts/instance_registry_harness.py`, which calls
`discover_nodes(force=True)`, groups the 25,961 discovered nodes by owner
qualname, inspects each owner's constructor signature, and *actually attempts
construction* to distinguish "signature says required" from "constructor really
needs it".

| Classification | Owners | Dotted nodes |
|---|---:|---:|
| `auto_wireable` (zero-arg ctor — bridge already works) | 1,629 | 7,406 |
| `needs_existing_factory` (all required args have a known platform source) | 134 | 1,253 |
| `genuinely_unconstructible` (no platform source identified) | 288 | 843 |
| `partially_wireable` (some args sourced, some not) | 3 | 9 |
| `unresolvable` (owner module failed to import — pre-existing) | 95 | 197 |
| **Total** | **2,149** | **9,708** |

**Owners needing a supplied instance: 425. Dotted nodes affected: 2,105.**

The dominant dependency is overwhelmingly `session` (110 owners); then
`name` (48), `node_id` (45), `id` (16), `config` (14), `source_id` (13),
`conn` (10).

**Caveat on the "unconstructible" bucket.** A large share of it is not
unconstructible *services* but per-request context: `APIExtractNode(node_id)`,
`APIAdapter(adapter_id, path)` are workflow node classes whose parameters are
legitimate call arguments, not a service dependency the platform should supply.
Those need a different fix (pass-through context) and should **not** be wired
from a process-wide registry. Treating the bucket as homogeneous would be a
mistake; the JSON keeps per-owner detail so the two cases can be separated.

## 5. Tests

`Backend/tests/test_instance_registry.py` — 16 passed, 1 xfailed.

Round-trip (class and by path) · idempotent re-registration · conflict raises
and does not clobber · explicit `replace=True` · unregister · register by path
without importing the owner · **mutual exclusion** (held lock must block a
concurrent register) · 16-thread × 200-iteration stress with a contended-owner
single-winner assertion · nothing constructed at import (measured across a real
module import via the `_eager_probe.py` fixture) · lazy source resolves once and
memoises · no source means no construction · dotted node callable via the
registry · plain-function handler still works · dotted and plain nodes produce
identical handler signatures and metadata · unregistered required-arg owner
produces a diagnostic naming the class, the argument, and the remedy, and
explicitly *not* the misleading `'self'` TypeError.

### Falsification evidence

`scripts/neuter_instance_registry.py` — **5/5 mutations correctly falsified**
(each: apply → re-read file to confirm the edit landed → require RED → restore →
require GREEN).

| Mutation | RED | GREEN |
|---|---|---|
| drop the lock in `_register` | 1 failed | 1 passed |
| clobber silently instead of raising conflict | 1 error | 1 passed |
| stop collapsing class and dotted path in `owner_key` | 1 failed | 1 passed |
| construct the declared source at class-definition time | 1 failed | 1 passed |
| drop required-args detail from the diagnostic | 1 failed | 1 passed |

The first run of this harness reported **2 of 5 INVALID** — the lock mutation
and the laziness mutation did not produce RED. Both were faults in the *tests*,
not the code, and are worth recording:

- Removing the lock was unobservable because CPython dict operations are
  individually atomic under the GIL, so the 16-thread stress test passed
  anyway. Replaced with a deterministic mutual-exclusion test: the main thread
  holds the registry lock, a worker calls the public API and must block. An
  earlier draft of that test was also invalid because the worker took the lock
  itself, masking the registry's; fixed by having only the main thread hold it.
- The laziness mutation only changed `resolve_instance`, which nothing calls at
  import time, so it modelled nothing. Replaced with a mutation of the probe
  fixture that adds an eager `__init_subclass__` — the actual anti-pattern of
  eager wiring.

## 6. Found but not fixed

- The `unresolvable` (95 owners) and `partially_wireable` (3) buckets reflect
  pre-existing import problems in other modules. Recorded, not touched — those
  modules belong to other live sessions.
- `common/__init__.py` imports `data_storage.common.db_models`, so importing
  `common_lib.modules.common.instance_registry` transitively pulls in a DB
  model module. Harmless here (no connection is opened) but it means the
  package is not as import-light as the registry itself; worth a separate look.
- The harness's `KNOWN_FACTORIES` map is a hand-maintained heuristic. It is
  explicit about that, and the per-owner JSON lets a human correct it.
- The 288-owner "unconstructible" bucket needs triage into "platform should
  supply" vs "per-request argument" before any bulk wiring. Doing that in bulk
  without review would register instances nobody asked for.
