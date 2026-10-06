"""``app.cli`` package -- re-exports the shadowed sibling ``app/cli.py``.

Why this file exists
--------------------
Backend ships BOTH ``app/cli.py`` (the 4.9 kB module that defines ``dev_server``
and ``db_up``) and ``app/cli/`` (the package holding ``sync_prompts.py``).
Python's ``FileFinder`` resolves a *directory* named ``cli`` before a *file*
named ``cli.py``, so ``import app.cli`` binds this package and ``app/cli.py``
becomes unreachable by ordinary import.

Two console scripts in ``Backend/pyproject.toml`` target that unreachable
module::

    dev   = "app.cli:dev_server"
    db-up = "app.cli:db_up"

Both raised ``AttributeError: module 'app.cli' has no attribute 'dev_server'``:
the generated wrapper imports the module successfully, then the attribute
lookup fails. The declaration was live; the implementation was not reachable.

``app/cli.py`` cannot simply be imported, and is NOT deleted, because it holds
real launchers that rule 07 forbids ``common_lib`` from hosting: ``dev_server``
runs ``uvicorn.run("app.main:app")`` and ``db_up`` wraps docker-compose. So the
module is loaded explicitly *by path* and its callables are re-exported here.

Why these are explicit functions, not a module ``__getattr__``
-------------------------------------------------------------
A PEP 562 ``__getattr__`` would work at runtime but is invisible to static
analysis. Golden rule 19 resolves a console script by finding the module file
and then AST-parsing it for statically defined names, so a dynamic export left
rule 19 still reporting ``module has no 'db_up'`` -- the debt would look
unpaid even though ``db-up`` had started working. Defining real module-level
functions keeps the fix verifiable by both the interpreter and the gate.

Additive only: this file was previously 0 bytes.

Absolute imports only (G5 / rule 04).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

#: Absolute path of the shadowed sibling module, ``app/cli.py``.
SHADOWED_MODULE_PATH = Path(__file__).resolve().parent.parent / "cli.py"


def _load_shadowed_cli_module() -> ModuleType | None:
    """Load ``app/cli.py`` by path, bypassing the package that shadows it.

    Returns ``None`` if the file is absent or fails to load. That degradation is
    deliberate: ``app.cli`` is also the parent package of ``app.cli.sync_prompts``,
    so this module must never be the reason that import fails.
    """
    if not SHADOWED_MODULE_PATH.is_file():
        return None
    module_name = "app.cli._shadowed_cli_module"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SHADOWED_MODULE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    # Registered before exec so a circular reference inside the loader finds the
    # partially-initialised module rather than re-entering the import machinery.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:  # pragma: no cover -- launcher is stdlib-only today
        sys.modules.pop(module_name, None)
        return None
    return module


_shadowed = _load_shadowed_cli_module()


def _delegate(name: str):
    """Return the named callable from the shadowed ``app/cli.py``.

    Raises ``AttributeError`` (not ``ImportError``) so a missing launcher
    surfaces with the same exception type the un-fixed code raised, rather than
    a new failure mode callers would not expect.
    """
    if _shadowed is None:
        raise AttributeError(
            f"'app.cli.{name}' is unavailable: the shadowed launcher "
            f"{SHADOWED_MODULE_PATH} could not be loaded"
        )
    try:
        return getattr(_shadowed, name)
    except AttributeError as exc:  # pragma: no cover -- launcher is stable
        raise AttributeError(
            f"'app.cli.{name}' is unavailable: not defined in {SHADOWED_MODULE_PATH}"
        ) from exc


def db_up() -> None:
    """Start the database services (docker-compose wrapper).

    Delegates to ``app/cli.py``'s ``db_up``.
    """
    return _delegate("db_up")()


def db_down() -> None:
    """Stop the database services (docker-compose wrapper).

    Delegates to ``app/cli.py``'s ``db_down``.
    """
    return _delegate("db_down")()


def db_logs() -> None:
    """Follow the database service logs (docker-compose wrapper).

    Delegates to ``app/cli.py``'s ``db_logs``.
    """
    return _delegate("db_logs")()


def main() -> None:
    """Run the legacy ``app/cli.py`` argument parser.

    Delegates to ``app/cli.py``'s ``main``. Note that ``nexus`` in
    ``Backend/pyproject.toml`` deliberately points at the canonical
    ``common_lib.modules.cli.runtime.runner:main`` instead; this is retained
    only so the declared symbol exists.
    """
    return _delegate("main")()


def dev_server() -> None:
    """Launch the uvicorn dev server for ``app.main:app``.

    Delegates to ``app/cli.py``'s ``dev_server``. That function derives its
    paths from its own ``__file__``, so it keeps working unchanged when
    invoked through this wrapper.
    """
    return _delegate("dev_server")()


__all__ = [
    "SHADOWED_MODULE_PATH",
    "db_down",
    "db_logs",
    "db_up",
    "dev_server",
    "main",
]
