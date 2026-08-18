#!/usr/bin/env python
"""
Comprehensive import validation for Backend app.
Validates: router -> route handlers -> common_lib service imports.
Catches stale imports from refactoring that only fail at request time.
"""

from __future__ import annotations

import ast
import inspect
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI

# Add backend to path
BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Also add common_lib - use absolute path
COMMON_LIB_ROOT = BACKEND_ROOT.parent / "Python Libs" / "common_lib" / "src"
sys.path.insert(0, str(COMMON_LIB_ROOT.resolve()))


def extract_imports_from_function(func) -> set[str]:
    """Extract all imports used by a function via static analysis."""
    try:
        source = inspect.getsource(func)
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.add(f"{module}.{alias.name}" if module else alias.name)
        return imports
    except Exception:
        return set()


def check_common_lib_import(import_path: str) -> tuple[bool, str]:
    """Verify a common_lib import resolves correctly."""
    if not import_path.startswith("common_lib."):
        return True, "not common_lib"

    try:
        # Handle both module imports (common_lib.module) and from imports (common_lib.module.Class)
        parts = import_path.split(".")
        module_path = (
            ".".join(parts[:-1])
            if len(parts) > 1 and not import_path.endswith(".")
            else import_path
        )
        attr_name = (
            parts[-1] if len(parts) > 1 and not import_path.endswith(".") else None
        )

        module = __import__(module_path, fromlist=[attr_name] if attr_name else [])
        if attr_name:
            getattr(module, attr_name)
        return True, "OK"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def validate_endpoint(endpoint) -> list[tuple[str, str]]:
    """Validate all common_lib imports used by an endpoint."""
    issues = []

    # Unwrap decorators
    handler = endpoint
    while hasattr(handler, "__wrapped__"):
        handler = handler.__wrapped__

    # Extract imports
    imports = extract_imports_from_function(handler)

    # Check each common_lib import
    for imp in imports:
        if imp.startswith("common_lib."):
            ok, msg = check_common_lib_import(imp)
            if not ok:
                issues.append((imp, msg))

    return issues


def main():
    print("=" * 80)
    print("COMPREHENSIVE BACKEND IMPORT VALIDATION")
    print("=" * 80)

    # Create dummy app and register all routers
    app = FastAPI()

    # Import and call register_routers
    from app.core.routers import register_routers

    class DummySettings:
        API_V1_STR = "/api/v1"

    settings = DummySettings()
    global_deps = []

    try:
        register_routers(app, settings.API_V1_STR, global_deps)
        print(f"\nRegistered routers successfully. Total routes: {len(app.routes)}")
    except Exception as e:
        print(f"FAILED to register routers: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # Validate each route
    all_issues = []
    total_validated = 0
    issue_counter = defaultdict(int)
    import_to_routes = defaultdict(list)

    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue

        path = getattr(route, "path", "unknown")
        methods = getattr(route, "methods", set())
        route_key = f"{methods} {path}"

        issues = validate_endpoint(endpoint)
        if issues:
            for imp, msg in issues:
                all_issues.append((route_key, imp, msg))
                issue_counter[imp] += 1
                import_to_routes[imp].append(route_key)
            print(f"  FAIL {route_key}: {len(issues)} import issues")
        else:
            total_validated += 1

    print(f"\n{'=' * 80}")
    print(
        f"SUMMARY: {total_validated} routes validated, {len(all_issues)} total import issues"
    )
    print(f"UNIQUE FAILING IMPORTS: {len(issue_counter)}")
    print("=" * 80)

    if all_issues:
        # Group by import path, sort by frequency
        sorted_imports = sorted(issue_counter.items(), key=lambda x: -x[1])

        print("\nTOP FAILING IMPORTS (by frequency):")
        for imp, count in sorted_imports[:30]:
            print(f"  [{count:3d}x] {imp}")
            msg = import_to_routes[imp][0][2] if import_to_routes[imp] else "unknown"
            print(f"          Error: {msg}")
            # Show first few affected routes
            for route_key in import_to_routes[imp][:3]:
                print(f"          -> {route_key}")
            if len(import_to_routes[imp]) > 3:
                print(f"          ... and {len(import_to_routes[imp]) - 3} more routes")
            print()

        # Save full report
        report_path = BACKEND_ROOT / "import_validation_report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"BACKEND IMPORT VALIDATION REPORT\n")
            f.write(f"{'=' * 80}\n")
            f.write(f"Total routes: {len(app.routes)}\n")
            f.write(f"Routes validated: {total_validated}\n")
            f.write(f"Total issues: {len(all_issues)}\n")
            f.write(f"Unique failing imports: {len(issue_counter)}\n\n")

            for imp, count in sorted_imports:
                f.write(f"[{count:3d}x] {imp}\n")
                f.write(f"  Error: {import_to_routes[imp][0][2]}\n")
                for route_key in import_to_routes[imp]:
                    f.write(f"  -> {route_key}\n")
                f.write("\n")

        print(f"\nFull report saved to: {report_path}")
        return 1

    print("\nALL IMPORTS VALIDATED SUCCESSFULLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
