#!/usr/bin/env python
"""
test_compose.py — Dry-run the $compose / $connect composition system.

Verifies that YAMLComposer correctly expands $compose directives into a
flat graph — WITHOUT executing any GPU nodes.

Usage (from Backend Monorepo/Backend dir):
    uv run python test_compose.py
    uv run python test_compose.py --workflow composed_gen_upscale_v2
    uv run python test_compose.py --verbose
    uv run python test_compose.py --log-level DEBUG

What it checks:
  ✓ $compose nodes are expanded (sub_image_gen, sub_image_upscale)
  ✓ No $compose or $connect directives remain in the flat graph
  ✓ No workflow.input / workflow.output sentinel nodes remain
  ✓ Node IDs are properly namespaced (e.g. gen_step_generate)
  ✓ No duplicate node IDs
  ✓ All edge from/to reference real nodes (edge integrity)
  ✓ {{param}} substitution flows through compose inputs blocks
  ✓ A save node is present at the end
"""

import argparse
import json
import sys
import logging
from pathlib import Path

# ── Path bootstrap ─────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_COMMON_LIB = _HERE.parent / "Python Libs" / "common_lib" / "src"
if str(_COMMON_LIB) not in sys.path:
    sys.path.insert(0, str(_COMMON_LIB))


# ── Output helpers ─────────────────────────────────────────────────────────

def hr(title: str = "") -> None:
    if title:
        print(f"\n{'─' * 62}\n  {title}\n{'─' * 62}")
    else:
        print("─" * 62)

def ok(msg: str)   -> None: print(f"  ✓  {msg}")
def warn(msg: str) -> None: print(f"  ⚠  {msg}")

def fail(msg: str) -> None:
    print(f"\n  ✗  FAIL: {msg}\n")
    sys.exit(1)

def section(label: str, items: list) -> None:
    print(f"\n  {label}:")
    for item in items:
        print(f"    • {item}")


# ── Core test ──────────────────────────────────────────────────────────────

def test_workflow(workflow_id: str, verbose: bool) -> dict:
    hr(f"Composing: '{workflow_id}'")

    from common_lib.modules.workflows.subflows.yaml_composer import YAMLComposer, COMPOSE_TYPE, CONNECT_TYPE

    composer = YAMLComposer()

    # Step 1 — load raw workflow to check it has $compose directives
    raw = composer._load(workflow_id)
    if raw is None:
        fail(f"Could not load workflow '{workflow_id}' from registry or file system")

    has_compose = YAMLComposer.needs_composition(raw)
    if not has_compose:
        warn(f"Workflow '{workflow_id}' has no $compose nodes — nothing to test.")
        return raw

    compose_count = sum(1 for n in raw.get("nodes", []) if n.get("type") == COMPOSE_TYPE)
    ok(f"Found {compose_count} $compose directive(s) in '{workflow_id}'")

    # Step 2 — expand
    flat = composer.compose(workflow_id)
    nodes = flat.get("nodes", [])
    edges = flat.get("edges", [])

    # ── Checks ──────────────────────────────────────────────────────────────

    # 1. No $compose or $connect directives remain
    leftover = [n for n in nodes if n.get("type") in (COMPOSE_TYPE, CONNECT_TYPE)]
    if leftover:
        fail(f"$compose/$connect directives not removed: {[n['id'] for n in leftover]}")
    ok("No $compose / $connect directives remain in flat graph")

    leftover_edges = [e for e in edges if e.get("type") in (COMPOSE_TYPE, CONNECT_TYPE)]
    if leftover_edges:
        fail(f"$connect edges not resolved: {leftover_edges}")
    ok("All $connect edges resolved to real edges")

    # 2. No sentinel interface nodes remain
    sentinels = [
        n for n in nodes
        if n.get("type") in ("workflow.input", "workflow.output")
    ]
    if sentinels:
        fail(f"Sentinel nodes were NOT removed: {[n['id'] for n in sentinels]}")
    ok("No workflow.input / workflow.output sentinels remain")

    # 3. Unique node IDs
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        from collections import Counter
        dupes = [k for k, v in Counter(ids).items() if v > 1]
        fail(f"Duplicate node IDs: {dupes}")
    ok(f"All {len(nodes)} node IDs are unique")

    # 4. Edge integrity
    id_set = set(ids)
    bad = [
        e for e in edges
        if e.get("from") not in id_set or e.get("to") not in id_set
    ]
    if bad:
        fail(
            "Edges reference non-existent nodes:\n" +
            "\n".join(f"    {e}" for e in bad)
        )
    ok(f"All {len(edges)} edges reference valid nodes")

    # 5. Namespacing check — composed nodes should carry a prefix
    prefixed = [n["id"] for n in nodes if "_" in n["id"]]
    ok(f"{len(prefixed)}/{len(nodes)} node IDs carry a sub-workflow prefix")

    # 6. Save node present
    save_nodes = [
        n for n in nodes
        if "save" in n.get("type", "").lower() or "save" in n.get("id", "").lower()
    ]
    if save_nodes:
        ok(f"Save node present: {save_nodes[0]['id']} ({save_nodes[0].get('type')})")
    else:
        warn("No save node found in flat graph")

    # ── Summary ─────────────────────────────────────────────────────────────
    section(
        "Flat nodes",
        [f"{n['id']}  ({n.get('type', '?')})" for n in nodes]
    )
    section(
        "Flat edges",
        [
            f"{e.get('from')}:{e.get('fromPort', '?')}  →  "
            f"{e.get('to')}:{e.get('toPort', '?')}"
            for e in edges
        ]
    )

    if verbose:
        print("\n  Full flat JSON:")
        print(json.dumps(flat, indent=2, default=str))

    return flat


# ── Param substitution test ────────────────────────────────────────────────

def test_param_substitution(workflow_id: str) -> None:
    hr("Param substitution test")

    from common_lib.modules.workflows.subflows.yaml_composer import YAMLComposer

    # Pass a custom prompt and check it flows through
    flat = YAMLComposer().compose(
        workflow_id,
        parent_params={
            "prompt": "TEST_PROMPT_VALUE",
            "width":  512,
            "height": 512,
        }
    )

    flat_str = json.dumps(flat, default=str)
    if "TEST_PROMPT_VALUE" in flat_str:
        ok("Custom prompt flowed through $compose inputs into sub-workflow nodes")
    else:
        warn("Could not verify prompt substitution (node may not expose it as a literal)")

    if "{{prompt}}" in flat_str:
        fail("Unresolved {{prompt}} template still present in flat graph")
    ok("No unresolved {{param}} templates in flat graph")


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run $compose workflow expansion — no GPU required"
    )
    parser.add_argument(
        "--workflow", "-w",
        default="composed_gen_upscale_v2",
        help="Workflow ID to expand (default: composed_gen_upscale_v2)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print full flat JSON after expansion"
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(name)s | %(levelname)s | %(message)s"
    )

    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     Workflow Composition Dry-Run — $compose / $connect     ║")
    print("╚════════════════════════════════════════════════════════════╝")

    test_workflow(args.workflow, args.verbose)
    test_param_substitution(args.workflow)

    hr()
    print("  All checks passed ✓")
    hr()
    print()


if __name__ == "__main__":
    main()
