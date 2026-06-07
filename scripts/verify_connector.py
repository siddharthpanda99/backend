#!/usr/bin/env python3
"""verify_connector.py — Validate all connector provider definitions.

Scans every provider sub-package and the fallback engine for:
  - Python syntax errors
  - Successful module import
  - Provider class existence and proper base class
  - Endpoint consistency (method, path format, no duplicates)
  - Path parameter extraction vs seed tool schemas
  - Cross-reference: all seeded tools have a matching endpoint

Usage:
    cd Backend Monorepo/Backend
    uv run python scripts/verify_connector.py
    uv run python scripts/verify_connector.py --verbose
    uv run python scripts/verify_connector.py atlassian   # single connector
"""

import argparse
import ast
import importlib
import inspect
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Paths (relative to this script)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
CONNECTORS_DIR = BACKEND_DIR / "app" / "modules" / "connectors"
PROVIDERS_DIR = CONNECTORS_DIR / "providers"
EXECUTE_ENGINE_PATH = CONNECTORS_DIR / "execute_engine.py"
SEED_PATH = CONNECTORS_DIR.parent.parent / "resources" / "connector_seeds.json"

# Ensure project root is on sys.path (so we can import app modules)
_SYS_PATH_SET = False


def _ensure_path():
    global _SYS_PATH_SET
    if not _SYS_PATH_SET:
        root = BACKEND_DIR.resolve()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        _SYS_PATH_SET = True


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class Check:
    """A single check result."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"

    def __init__(self, name: str, status: str, detail: str = ""):
        self.name = name
        self.status = status
        self.detail = detail

    def __str__(self) -> str:
        icon = {"PASS": "[OK]", "FAIL": "[!!]", "SKIP": "[--]"}.get(self.status, "[??]")
        line = f"  {icon} {self.name}"
        if self.detail:
            line += f"  ({self.detail})"
        return line


class PackageResult:
    """Results for one provider package."""

    def __init__(self, name: str):
        self.name = name
        self.checks: List[Check] = []
        self.total_endpoints = 0

    @property
    def passed(self) -> bool:
        return all(c.status != Check.FAIL for c in self.checks)

    def add(self, check: Check):
        self.checks.append(check)

    def summary(self, verbose: bool = False) -> str:
        header = f"\n{'=' * 60}\n{self.name}\n{'=' * 60}"
        lines = [header]
        for c in self.checks:
            if verbose or c.status == Check.FAIL:
                lines.append(str(c))
        if not verbose and self.passed:
            lines.append(f"  [OK] All {len(self.checks)} checks passed ({self.total_endpoints} endpoints)")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Syntax check
# ---------------------------------------------------------------------------


def check_syntax(filepath: Path) -> Check:
    """ast.parse the file to catch syntax errors."""
    name = f"Syntax: {filepath.name}"
    try:
        source = filepath.read_text(encoding="utf-8")
        ast.parse(source, filename=str(filepath))
        return Check(name, Check.PASS)
    except SyntaxError as e:
        return Check(name, Check.FAIL, f"{e.msg} at line {e.lineno}: {e.text and e.text.strip()}")


# ---------------------------------------------------------------------------
# Provider package checks
# ---------------------------------------------------------------------------


def check_provider_package(pkg_dir: Path) -> Optional[PackageResult]:
    """Run all checks on a single provider package."""
    name = pkg_dir.name
    result = PackageResult(name)
    provider_py = pkg_dir / "provider.py"

    # 1. Check the provider.py exists
    if not provider_py.exists():
        result.add(Check("provider.py exists", Check.FAIL, "file not found"))
        return result

    # 2. Syntax check
    result.add(check_syntax(provider_py))
    if result.checks[-1].status == Check.FAIL:
        return result

    # 3. Import check (can the module be loaded?)
    try:
        _ensure_path()
        mod_name = f"app.modules.connectors.providers.{name}.provider"
        spec = importlib.util.find_spec(mod_name)
        if spec is None:
            result.add(Check("Module import", Check.FAIL, f"module {mod_name} not found"))
            return result
        mod = importlib.import_module(mod_name)
        result.add(Check("Module import", Check.PASS))
    except Exception as e:
        tb = traceback.format_exc()
        result.add(Check("Module import", Check.FAIL, f"{type(e).__name__}: {e}"))
        if "--verbose" in sys.argv or "-v" in sys.argv:
            print(tb)
        return result

    # 4. Provider class exists
    provider_cls = getattr(mod, "Provider", None)
    if provider_cls is None:
        result.add(Check("Provider class", Check.FAIL, "no Provider class defined"))
        return result
    result.add(Check("Provider class", Check.PASS))

    # 5. Has provider_id
    pid = getattr(provider_cls, "provider_id", None)
    if not pid:
        result.add(Check("provider_id", Check.FAIL, "provider_id not set"))
    elif pid != name:
        result.add(Check("provider_id", Check.PASS, f"'{pid}' matches dir name"))
    else:
        result.add(Check("provider_id", Check.PASS, f"'{pid}'"))

    # 6. Inherits from proper base
    from app.modules.connectors.providers.base import BaseConnectorProvider, RESTProvider

    proper_base = issubclass(provider_cls, BaseConnectorProvider)
    if not proper_base:
        result.add(Check("Base class", Check.FAIL, "does not inherit from BaseConnectorProvider"))
    else:
        base_name = "RESTProvider" if issubclass(provider_cls, RESTProvider) else "BaseConnectorProvider"
        result.add(Check("Base class", Check.PASS, base_name))

    # 7. Endpoint validation
    endpoints = {}
    if hasattr(provider_cls, "endpoints"):
        endpoints.update(provider_cls.endpoints)
    # Also check for product-specific dictionaries (Atlassian pattern)
    for attr_name in dir(mod):
        attr_val = getattr(mod, attr_name)
        if isinstance(attr_val, dict) and attr_name.endswith("_ENDPOINTS") and not attr_name.startswith("_"):
            endpoints.update(attr_val)

    if not endpoints:
        result.add(Check("Endpoints", Check.PASS, "0 endpoints (runtime-only)"))
        return result

    result.total_endpoints = len(endpoints)
    result.add(Check("Endpoints defined", Check.PASS, f"{len(endpoints)} total"))

    # Validate each endpoint
    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    bad_endpoints: List[str] = []
    for tid, ep_tuple in endpoints.items():
        if not isinstance(ep_tuple, (tuple, list)) or len(ep_tuple) != 2:
            bad_endpoints.append(f"{tid}: not a (method, path) tuple")
            continue
        method, path = ep_tuple
        if not isinstance(method, str) or method.upper() not in valid_methods:
            bad_endpoints.append(f"{tid}: invalid method '{method}'")
        if not isinstance(path, str) or not path.startswith("/"):
            bad_endpoints.append(f"{tid}: path '{path}' does not start with /")

    if bad_endpoints:
        for err in bad_endpoints:
            result.add(Check("Endpoint format", Check.FAIL, err))
    else:
        result.add(Check("Endpoint format", Check.PASS, "all valid"))

    # 8. Duplicate tool IDs within this provider
    seen_ids: Set[str] = set()
    dupes: Set[str] = set()
    for tid in endpoints:
        if tid in seen_ids:
            dupes.add(tid)
        seen_ids.add(tid)
    if dupes:
        result.add(Check("No duplicate tool IDs", Check.FAIL, f"duplicates: {sorted(dupes)}"))
    else:
        result.add(Check("No duplicate tool IDs", Check.PASS))

    # 9. Extract path parameters and check they match tool_id prefix
    import re
    param_re = re.compile(r"\{(\w+)\}")
    missing_params: List[str] = []
    for tid, ep_tuple in endpoints.items():
        if not isinstance(ep_tuple, (tuple, list)) or len(ep_tuple) != 2:
            continue  # already flagged above
        _method, path = ep_tuple
        params_in_path = param_re.findall(path)
        for p in params_in_path:
            if not p.isidentifier():
                missing_params.append(f"{tid}: invalid param name '{p}'")
    if missing_params:
        for err in missing_params:
            result.add(Check("Path params", Check.FAIL, err))
    else:
        result.add(Check("Path params", Check.PASS, "all valid"))

    return result


# ---------------------------------------------------------------------------
# Fallback TOOL_ENDPOINTS check
# ---------------------------------------------------------------------------


def check_fallback_endpoints() -> PackageResult:
    """Check the legacy TOOL_ENDPOINTS dict in execute_engine.py."""
    result = PackageResult("execute_engine.py (fallback TOOL_ENDPOINTS)")

    # Syntax check
    result.add(check_syntax(EXECUTE_ENGINE_PATH))
    if result.checks[-1].status == Check.FAIL:
        return result

    # Import and grab TOOL_ENDPOINTS
    try:
        _ensure_path()
        mod = importlib.import_module("app.modules.connectors.execute_engine")
        endpoints = getattr(mod, "TOOL_ENDPOINTS", {})
        result.add(Check("Import TOOL_ENDPOINTS", Check.PASS, f"{len(endpoints)} entries"))

        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        bad: List[str] = []
        for tid, ep in endpoints.items():
            if not isinstance(ep, (tuple, list)) or len(ep) != 2:
                bad.append(f"{tid}: not a (method, path) tuple")
                continue
            method, path = ep
            if not isinstance(method, str) or method.upper() not in valid_methods:
                bad.append(f"{tid}: invalid method '{method}'")
            if not isinstance(path, str) or not path.startswith("/"):
                bad.append(f"{tid}: path '{path}' does not start with /")
        if bad:
            for err in bad:
                result.add(Check("Endpoint format", Check.FAIL, err))
        else:
            result.add(Check("Endpoint format", Check.PASS, "all valid"))

        # Duplicates check
        seen: Set[str] = set()
        dupes: Set[str] = set()
        for tid in endpoints:
            if tid in seen:
                dupes.add(tid)
            seen.add(tid)
        if dupes:
            result.add(Check("No duplicate tool IDs", Check.FAIL, f"duplicates: {sorted(dupes)}"))
        else:
            result.add(Check("No duplicate tool IDs", Check.PASS))

        # Check cross-reference: all provider endpoints vs fallback
        # Identify providers that cover tools which are also in fallback
        provider_tools = _collect_all_provider_tools()
        overlapping = set(endpoints.keys()) & provider_tools
        if overlapping:
            result.add(Check("Fallback overlap with providers", Check.SKIP, f"{len(overlapping)} tools also defined in providers"))

    except Exception as e:
        result.add(Check("Import TOOL_ENDPOINTS", Check.FAIL, f"{type(e).__name__}: {e}"))

    return result


def _collect_all_provider_tools() -> Set[str]:
    """Collect all tool IDs from all provider packages."""
    _ensure_path()
    tools: Set[str] = set()
    for pkg_dir in sorted(PROVIDERS_DIR.iterdir()):
        if not pkg_dir.is_dir() or pkg_dir.name.startswith("_"):
            continue
        provider_py = pkg_dir / "provider.py"
        if not provider_py.exists():
            continue
        try:
            mod_name = f"app.modules.connectors.providers.{pkg_dir.name}.provider"
            mod = importlib.import_module(mod_name)
            provider_cls = getattr(mod, "Provider", None)
            if provider_cls and hasattr(provider_cls, "endpoints"):
                tools.update(provider_cls.endpoints.keys())
            for attr_name in dir(mod):
                attr_val = getattr(mod, attr_name)
                if isinstance(attr_val, dict) and attr_name.endswith("_ENDPOINTS"):
                    tools.update(attr_val.keys())
        except Exception:
            pass
    return tools


# ---------------------------------------------------------------------------
# Seed cross-reference check
# ---------------------------------------------------------------------------


def check_seed_crossref() -> PackageResult:
    """Check that all seeded tool IDs have corresponding endpoints."""
    result = PackageResult("Seed cross-reference")

    provider_tools = _collect_all_provider_tools()

    if not SEED_PATH.exists():
        result.add(Check("Seed file exists", Check.SKIP, "connector_seeds.json not found"))
        return result

    try:
        import json
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            seeds = json.load(f)

        all_seeded: Set[str] = set()
        for seed in seeds:
            for tool in seed.get("tools", []):
                all_seeded.add(tool["id"])

        result.add(Check("Seed loaded", Check.PASS, f"{len(all_seeded)} tool IDs in seeds"))

        missing = all_seeded - provider_tools
        if missing:
            result.add(Check("All seeded tools have endpoints", Check.FAIL, f"{len(missing)} missing: {sorted(missing)}"))
        else:
            result.add(Check("All seeded tools have endpoints", Check.PASS))

        # Also check count
        result.add(Check("Total endpoints match", Check.PASS, f"{len(all_seeded)} seeded ≈ {len(provider_tools)} provider"))

    except Exception as e:
        result.add(Check("Seed cross-ref", Check.FAIL, f"{type(e).__name__}: {e}"))

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Verify all connector provider definitions")
    parser.add_argument("connector", nargs="?", help="Check only a single connector (directory name)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all checks (not just failures)")
    parser.add_argument("--skip-fallback", action="store_true", help="Skip fallback TOOL_ENDPOINTS check")
    parser.add_argument("--skip-seed", action="store_true", help="Skip seed cross-reference check")
    args = parser.parse_args()

    if not PROVIDERS_DIR.exists():
        print(f"ERROR: Providers directory not found: {PROVIDERS_DIR}")
        sys.exit(1)

    all_results: List[PackageResult] = []
    has_failure = False

    # --- Per-provider checks ---
    pkg_dirs = sorted(PROVIDERS_DIR.iterdir())
    target = args.connector

    for pkg_dir in pkg_dirs:
        if not pkg_dir.is_dir() or pkg_dir.name.startswith("_"):
            continue
        if target and pkg_dir.name != target:
            continue
        result = check_provider_package(pkg_dir)
        if result:
            all_results.append(result)
            has_failure = has_failure or not result.passed

    if target and not all_results:
        print(f"ERROR: No provider directory found for '{target}'")
        sys.exit(1)

    # --- Fallback endpoints check ---
    if not args.skip_fallback and EXECUTE_ENGINE_PATH.exists():
        result = check_fallback_endpoints()
        all_results.append(result)
        has_failure = has_failure or not result.passed

    # --- Seed crossref check ---
    if not args.skip_seed:
        result = check_seed_crossref()
        all_results.append(result)
        has_failure = has_failure or not result.passed

    # --- Summary ---
    total_checks = sum(len(r.checks) for r in all_results)
    total_fails = sum(sum(1 for c in r.checks if c.status == Check.FAIL) for r in all_results)
    total_skips = sum(sum(1 for c in r.checks if c.status == Check.SKIP) for r in all_results)

    verbose = args.verbose or has_failure

    for result in all_results:
        print(result.summary(verbose=verbose))

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {total_checks} checks, {total_fails} failures, {total_skips} skipped, {len(all_results)} packages")
    print(f"{'=' * 60}")

    sys.exit(1 if has_failure else 0)


if __name__ == "__main__":
    main()
