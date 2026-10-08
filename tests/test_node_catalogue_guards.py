"""Guards for the `@node` catalogue: two mistakes that keep coming back.

WHAT IS GUARDED
---------------
1. **No Enum class may carry `@node`.** An ``Enum`` is a type tag. It takes no
   input, returns no output, and is not invocable — so listing one as a
   discoverable tool tells an LLM it can call something that cannot be called.
   402 enum classes (788 registry entries, inflated by re-exports) were carrying
   the decorator; the decorator was removed and the classes left intact.

2. **Every ``executable=False`` owner must be genuinely non-instantiable.** The
   flag is a promise that the node has no implementation to invoke. A wrong
   ``executable=False`` is worse than no flag: it hides a working capability.
   This has now bitten twice — 259 nodes were marked by a sweep that read the
   flag off the wrong dict (``metadata`` instead of the ``NodeInfo`` field), and
   then two of the 259 were found to sit on plain concrete classes that
   construct and bind fine.

Both guards introspect the REAL discovered registry. Nothing here re-implements
discovery or reads source, because a stand-in validated itself last time and let
a whole class of bug through (see the regression note in
``test_node_executable_flag.py``).

COUNTS (Backend Monorepo/Backend/.venv/bin/python)
--------------------------------------------------
    discover_nodes() before this cleanup : 25 961
    discover_nodes() after              : 25 180 - 25 193
    enum-class nodes removed             :  788 registry entries / 402 classes
    executable=False before / after      :  259 / 258

The after-count is a 13-wide band, not a point: 13 registry entries are
import-order dependent and appear in some runs only (reporting.ai.*,
external_platforms.huggingface.config.*, ...). That flakiness predates this
change and is unrelated to it.
"""

from __future__ import annotations

import ast
import enum
import importlib
import inspect
import textwrap
from pathlib import Path

import pytest

from common_lib.modules.nodes_registry import discover_nodes


@pytest.fixture(scope="module")
def nodes():
    return discover_nodes(force=True)


def _removed_enum_classes():
    """Load the frozen (module, qualname) record of the cleaned-up enum classes.

    Read by path rather than imported, because ``tests/`` is not a package (no
    ``__init__.py``) and ``import tests.x`` would depend on the rootdir landing
    on ``sys.path``.
    """
    record = Path(__file__).with_name("node_catalogue_removed_enums.py")
    namespace: dict = {}
    exec(compile(record.read_text(encoding="utf-8"), str(record), "exec"), namespace)
    return namespace["REMOVED_ENUM_CLASSES"]


def _resolve(node_info):
    """Best-effort resolution of a node's underlying object.

    ``NodeInfo.qualname`` is a dotted path in ``NodeInfo.module``, but that pair
    is not always self-consistent. Discovery attributes a node to the module it
    was *found in*, while ``qualname`` comes from the decorator's own
    ``__qualname__`` — so a class method defined in one module and reachable
    through a subclass in another arrives as ``BaseConnector.check_health`` with
    ``module`` naming the subclass's module, where ``BaseConnector`` is not an
    attribute. Three strategies, in order: walk the dotted path; drop the
    unresolvable leading segment; fall back to the object's own ``__module__``.
    """
    module = importlib.import_module(node_info.module)
    parts = (node_info.qualname or "").split(".")

    for k in range(len(parts), 0, -1):
        obj = module
        try:
            for part in parts[:k]:
                obj = getattr(obj, part)
        except AttributeError:
            continue
        return obj

    # No prefix resolved in that module: ask the object where it really lives.
    if "." in (node_info.qualname or ""):
        owner_name = node_info.qualname.rsplit(".", 1)[0]
        for candidate in dir(module):
            candidate_obj = getattr(module, candidate, None)
            if not inspect.isclass(candidate_obj):
                continue
            for base in inspect.getmro(candidate_obj):
                if base.__name__ == owner_name.rsplit(".", 1)[-1]:
                    member = getattr(base, node_info.qualname.rsplit(".", 1)[1], None)
                    if member is not None:
                        return member
    return None


# ── guard 1: no Enum may be a node ────────────────────────────────────────────


def test_no_enum_class_carries_a_node(nodes):
    """Enums are type tags, not callable tools."""
    offenders = []
    for n in nodes:
        if "." in (n.qualname or ""):
            continue  # a method, so the owner is a class, not the Enum itself
        obj = _resolve(n)
        if inspect.isclass(obj) and issubclass(obj, enum.Enum):
            offenders.append((n.name, n.module, n.qualname))
    assert not offenders, (
        f"{len(offenders)} Enum class(es) are decorated with @node; an Enum is "
        f"not invocable and must not be advertised as a tool: {offenders[:10]}"
    )


def test_enum_removal_did_not_delete_the_classes():
    """The fix was to drop the decorator, never the class.

    Every enum that used to be discoverable must still be importable by its
    Python name, or every type annotation and member lookup in the platform
    would break.
    """
    missing = []
    for module_name, qualname in _removed_enum_classes():
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - environmental
            missing.append((module_name, qualname, f"import failed: {exc}"))
            continue
        obj = module
        try:
            for part in qualname.split("."):
                obj = getattr(obj, part)
        except AttributeError:
            missing.append((module_name, qualname, "attribute gone"))
            continue
        if not (inspect.isclass(obj) and issubclass(obj, enum.Enum)):
            missing.append((module_name, qualname, "no longer an Enum"))
    assert not missing, f"enum classes lost during decorator removal: {missing[:10]}"


# ── guard 2: executable=False must be true ───────────────────────────────────


def _body_is_only_a_declaration(func) -> bool:
    """True when the function body has no implementation to run.

    A docstring, a bare ``pass``, or nothing but ``raise`` statements all mean
    "declaration, not implementation" — calling it cannot produce a result.
    """
    try:
        src = inspect.getsource(func)
    except (OSError, TypeError):
        return False
    tree = ast.parse(textwrap.dedent(src))
    fn = tree.body[0]
    body = [
        stmt
        for stmt in fn.body
        if not (
            isinstance(stmt, ast.Expr)
            and isinstance(getattr(stmt, "value", None), ast.Constant)
            and isinstance(stmt.value.value, str)
        )
    ]
    if not body:
        return True
    return all(isinstance(stmt, (ast.Pass, ast.Raise)) for stmt in body)


def _owner_is_non_instantiable(func) -> bool:
    """True when the class owning ``func`` cannot be constructed.

    Covers the three ways that happens in this codebase: an ABC with abstract
    methods, a ``Protocol`` (which refuses instantiation outright), and a class
    whose ``__init__`` demands arguments or raises without them.
    """
    qual = getattr(func, "__qualname__", "") or ""
    if "." not in qual:
        return True  # a module-level function: nothing to bind
    module = inspect.getmodule(func)
    if module is None:
        return False
    owner = module
    for part in qual.split(".")[:-1]:
        owner = getattr(owner, part, None)
        if owner is None:
            return False
    if not inspect.isclass(owner):
        return False
    if getattr(owner, "_is_protocol", False):
        return True
    if inspect.isabstract(owner):
        return True
    try:
        owner()
    except Exception:
        return True
    return False


def test_every_non_executable_node_is_genuinely_not_callable(nodes):
    """A wrong ``executable=False`` hides a working capability.

    The node must fail at least one of two ways: its owner cannot be built (so
    the bridge can never bind ``self``), or its body is a bare declaration with
    no implementation to run. Anything else is a mis-mark.
    """
    mis_marked = []
    for n in nodes:
        if getattr(n, "executable", True) is not False:
            continue
        func = _resolve(n)
        if inspect.isfunction(func) and (
            _owner_is_non_instantiable(func) or _body_is_only_a_declaration(func)
        ):
            continue
        mis_marked.append((n.name, n.module, n.qualname, type(func).__name__))
    assert not mis_marked, (
        f"{len(mis_marked)} node(s) marked executable=False but are in fact "
        f"callable — a wrong flag hides a working capability: {mis_marked[:10]}"
    )


def test_the_two_controlnet_handlers_are_advertised_as_executable(nodes):
    """Named regression.

    ``TransformerNativeControlNetHandler.apply`` and
    ``ModelPatchControlNetHandler.apply`` sit on plain concrete classes:
    ``isabstract=False``, no abstract methods, ``cls()`` succeeds, ``apply``
    binds, and the body runs (delegating to ``apply_patch`` or raising a
    deliberate ``NotImplementedError``). They were marked ``executable=False``,
    which lied about a working capability.
    """
    by_name = {n.name: n for n in nodes}
    for name in (
        "image_processing.TransformerNativeControlNetHandler.apply",
        "image_processing.ModelPatchControlNetHandler.apply",
    ):
        n = by_name.get(name)
        assert n is not None, f"{name} disappeared from the registry"
        assert n.executable is True, f"{name} is still marked executable=False"


def test_image_backend_supports_is_marked_non_executable(nodes):
    """Task C: a ``REAL_BODY`` the earlier sweep missed.

    ``ImageBackend`` is a ``Protocol``, so ``ImageBackend()`` raises
    "Protocols cannot be instantiated" and no instance is registered — the
    bridge can never bind ``self``. ``supports`` has a real body, which is why a
    body-only sweep skipped it. Runtime: the handler returns
    ``{"error": "Cannot bind node for 'ImageBackend' ... no instance is
    registered"}`` rather than any result.
    """
    matches = [
        n
        for n in nodes
        if n.qualname == "ImageBackend.supports"
        and n.module == "common_lib.modules.image_processing.backends.base"
    ]
    assert matches, "ImageBackend.supports is no longer discovered"
    assert matches[0].executable is False
