"""Final RBAC fix: add missing bare-name aliases to conftest and fix test imports."""

import os
import re

# ============================================================
# 1. Add bare-name aliases for policy engine tables
# ============================================================

conftest_path = "tests/rbac/conftest.py"
with open(conftest_path, "r", encoding="utf-8") as f:
    content = f.read()

aliases_marker = "# Policy Engine bare-name aliases"
if aliases_marker not in content:
    content = content.replace(
        "rbac_cache_entries_table = rbac_cache_entries\n\n",
        "rbac_cache_entries_table = rbac_cache_entries\n\n"
        "# Policy engine bare-name aliases\n"
        "policy_rules = rbac_policy_rules\n"
        "abac_conditions = rbac_abac_conditions\n"
        "rebac_relations = rbac_rebac_relations\n\n"
    )
    with open(conftest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("FIX 1: Added policy engine bare-name aliases to conftest.py")
else:
    print("OK 1: Policy engine aliases already present")

# ============================================================
# 2. Fix test_permission_check_api.py - add bare name imports
# ============================================================

fpath = "tests/rbac/test_permission_check_api.py"
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()

# Check if the import line exists and has _table suffix
import_match = re.search(r"^from tests\.rbac\.conftest import (.*)$", content, re.MULTILINE)
if import_match:
    current_imports = import_match.group(1).strip()
    # Replace _table suffix with bare names in the import
    fixed_imports = current_imports.replace("_table", "")
    if fixed_imports != current_imports:
        content = content.replace(current_imports, fixed_imports)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"FIX 2: Fixed imports in test_permission_check_api.py")
    else:
        print(f"OK 2: test_permission_check_api.py imports already bare")
else:
    print(f"WARN 2: No conftest import found in test_permission_check_api.py")

# ============================================================
# 3. Fix test_policy_engine.py import to include bare names
# ============================================================

fpath = "tests/rbac/test_policy_engine.py"
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()

import_match = re.search(r"^from tests\.rbac\.conftest import (.*)$", content, re.MULTILINE)
if import_match:
    current_imports = import_match.group(1).strip()
    # Ensure bare names are included alongside the existing ones
    names = [n.strip() for n in current_imports.split(",")]
    needed_bare = {"rbac_policy_rules": "policy_rules", "rbac_abac_conditions": "abac_conditions", "rbac_rebac_relations": "rebac_relations"}
    updated = False
    final_names = []
    for name in names:
        final_names.append(name)
        if name in needed_bare:
            bare = needed_bare[name]
            if bare not in names:
                final_names.append(bare)
                updated = True
                del needed_bare[name]
    
    if updated:
        new_import = ", ".join(final_names)
        content = content.replace(current_imports, new_import)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"FIX 3: Added bare-name imports to test_policy_engine.py")
    else:
        print(f"OK 3: test_policy_engine.py imports already correct")
else:
    print(f"WARN 3: No conftest import found in test_policy_engine.py")

print("\nAll fixes applied.")
