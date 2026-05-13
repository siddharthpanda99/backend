import sys
import os
from fastapi.testclient import TestClient

# Add paths to sys.path
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend")
sys.path.append(r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Python Libs\common_lib\src")

from app.main import app

client = TestClient(app)

def test_consolidated_wildcard_routes():
    print("Testing GET /api/v1/wildcards/...")
    response = client.get("/api/v1/wildcards/")
    print(f"Status: {response.status_code}")
    print(f"Total: {response.json().get('total')}")
    
    print("\nTesting GET /api/v1/wildcards/sample...")
    response = client.get("/api/v1/wildcards/sample")
    print(f"Status: {response.status_code}")
    
    print("\nTesting POST /api/v1/wildcards/preview...")
    file_content = b"Grouped Mock Value 1\nGrouped Mock Value 2"
    files = {"file": ("grouped_test.txt", file_content, "text/plain")}
    response = client.post("/api/v1/wildcards/preview", files=files)
    print(f"Status: {response.status_code}")
    print(f"Preview Values: {response.json().get('values')}")
    
    print("\nTesting POST /api/v1/wildcards/save...")
    payload = {
        "name": "grouped_test_wildcard",
        "content": "Line A\nLine B",
        "format": "txt"
    }
    response = client.post("/api/v1/wildcards/save", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    try:
        test_consolidated_wildcard_routes()
    except Exception as e:
        print(f"Error during testing: {e}")
