#!/usr/bin/env python3
"""Comprehensive E2E tests for Node Definition CRUD API endpoints."""

import sys, os, json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PYTHONIOENCODING"] = "utf-8"

from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

BASE = "/api/v1/entities/registry"


def test_node_definition_crud_flow(client):
    # 1. LIST: GET /definitions
    r = client.get(f"{BASE}/definitions")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "success"
    defs = data.get("data", [])
    assert len(defs) > 0
    has_tools = any(d.get("type", "").startswith("core.") for d in defs)
    assert has_tools
    assert len(defs) >= 350

    # 2. GET single (non-existent)
    r = client.get(f"{BASE}/node_definition/nonexistent.node")
    assert r.status_code == 404

    # 3. CREATE via dedicated POST /node_definition
    new_node = {
        "id": "e2e.test.node",
        "name": "E2E Test Node",
        "description": "Created during E2E test",
        "version": "1.0.0",
        "category": "E2E Test",
        "inputs": [{"id": "in", "type": "string"}],
        "outputs": [{"id": "out", "type": "string"}],
        "ui": {"color": "#ff6600"},
        "properties": {"prop1": {"type": "text", "label": "Test"}},
    }
    r = client.post(f"{BASE}/node_definition", json=new_node)
    assert r.status_code == 200, f"status={r.status_code}"
    data = r.json()
    assert data.get("status") == "success"

    # 4. GET single (now exists)
    r = client.get(f"{BASE}/node_definition/e2e.test.node")
    assert r.status_code == 200
    data = r.json()
    node = data.get("data", {})
    assert node.get("id") == "e2e.test.node"
    assert node.get("name") == "E2E Test Node"

    # 5. PUT (update)
    updated = new_node.copy()
    updated["name"] = "E2E Test Node Updated"
    updated["description"] = "Updated during E2E test"
    r = client.put(f"{BASE}/node_definition/e2e.test.node", json=updated)
    assert r.status_code == 200, f"status={r.status_code}"
    data = r.json()
    assert data.get("status") == "success"
    assert isinstance(data.get("data"), dict)

    r2 = client.get(f"{BASE}/node_definition/e2e.test.node")
    node2 = r2.json().get("data", {})
    assert node2.get("name") == "E2E Test Node Updated"
    assert node2.get("description") == "Updated during E2E test"

    # 6. DELETE
    r = client.delete(f"{BASE}/node_definition/e2e.test.node")
    assert r.status_code == 200, f"status={r.status_code}"
    data = r.json()
    assert data.get("status") == "success"
    assert data.get("data") is True

    r3 = client.get(f"{BASE}/node_definition/e2e.test.node")
    assert r3.status_code == 404

    # 7. DELETE nonexistent
    r = client.delete(f"{BASE}/node_definition/never.existed")
    assert r.status_code == 404

    # 8. Full lifecycle
    r = client.post(
        f"{BASE}/node_definition",
        json={"id": "e2e.lifecycle.node", "name": "Lifecycle Node", "version": "1.0.0"},
    )
    assert r.status_code == 200 and r.json().get("status") == "success"

    r = client.get(f"{BASE}/node_definition/e2e.lifecycle.node")
    assert r.status_code == 200
    assert r.json().get("data", {}).get("name") == "Lifecycle Node"

    r = client.put(
        f"{BASE}/node_definition/e2e.lifecycle.node",
        json={
            "id": "e2e.lifecycle.node",
            "name": "Lifecycle Node Updated",
            "version": "1.0.0",
        },
    )
    assert r.status_code == 200 and r.json().get("status") == "success"

    r = client.get(f"{BASE}/node_definition/e2e.lifecycle.node")
    assert r.status_code == 200
    assert r.json().get("data", {}).get("name") == "Lifecycle Node Updated"

    r = client.delete(f"{BASE}/node_definition/e2e.lifecycle.node")
    assert r.status_code == 200 and r.json().get("data") is True

    r = client.get(f"{BASE}/node_definition/e2e.lifecycle.node")
    assert r.status_code == 404


if __name__ == "__main__":
    client_obj = TestClient(app)
    try:
        test_node_definition_crud_flow(client_obj)
        print("All tests passed successfully!")
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)

