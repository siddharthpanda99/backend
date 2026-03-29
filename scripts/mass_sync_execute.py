import sys
import os

# Set environment variables for DB if needed, though app.core.common_lib_integration usually handles it
os.environ["DATABASE_URL"] = "postgresql://agent_user:agent_password@localhost:5433/agentic_data"

# Add paths to sys.path
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend")
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src")

from app.core.common_lib_integration import common_memory
from common_lib.modules.orchestration.sync.manager import EntitySyncManager

templates_root = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src\common_lib\templates"

print(f"Starting massive bidirectional synchronization from {templates_root}...")
sync_manager = EntitySyncManager(common_memory, templates_root)
report = sync_manager.sync_complete(rebuild_index=True)

print("\n--- SYNC REPORT ---")
print(f"Total entities processed: {report.entities_processed}")
print(f"Files successfully imported: {report.files_imported}")
print(f"Files exported (mirrored): {report.files_exported}")
print(f"Entities created/updated in DB: {report.entities_created}")

if report.errors:
    print(f"\nErrors encountered ({len(report.errors)}):")
    for err in report.errors[:20]:  # Limit output
        print(f" - {err}")
print("Index rebuilt successfully.")
