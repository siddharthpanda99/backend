import os
import sys
import uuid
import requests
import pytest
from pathlib import Path

# Bootstrap path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Adjust BASE_URL to point to the actual API
BASE_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1")
FILE_BROWSER_URL = f"{BASE_URL}/file-browser"

@pytest.fixture(scope="module")
def api_base():
    """Verify API is up before running tests."""
    try:
        # Check health using storage stats
        resp = requests.get(f"{FILE_BROWSER_URL}/storage", timeout=5)
        resp.raise_for_status()
        return FILE_BROWSER_URL
    except Exception as e:
        pytest.skip(f"API not accessible at {FILE_BROWSER_URL}: {e}")

@pytest.fixture
def test_id():
    """Unique ID for test isolation."""
    return uuid.uuid4().hex[:8]

@pytest.fixture
def temp_file(api_base, test_id):
    """Fixture to create and cleanup a test file."""
    filename = f"test_file_{test_id}.txt"
    content = b"This is a test file for modular testing."
    
    files = {"file": (filename, content, "text/plain")}
    resp = requests.post(f"{api_base}/files", files=files)
    resp.raise_for_status()
    file_id = resp.json()["id"]
    
    yield file_id
    
    # Cleanup: Permanent delete
    try:
        requests.post(f"{api_base}/files/bulk-delete", json={"ids": [file_id], "permanent": True}, timeout=2)
    except:
        pass
