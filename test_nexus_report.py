import os
import sys
import json
from pathlib import Path

# Setup paths
repo_root = Path(r"c:\Users\91797\Documents\Dev\JS\Monorepo")
common_lib_src = repo_root / "Backend Monorepo" / "Python Libs" / "common_lib" / "src"
sys.path.insert(0, str(common_lib_src))

# Try to mock the node registry so that our custom_reporting module is loaded
import common_lib.modules.plugins.node as node_plugin
from common_lib.modules.workflows.dynamic_runner import DynamicWorkflowRunner

os.environ["MEMORY_BACKEND"] = "in_memory"
os.environ["DB_URL"] = "sqlite:///:memory:"

# Manually import our new nodes to ensure they are registered
import common_lib.modules.db_studio.nodes.custom_reporting

from common_lib.modules.core_infrastructure.registry.tool_registry import RegistryService

# Monkey-patch RegistryService to be a singleton for testing
_registry_instance = None
_original_new = RegistryService.__new__

def singleton_new(cls, *args, **kwargs):
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = _original_new(cls)
        _registry_instance.__init__(*args, **kwargs)
        # Pre-load tools using auto discovery
        from common_lib.modules.core_infrastructure.registry.auto_discovery import AutoDiscovery
        AutoDiscovery(_registry_instance).discover_and_register(exhaustive=True)
    return _registry_instance

RegistryService.__new__ = singleton_new

def main():
    yaml_path = common_lib_src / "common_lib" / "templates" / "workflows" / "executable" / "composition" / "composed_nexus_report.workflow.yaml"
    
    # Check if we have matplotlib
    try:
        import matplotlib
        print("Matplotlib is available.")
    except ImportError:
        print("Warning: Matplotlib not found, chart will not be generated.")

    print(f"Loading workflow: {yaml_path}")
    # Removed incorrect runner initialization
    
    # We will just run it against an in-memory SQLite DB by default for testing
    # But let's create some dummy tables to make the report interesting
    from sqlalchemy import create_engine, text
    db_path = repo_root / "Backend Monorepo" / "Backend" / "test_nexus.db"
    if db_path.exists():
        db_path.unlink()
        
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT)"))
        conn.execute(text("CREATE TABLE comments (id INTEGER PRIMARY KEY, post_id INTEGER, body TEXT)"))
        
        conn.execute(text("INSERT INTO users (name) VALUES ('Alice'), ('Bob'), ('Charlie')"))
        for i in range(15):
            conn.execute(text(f"INSERT INTO posts (user_id, title) VALUES (1, 'Post {i}')"))
        for i in range(42):
            conn.execute(text(f"INSERT INTO comments (post_id, body) VALUES (1, 'Comment {i}')"))
    
    db_url = f"sqlite:///{db_path}"
    print(f"Test DB created at: {db_url}")
    
    inputs = {
        "db_url": db_url,
        "report_title": "Nexus E2E Test Analysis"
    }
    
    import asyncio
    
    print("\nExecuting Workflow...")
    runner = DynamicWorkflowRunner()
    
    # Run the async method using asyncio
    outputs = asyncio.run(runner.run(
        workflow=yaml_path,
        overrides=inputs
    ))
    
    print("\n--- Workflow Execution Complete ---")
    print("Raw Stats Output:", outputs.get("raw_stats"))
    
    report_md = outputs.get("final_markdown", "")
    print("\n--- Generated Markdown Report Preview ---")
    print(report_md[:500] + "...\n[Truncated]" if len(report_md) > 500 else report_md)
    
    # Save the markdown to a file for inspection
    out_file = repo_root / "NEXUS_REPORT.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"\nFull report saved to {out_file}")

if __name__ == "__main__":
    main()
