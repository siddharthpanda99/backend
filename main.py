import uvicorn
from app.main import app

import sys
from pathlib import Path

# Add paths to sys.path if not already there, though hatch/uv handles this
# but ensuring reload watches the right directories
backend_dir = str(Path(__file__).parent.resolve())
common_lib_dir = str((Path(__file__).parent.parent / "Python Libs" / "common_lib" / "src").resolve())

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=[backend_dir, common_lib_dir])
