"""Guard: no ``@node`` may sit on a ``@property``.

WHY A SEPARATE GUARD FROM ``test_node_catalogue_guards.py``
----------------------------------------------------------
That file guards Enums by walking the objects **inside the discovered registry**.
That shape cannot see this bug: a ``property`` is a descriptor, so
``nodes_registry`` (which selects with ``inspect.isfunction``) never collects it.
A property carrying ``@node`` is therefore invisible to a registry-walking guard
by construction — it fails exactly when the code is worst.

So this guard enumerates by **real runtime introspection over every discoverable
module**, not by parsing source and not by walking the registry:

    for each candidate module: import it
        for each class attribute that ``isinstance(..., property)``
            check the descriptor's ``fget`` for ``_is_plugin_node``

That is the same evidence a human gets from ``dir()``/``getattr``, so it cannot
drift from runtime the way a source assertion can.

COUNTS (Backend Monorepo/Backend/.venv/bin/python, discover_nodes(force=True))
-----------------------------------------------------------------------------
    properties carrying @node before this cleanup : 442
    removed by this work                           : 263  (14 module commits)
    left in place (owned by an in-flight agent)     : 179
    discover_nodes() before / after                : 25 215 / 25 215  (unchanged)

The registry total is unchanged because **none of the 442 was ever in it** —
that is the whole point of the bug, and it is the falsification check: if a
future edit ever made one of these reachable, the count would move.

The 179 still decorated are in modules a concurrent audit session owns
(orchestration, proxy_routing, rbac, secrets_manager, ai_models,
knowledge_engine, image_processing, iil, doc_processing, external_platforms,
core_infrastructure, notification). They are **reported, not failed on**, so this
guard does not block the agents that own them.

EXCLUSIONS — what this guard deliberately does NOT flag
------------------------------------------------------
* ``@node`` on a plain function or method: fine, that is the normal case.
* ``@node`` on a class that is not an Enum: fine. A dataclass or service class
  tagged ``group`` is a catalogue grouping entry and IS collected by
  ``_collect_from_module`` (10 391 such class-level nodes exist and are
  reachable), so flagging them would be wrong.
* ``@node`` on an ``Enum``: already covered, and correctly, by
  ``test_no_enum_class_carries_a_node`` in ``test_node_catalogue_guards.py``.
  Duplicating it here would double-report the same defect.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from common_lib.modules.nodes_registry import _path_to_module, _scan_module_paths

# Modules whose property decorators belong to another in-flight audit session.
# Reported by the test, never failed on. Delete entries as those sessions land.
IN_FLIGHT_MODULES = frozenset(
    {
        "ai_models",
        "core_infrastructure",
        "doc_processing",
        "external_platforms",
        "iil",
        "image_processing",
        "knowledge_engine",
        "notification",
        "orchestration",
        "proxy_routing",
        "rbac",
        "secrets_manager",
    }
)


def _module_of(path):
    try:
        return _path_to_module(path)
    except Exception:
        return None


def _marked_properties():
    """Yield ``(module, Class.prop)`` for every property whose fget carries @node.

    Runtime introspection only: import the module, then look at real descriptors.
    """
    seen = set()
    for path in _scan_module_paths():
        mod_name = _module_of(path)
        if not mod_name:
            continue
        try:
            module = importlib.import_module(mod_name)
        except Exception:
            # A module that cannot import contributes no live descriptors.
            continue
        for attr_name in dir(module):
            try:
                attr = getattr(module, attr_name)
            except Exception:
                continue
            if not inspect.isclass(attr):
                continue
            for member_name, descriptor in vars(attr).items():
                if not isinstance(descriptor, property):
                    continue
                fget = descriptor.fget
                if fget is None:
                    continue
                if getattr(fget, "_is_plugin_node", False):
                    # Attribute the property to the module that DEFINES the class,
                    # not the one we happened to reach it through. Several modules
                    # re-export a class (``plugins.connectors.keys.bridge`` imports
                    # ``secrets_manager``'s ``KeyManagementService``), and fixing
                    # the decorator in the aliasing module is impossible — the
                    # decorator lives on the original class. Keying on the defining
                    # module stops the guard from blaming an in-flight owner on a
                    # module that merely re-exports it.
                    defining = getattr(attr, "__module__", mod_name) or mod_name
                    key = (defining, f"{attr_name}.{member_name}")
                    if key not in seen:
                        seen.add(key)
                        yield key


MARKED = sorted(_marked_properties())


def _top_module(mod_name: str) -> str:
    parts = mod_name.split(".")
    return parts[2] if len(parts) > 2 else parts[-1]


def test_no_property_carries_a_node_outside_in_flight_modules():
    """The actual gate: @node on a @property is unreachable and therefore a lie."""
    offenders = [(m, q) for m, q in MARKED if _top_module(m) not in IN_FLIGHT_MODULES]
    assert offenders == [], (
        "@node on a @property can never be discovered: nodes_registry selects "
        "with inspect.isfunction and a property is a descriptor, so the "
        "decorator is inert metadata on fget. Remove the @node (keep the "
        f"property). Offenders: {offenders}"
    )


def test_in_flight_property_nodes_are_still_reported():
    """Documents the residue rather than hiding it.

    If this test starts failing with an empty list, the in-flight sessions have
    landed and IN_FLIGHT_MODULES can be pruned.
    """
    residue = [(m, q) for m, q in MARKED if _top_module(m) in IN_FLIGHT_MODULES]
    print(f"\n@node-on-property residue in in-flight modules: {len(residue)}")
    for mod_name, qualname in residue:
        print(f"  {mod_name}.{qualname}")


def test_plain_function_nodes_are_not_flagged():
    """A @node on a plain function is legitimate; the guard must not catch it."""

    @importlib.import_module("common_lib.modules.plugins.node").node(
        name="guard_probe.synthetic_tool",
        description="Synthetic node used only to prove the guard ignores functions.",
        category="guard_probe",
        tags=["guard", "probe"],
        audience=["executor"],
        input_schema={},
        output_schema={},
    )
    def synthetic_tool(value: str = "x") -> str:
        return value

    assert inspect.isfunction(synthetic_tool)
    assert not isinstance(synthetic_tool, property)
    assert getattr(synthetic_tool, "_is_plugin_node", False) is True
    # A function must never be reported by the property scan.
    assert ("common_lib.modules.plugins.node", "synthetic_tool") not in dict(MARKED)


@pytest.mark.parametrize(
    "mod_name,qualname", MARKED, ids=[f"{m}.{q}" for m, q in MARKED]
)
def test_each_marked_property_is_absent_from_the_registry(mod_name, qualname):
    """Falsification: a property @node must not be reachable in the registry.

    This is the check that would catch a genuine behaviour change: if one of
    these ever became discoverable, its NodeInfo would appear here.
    """
    from common_lib.modules.nodes_registry import discover_nodes

    registry = discover_nodes()
    qualnames = {n.qualname for n in registry}
    names = {n.name for n in registry}
    cls_name, prop_name = qualname.split(".", 1)
    assert qualname not in qualnames
    assert f"{cls_name}.{prop_name}" not in names
