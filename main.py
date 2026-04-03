import uvicorn
from app.main import app

# --- CENTRALIZED LOGGING INITIALIZATION ---
from app.core.logging_config import setup_logging
setup_logging("logs/server.log")

import sys
from pathlib import Path

# Add paths to sys.path if not already there, though hatch/uv handles this
# but ensuring reload watches the right directories
backend_dir = str(Path(__file__).parent.resolve())
common_lib_dir = str((Path(__file__).parent.parent / "Python Libs" / "common_lib" / "src").resolve())

if __name__ == "__main__":
    # Specify the EXACT directories to watch to avoid circular restarts from logs/assets/generated_content
    app_dir = str((Path(__file__).parent / "app").resolve())
    common_lib_dir = str((Path(__file__).parent.parent / "Python Libs" / "common_lib" / "src").resolve())
    
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True, 
        reload_dirs=[app_dir, common_lib_dir],
        reload_excludes=[
            "logs/*", 
            "**/logs/*",
            "resources/*",
            "**/resources/*",
            "**/resources/**/*",
            "**/resources/*.yaml", 
            "**/resources/*.json",
            "CHARACTER_PROFILES_DIR/*",
            "**/character_profiles/*",
            "**/__pycache__/*",
            "**/__pycache__/**",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.pyd",
            "**/*.db*",      # SQLite databases, journals, WAL files
            "**/.db*",
            "**/.pytest_cache/*",
            ".antigrav-history/*",
            "**/.idea/*",    # JetBrains
            "**/.vscode/*",  # VS Code
            "**/.git/*",     # Git
            "*.log"
        ]

    )
