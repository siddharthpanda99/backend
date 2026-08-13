"""Shared helpers for secrets_manager @node wrapper tests.

Builds a canonical registry of (subpackage, wrapper_name, wrapper_fn,
_node_metadata) by importing each subpackage's ``nodes.py`` and collecting
every function decorated with ``@node`` (i.e. marked ``_is_plugin_node``).
"""

from __future__ import annotations

import importlib
from typing import List, Tuple, Dict, Any

SUBPACKAGES: List[str] = [
    "vault",
    "core",
    "policy",
    "audit",
    "seal",
    "engines",
    "events",
    "scanning",
    "replication",
    "plugins",
    "import_export",
    "dynamic",
    "cloud",
    "kubernetes",
    "monitoring",
    "pki",
    "proxy",
    "rotation",
    "ssh",
]


def collect_wrappers() -> List[Tuple[str, str, Any, Dict[str, Any]]]:
    """Return ``[(subpackage, name, fn, metadata), ...]`` for every @node wrapper."""
    out: List[Tuple[str, str, Any, Dict[str, Any]]] = []
    for sub in SUBPACKAGES:
        mod = importlib.import_module(f"common_lib.modules.secrets_manager.{sub}.nodes")
        for attr in dir(mod):
            fn = getattr(mod, attr)
            if getattr(fn, "_is_plugin_node", False) and callable(fn):
                out.append((sub, attr, fn, getattr(fn, "_node_metadata", {})))
    return out


def wrapper_names() -> List[str]:
    return [n for _, n, _, _ in collect_wrappers()]
