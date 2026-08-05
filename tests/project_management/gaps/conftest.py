"""Gap tests conftest — override parent's autouse fixture.

Gap tests test service classes directly (not @node wrappers),
so we don't need to patch _get_session for any submodule nodes.py files.
This conftest overrides the parent's autouse=True patch_get_session
with a no-op to prevent patching errors.
"""

import os
import sys
from pathlib import Path

import pytest

# Bootstrap paths
BACKEND_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
PROJECT_ROOT = BACKEND_ROOT.parent
COMMON_LIB_SRC = str(PROJECT_ROOT / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Register base PM SQLModel tables so FK references resolve in filtered create_all
from common_lib.modules.project_management.models import Project, Issue, Team


@pytest.fixture(autouse=True)
def patch_get_session():
    """Override parent conftest's autouse fixture with a no-op.

    Gap tests use real SQLModel sessions with filtered table creation,
    so they don't need the _get_session patching that the parent conftest does.
    """
    yield None
