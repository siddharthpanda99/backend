"""
Integration test conftest — completely isolated from project_management's
autouse fixtures that patch ``_get_session`` and pollute ``SQLModel.metadata``.

This directory has NO ``autouse=True`` fixtures.
All integration tests manage their own real database connections.
"""

import os
import sys
from pathlib import Path

# Bootstrap paths (same as parent conftest)
BACKEND_ROOT = Path(__file__).parent.parent.resolve()
PROJECT_ROOT = BACKEND_ROOT.parent
COMMON_LIB_SRC = str(PROJECT_ROOT / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
