"""
run_full_registry_sync.py
-------------------------
Syncs the entire filesystem registry (YAML) with the database.
Now includes hydration for the new prompt_template/resolved_prompt columns.
"""
import sys, os
import logging
from sqlalchemy import text

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.core.settings import get_settings
cfg = get_settings()

from app.core.common_lib_integration import common_memory, sync_manager
from common_lib.modules.orchestration.sync.manager import EntitySyncManager

# 0. In-process Migration (Ensures columns exist on the same connection being synced)
def migrate_db():
    print("--- Running In-process Migration ---")
    with common_memory.engine.connect() as conn:
        # PostgreSQL syntax for adding column if not exists
        for col, col_type in [
            ("prompt_template", "TEXT"),
            ("resolved_prompt", "TEXT"),
            ("prompt_resolved_at", "TIMESTAMPTZ")
        ]:
            try:
                # Use ALTER TABLE ADD COLUMN IF NOT EXISTS
                conn.execute(text(f"ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                conn.commit()
                print(f"  Column verified: {col}")
            except Exception as e:
                print(f"  Warning adding {col}: {e}")

# 1. Mandatory Seeding of Sections (to ensure agents can resolve references)
def seed_sections():
    print("\n--- Seeding Shared Sections ---")
    sections_root = os.path.join(os.path.dirname(sync_manager.templates_root), "configs", "sections")
    if not os.path.exists(sections_root):
        print(f"Sections root not found at {sections_root}, skipping.")
        return

    for f in os.listdir(sections_root):
        if f.endswith(".section.yaml"):
            fpath = os.path.join(sections_root, f)
            print(f"  Importing section: {f}")
            sync_manager.import_from_file("section", fpath, import_source="seed")

# 2. Main Sync of Entities
def sync_registry():
    print("\n--- Syncing Registry Entities (FS -> DB) ---")
    # We scan for all types to ensure parity
    report = sync_manager.sync_all_from_files()
    print(f"Sync complete. Processed {report.entities_processed} entities.")
    if report.errors:
        print(f"Errors encountered: {len(report.errors)}")
        for err in report.errors[:5]:
            print(f"  - {err}")

# 3. Specific resolution check for prompt-templating
def verify_resolution():
    print("\n--- Verifying Prompt Resolution ---")
    with common_memory._get_session() as session:
        from common_lib.modules.orchestration.agent.models import AgentDefinitionRecord
        agents = session.query(AgentDefinitionRecord).all()
        for a in agents:
            status = "RESOLVED" if a.resolved_prompt else "EMPTY"
            print(f"  Agent: {a.id:20} | Template: {'YES' if a.prompt_template else 'NO ':4} | Resolved: {status}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    migrate_db()
    seed_sections()
    sync_registry()
    verify_resolution()
    print("\nAll tasks complete.")
