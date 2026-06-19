#!/usr/bin/env python3
"""Standardize all backend app/modules from routes.py to routes/ directory pattern."""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

MODULES_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "modules")


def convert_module(module_path: str) -> bool:
    name = os.path.basename(os.path.normpath(module_path))
    old_routes_py = os.path.join(module_path, "routes.py")
    routes_dir = os.path.join(module_path, "routes")

    if os.path.isdir(routes_dir):
        return False

    if not os.path.isfile(old_routes_py):
        return False

    with open(old_routes_py, "r", encoding="utf-8") as f:
        content = f.read()

    os.makedirs(routes_dir, exist_ok=True)

    # Write routes/router.py with the same content
    with open(os.path.join(routes_dir, "router.py"), "w", encoding="utf-8") as f:
        f.write(content)

    # Write routes/__init__.py
    with open(os.path.join(routes_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(f"from app.modules.{name}.routes.router import router\n\n__all__ = [\"router\"]\n")

    os.remove(old_routes_py)
    return True


def main():
    modules = sorted([
        os.path.join(MODULES_DIR, d)
        for d in os.listdir(MODULES_DIR)
        if os.path.isdir(os.path.join(MODULES_DIR, d)) and not d.startswith("_")
    ])

    converted = []
    skipped = []

    for mod_path in modules:
        name = os.path.basename(os.path.normpath(mod_path))
        old = os.path.join(mod_path, "routes.py")
        routes_dir = os.path.join(mod_path, "routes")

        if os.path.isdir(routes_dir):
            skipped.append((name, "already has routes/"))
        elif not os.path.isfile(old):
            skipped.append((name, "no routes.py"))
        else:
            convert_module(mod_path)
            converted.append(name)

    print("=" * 60)
    print(f"Converted: {len(converted)} modules")
    print(f"Skipped:   {len(skipped)} modules")
    print("=" * 60)
    if converted:
        print("Converted:", ", ".join(converted))
    if skipped:
        for name, reason in skipped:
            print(f"  - {name}: {reason}")


if __name__ == "__main__":
    main()
