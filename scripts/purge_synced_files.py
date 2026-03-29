import os
import yaml
import sys

# Add paths to sys.path
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend")
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src")

from app.core.common_lib_integration import common_memory
from common_lib.modules.orchestration.sync.manager import EntitySyncManager

templates_root = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src\common_lib\templates"
index_path = os.path.join(templates_root, "index.yaml")

if not os.path.exists(index_path):
    print("Error: index.yaml not found. Run sync first.")
    sys.exit(1)

with open(index_path, 'r', encoding='utf-8') as f:
    index_data = yaml.safe_load(f)

manifest = index_data.get("manifest", {})
files_to_delete = []

for entity_type, entities in manifest.items():
    for entity in entities:
        if entity.get("location") == "both":
            rel_path = entity.get("path")
            if rel_path:
                full_path = os.path.join(templates_root, rel_path)
                if os.path.exists(full_path):
                    files_to_delete.append(full_path)

print(f"Found {len(files_to_delete)} files that are synced to DB and can be safely removed.")

# Perform deletion
deleted_count = 0
for file_path in files_to_delete:
    try:
        os.remove(file_path)
        deleted_count += 1
    except Exception as e:
        print(f"Failed to delete {file_path}: {e}")

print(f"\nSuccessfully deleted {deleted_count} legacy YAML files.")

# Rebuild index to reflect changes
print("\nRebuilding index.yaml...")
sync_manager = EntitySyncManager(common_memory, templates_root)
sync_manager.rebuild_index()
print("Done.")
