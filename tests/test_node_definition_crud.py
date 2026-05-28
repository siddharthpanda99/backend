#!/usr/bin/env python3
"""Comprehensive E2E tests for Node Definition CRUD API endpoints."""

import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
os.environ["PYTHONIOENCODING"] = "utf-8"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
BASE = "/api/v1/entities/registry"
passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  [{detail}]")


print("=== Node Definition CRUD E2E Tests ===\n")

# 1. LIST: GET /definitions
print("[1] LIST definitions via GET /definitions")
r = client.get(f"{BASE}/definitions")
check("200 OK", r.status_code == 200)
data = r.json()
check("status=success", data.get("status") == "success")
defs = data.get("data", [])
check("has definitions", len(defs) > 0, f"count={len(defs)}")
has_tools = any(d.get("type", "").startswith("core.") for d in defs)
check("has core tools", has_tools)
check("count >= 350", len(defs) >= 350, f"count={len(defs)}")

# 2. GET single (non-existent)
print("\n[2] GET nonexistent node_definition")
r = client.get(f"{BASE}/node_definition/nonexistent.node")
check("404 on missing", r.status_code == 404)

# 3. CREATE via dedicated POST /node_definition
print("\n[3] CREATE node_definition via POST")
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
check(f"200 OK", r.status_code == 200, f"status={r.status_code}")
data = r.json()
check("status=success", data.get("status") == "success")
print(f"  message: {data.get('message', '')}")

# 4. GET single (now exists)
print("\n[4] GET created node_definition")
r = client.get(f"{BASE}/node_definition/e2e.test.node")
check("200 OK", r.status_code == 200)
data = r.json()
node = data.get("data", {})
check("retrieved id matches", node.get("id") == "e2e.test.node", f"id={node.get('id')}")
check(
    "retrieved name matches",
    node.get("name") == "E2E Test Node",
    f"name={node.get('name')}",
)

# 5. PUT (update)
print("\n[5] UPDATE node_definition via PUT")
updated = new_node.copy()
updated["name"] = "E2E Test Node Updated"
updated["description"] = "Updated during E2E test"
r = client.put(f"{BASE}/node_definition/e2e.test.node", json=updated)
check("200 OK", r.status_code == 200, f"status={r.status_code}")
data = r.json()
check("status=success", data.get("status") == "success")
check("has data dict", isinstance(data.get("data"), dict))

r2 = client.get(f"{BASE}/node_definition/e2e.test.node")
node2 = r2.json().get("data", {})
check(
    "name updated",
    node2.get("name") == "E2E Test Node Updated",
    f"name={node2.get('name')}",
)
check("description updated", node2.get("description") == "Updated during E2E test")

# 6. DELETE
print("\n[6] DELETE node_definition")
r = client.delete(f"{BASE}/node_definition/e2e.test.node")
check("200 OK", r.status_code == 200, f"status={r.status_code}")
data = r.json()
check("status=success", data.get("status") == "success")
check("data is true", data.get("data") == True)

r3 = client.get(f"{BASE}/node_definition/e2e.test.node")
check("404 after delete", r3.status_code == 404)

# 7. DELETE nonexistent
print("\n[7] DELETE nonexistent node_definition")
r = client.delete(f"{BASE}/node_definition/never.existed")
check("404 on delete missing", r.status_code == 404)

# 8. Full lifecycle
print("\n[8] Full lifecycle: POST -> GET -> PUT -> GET -> DELETE -> GET")
r = client.post(
    f"{BASE}/node_definition",
    json={"id": "e2e.lifecycle.node", "name": "Lifecycle Node", "version": "1.0.0"},
)
check("lifecycle create", r.status_code == 200 and r.json().get("status") == "success")

r = client.get(f"{BASE}/node_definition/e2e.lifecycle.node")
check("lifecycle get after create", r.status_code == 200)
check(
    "lifecycle name correct", r.json().get("data", {}).get("name") == "Lifecycle Node"
)

r = client.put(
    f"{BASE}/node_definition/e2e.lifecycle.node",
    json={
        "id": "e2e.lifecycle.node",
        "name": "Lifecycle Node Updated",
        "version": "1.0.0",
    },
)
check(
    "lifecycle update status",
    r.status_code == 200 and r.json().get("status") == "success",
)

r = client.get(f"{BASE}/node_definition/e2e.lifecycle.node")
check("lifecycle get after update", r.status_code == 200)
check(
    "lifecycle name updated",
    r.json().get("data", {}).get("name") == "Lifecycle Node Updated",
)

r = client.delete(f"{BASE}/node_definition/e2e.lifecycle.node")
check("lifecycle delete", r.status_code == 200 and r.json().get("data") == True)

r = client.get(f"{BASE}/node_definition/e2e.lifecycle.node")
check("lifecycle get after delete", r.status_code == 404)

# Summary
total = passed + failed
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed}/{total} passed, {failed}/{total} failed")
if failed > 0:
    sys.exit(1)
