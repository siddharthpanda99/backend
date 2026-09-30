#!/usr/bin/env python3
"""Falsification harness: neuter the registry, confirm the test goes RED, restore.

A test that passes the first time is not evidence. For each mutation this script:
  1. applies the edit,
  2. RE-READS the file to prove the edit actually landed (an earlier round in
     this repo recorded two "falsification proofs" that were invalid because the
     edit never applied),
  3. runs the targeted test and requires it to FAIL,
  4. restores from the pristine copy and requires the test to PASS again.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REG = (
    BACKEND.parent
    / "Python Libs"
    / "common_lib"
    / "src"
    / "common_lib"
    / "modules"
    / "common"
    / "instance_registry.py"
)
PRISTINE = REG.with_suffix(".py.pristine")
PROBE = BACKEND / "tests" / "_eager_probe.py"
PROBE_PRISTINE = PROBE.with_suffix(".py.pristine")
PY = str(BACKEND / ".venv" / "bin" / "python")

# (label, old, new, test node id[, target file])
MUTATIONS = [
    (
        "thread-safety: drop the lock in _register",
        "    with _LOCK:\n        existing = _INSTANCES.get(key)",
        "    if True:\n        existing = _INSTANCES.get(key)",
        "test_register_and_get_are_mutually_exclusive",
    ),
    (
        "conflict: clobber silently instead of raising",
        "                raise InstanceRegistryConflictError(",
        "                _INSTANCES[key] = instance or\n"
        "                _INSTANCES[key] = instance\n"
        "                if False: raise InstanceRegistryConflictError(",
        "test_conflicting_instance_raises_and_does_not_clobber",
    ),
    (
        "owner_key: stop collapsing class and dotted path",
        '        return f"{owner.__module__}.{owner.__qualname__}"',
        "        return owner.__name__",
        "test_roundtrip_by_class_and_by_path",
    ),
    (
        "lazy: construct the declared source at class-definition time",
        "class Lazy:",
        "def _eager(cls):\n"
        "    src = cls.__dict__.get('__node_instance_source__')\n"
        "    if src is not None:\n"
        "        mod, _, attr = src.partition(':')\n"
        "        getattr(importlib.import_module(mod), attr)()\n\n\n"
        "class _EagerBase:\n"
        "    def __init_subclass__(cls, **kw):\n"
        "        _eager(cls)\n\n\n"
        "class Lazy(_EagerBase):",
        "test_nothing_constructed_at_import_time",
        PROBE,
    ),
    (
        "diagnostic: drop the required-args detail from the error",
        '    hint = (\n        f" Its constructor requires {required!r}."',
        '    hint = (\n        f" (detail removed)."',
        "test_unregistered_required_arg_owner_reports_diagnostically",
    ),
]


def run(node: str) -> tuple[int, str]:
    p = subprocess.run(
        [
            PY,
            "-m",
            "pytest",
            f"tests/test_instance_registry.py::{node}",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=300,
    )
    tail = (
        (p.stdout or p.stderr).strip().splitlines()[-1]
        if (p.stdout or p.stderr).strip()
        else ""
    )
    return p.returncode, tail


def main() -> int:
    shutil.copy(REG, PRISTINE)
    shutil.copy(PROBE, PROBE_PRISTINE)
    results = []
    try:
        for mut in MUTATIONS:
            label, old, new, node = mut[:4]
            target = mut[4] if len(mut) > 4 else REG
            pristine = PROBE_PRISTINE if target == PROBE else PRISTINE
            src = pristine.read_text()
            if old not in src:
                results.append((label, "EDIT-NOT-FOUND", "", ""))
                continue
            target.write_text(src.replace(old, new, 1))

            # Prove the edit landed, rather than trusting the write.
            landed = target.read_text()
            if new not in landed or landed == src:
                results.append((label, "EDIT-DID-NOT-LAND", "", ""))
                target.write_text(src)
                continue

            red_code, red_tail = run(node)
            target.write_text(src)  # restore
            green_code, green_tail = run(node)

            ok = red_code != 0 and green_code == 0
            results.append(
                (label, "RED+GREEN-OK" if ok else "INVALID", red_tail, green_tail)
            )
            print(
                f"[{'ok' if ok else 'INVALID'}] {label}\n     red: {red_tail}\n     green: {green_tail}"
            )
    finally:
        shutil.copy(PRISTINE, REG)
        shutil.copy(PROBE_PRISTINE, PROBE)
        PRISTINE.unlink(missing_ok=True)
        PROBE_PRISTINE.unlink(missing_ok=True)

    bad = [r for r in results if r[1] != "RED+GREEN-OK"]
    print(f"\n{len(results) - len(bad)}/{len(results)} mutations correctly falsified")
    for label, status, red, green in bad:
        print(f"  !! {label}: {status} | red={red} | green={green}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
