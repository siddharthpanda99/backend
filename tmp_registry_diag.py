
import os
import sys

# Correct mapping for libraries
sys.path.append(r"C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend")
sys.path.append(r"C:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src")

try:
    from common_lib.modules.memories import common_memory
    from common_lib.modules.orchestration.sync.manager import get_sync_manager
except ImportError:
    # Try alternate naming
    from app.modules.memories import common_memory
    from common_lib.modules.orchestration.sync.manager import get_sync_manager

def diag():
    print("--- SYNC MANAGER DIAG ---")
    try:
        sm = get_sync_manager()
        if sm:
            counts = {}
            for key, collection in sm.collections.items():
                counts[key] = len(collection.entities)
            print(f"Collections (sm): {counts}")
    except Exception as e:
        print(f"SyncManager Error: {e}")
        
    print("\n--- COMMON MEMORY DIAG ---")
    try:
        db_skills = common_memory.list_skill_definitions()
        print(f"Skills (DB): {len(db_skills)}")
        
        db_prompts = common_memory.list_prompt_definitions()
        print(f"Prompts (DB): {len(db_prompts)}")
        
        prompt_cats = {}
        for p in db_prompts:
            cat = p.get("logical_category") or "None"
            prompt_cats[cat] = prompt_cats.get(cat, 0) + 1
        print(f"Prompt Categories (DB): {prompt_cats}")
    except Exception as e:
        print(f"CommonMemory Error: {e}")

if __name__ == "__main__":
    diag()
