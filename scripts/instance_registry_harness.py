"""Introspect @node-owning classes whose constructor requires arguments.

Run:  .venv/bin/python -m scripts.instance_registry_harness
Writes: docs/duplication-audit/node_instance_registry_report.json

Classification is derived at RUNTIME by inspecting each owner's constructor
signature, never by grepping for `def __init__`.
"""

from __future__ import annotations

import inspect
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

BACKEND = Path(__file__).resolve().parents[1]
COMMON_LIB_SRC = BACKEND.parent / "Python Libs" / "common_lib" / "src"
for p in (str(COMMON_LIB_SRC), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Factories the platform already provides, used to classify owners.
KNOWN_FACTORIES = {
    "session": "common_lib.modules.data_storage.db:get_session (session factory)",
    "db": "common_lib.modules.data_storage.db:get_db / get_session (SQLModel Session)",
    "client": "per-module client (OpenAI/HTTP/redis) — usually a module singleton",
    "conn": "connection object supplied by the caller of the route",
    "container": "common_lib DI containers, e.g. AIModelsContainer (get_*_container ports)",
    "config": "core.config.settings (module-level singleton, no construction needed)",
    "settings": "core.config.settings (module-level singleton)",
}


def classify(cls: type) -> Dict[str, Any]:
    """Return required ctor params and a 3-way classification for ``cls``."""
    try:
        params = list(inspect.signature(cls.__init__).parameters.values())[1:]
    except (TypeError, ValueError) as exc:
        return {
            "required_params": [],
            "optional_params": [],
            "classification": "uninspectable",
            "detail": str(exc),
        }

    required = [
        p.name
        for p in params
        if p.default is inspect.Parameter.empty
        and p.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    ]
    optional = [p.name for p in params if p.name not in required]

    # 1. No required args -> the existing bridge already handles it via owner().
    if not required:
        return {
            "required_params": [],
            "optional_params": optional,
            "classification": "auto_wireable",
            "detail": "zero-arg constructor; existing _bind_instance() already works",
        }

    # 2. Constructor actually succeeds with no args (e.g. defaults computed
    #    internally that introspection cannot see) -> verify by real construction.
    try:
        cls()
        return {
            "required_params": required,
            "optional_params": optional,
            "classification": "auto_wireable",
            "detail": "constructor succeeds with no args despite signature",
        }
    except Exception as exc:  # noqa: BLE001 - that is the measurement
        pass

    # 3. Name the platform factory for every required param we recognise.
    known = {n: KNOWN_FACTORIES[n] for n in required if n in KNOWN_FACTORIES}
    if known and len(known) == len(required):
        return {
            "required_params": required,
            "optional_params": optional,
            "classification": "needs_existing_factory",
            "detail": "; ".join(f"{k} <- {v}" for k, v in known.items()),
        }
    if known:
        unknown = [n for n in required if n not in KNOWN_FACTORIES]
        return {
            "required_params": required,
            "optional_params": optional,
            "classification": "partially_wireable",
            "detail": f"known: {list(known)}; no known source for {unknown}",
        }

    return {
        "required_params": required,
        "optional_params": optional,
        "classification": "genuinely_unconstructible",
        "detail": "no platform source identified for required params",
    }


def main() -> int:
    from common_lib.modules.nodes_registry import discover_nodes

    nodes = discover_nodes(force=True)
    print(f"discovered {len(nodes)} nodes", file=sys.stderr)

    owners: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        qual = n.qualname or ""
        if "." not in qual:
            continue  # module-level function: no instance needed
        owner_q = qual.rsplit(".", 1)[0]
        owners.setdefault(owner_q, {"nodes": [], "modules": set()})
        owners[owner_q]["nodes"].append(n.name)
        owners[owner_q]["modules"].add(n.module)

    records: List[Dict[str, Any]] = []
    for owner_q, info in sorted(owners.items()):
        mod_name = sorted(info["modules"])[0]
        rec: Dict[str, Any] = {
            "owner": owner_q,
            "module": mod_name,
            "node_count": len(info["nodes"]),
            "sample_nodes": sorted(info["nodes"])[:5],
        }
        try:
            obj: Any = __import__(mod_name, fromlist=["_"])
            for part in owner_q.split("."):
                obj = getattr(obj, part)
        except Exception as exc:  # noqa: BLE001
            rec.update(
                required_params=[],
                optional_params=[],
                classification="unresolvable",
                detail=f"{type(exc).__name__}: {exc}",
            )
            records.append(rec)
            continue

        if not inspect.isclass(obj):
            rec.update(
                required_params=[],
                optional_params=[],
                classification="not_a_class",
                detail=f"owner resolved to {type(obj).__name__}",
            )
            records.append(rec)
            continue

        rec.update(classify(obj))
        records.append(rec)

    counts: Dict[str, int] = {}
    node_counts: Dict[str, int] = {}
    for r in records:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
        node_counts[r["classification"]] = (
            node_counts.get(r["classification"], 0) + r["node_count"]
        )

    out = {
        "summary": {
            "total_owners_with_nodes": len(records),
            "total_dotted_nodes": sum(r["node_count"] for r in records),
            "owners_by_classification": counts,
            "nodes_by_classification": node_counts,
            "owners_requiring_instance": sum(
                v
                for k, v in counts.items()
                if k
                in (
                    "needs_existing_factory",
                    "partially_wireable",
                    "genuinely_unconstructible",
                )
            ),
            "nodes_requiring_instance": sum(
                v
                for k, v in node_counts.items()
                if k
                in (
                    "needs_existing_factory",
                    "partially_wireable",
                    "genuinely_unconstructible",
                )
            ),
        },
        "owners": records,
    }

    dest = BACKEND / "docs" / "duplication-audit" / "node_instance_registry_report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps(out["summary"], indent=2))
    print(f"wrote {dest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
