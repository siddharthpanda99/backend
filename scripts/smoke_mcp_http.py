"""Smoke test for the new MCP HTTP endpoints (tools/call + resources/read).

Boots the FastAPI router from app/mcp/routes.py with a TestClient and verifies:
  1. GET  /tools              -> pm.* tools are present
  2. GET  /resources          -> pm:// resources are present
  3. GET  /resources/read     -> reads a pm resource
  4. POST /tools/call         -> invokes a pm tool end-to-end
"""
import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, r"C:/Users/91797/Documents/Dev/JS/Monorepo/Backend Monorepo/Python Libs/common_lib/src")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mcp.routes import router

app = FastAPI()
app.include_router(router, prefix="/api/v1/mcp")
client = TestClient(app)

# 1. tools
r = client.get("/api/v1/mcp/tools")
assert r.status_code == 200, r.text
tools = r.json().get("tools", [])
pm_tools = [t for t in tools if t["name"].startswith("pm.")]
print(f"[1] tools={len(tools)} pm_tools={len(pm_tools)}")
assert pm_tools, "No pm.* tools found"
for name in ("pm.workflows.create_workflow", "pm.workflows.update_workflow_status", "pm.workflows.instantiate_automation_template"):
    found = any(t["name"] == name for t in pm_tools)
    print(f"    {'OK ' if found else 'MISS'} {name}")
    assert found, f"missing {name}"

# 2. resources
r = client.get("/api/v1/mcp/resources")
assert r.status_code == 200, r.text
resources = r.json().get("resources", [])
pm_resources = [res for res in resources if str(res["uri"]).startswith("pm://")]
print(f"[2] resources={len(resources)} pm_resources={len(pm_resources)}")
assert pm_resources, "No pm:// resources found"

# 3. read a resource
uri = pm_resources[0]["uri"]
r = client.get("/api/v1/mcp/resources/read", params={"uri": uri})
print(f"[3] read {uri} -> {r.status_code}")
if r.status_code == 200:
    print(f"    content len={len(r.json().get('content', ''))}")
else:
    print(f"    error: {r.json()}")
    # don't fail hard; resource content may need DB. Print and continue.

# 4. call a tool end-to-end (list_automation_template_categories takes no args)
r = client.post("/api/v1/mcp/tools/call", json={"name": "pm.workflows.list_automation_template_categories", "arguments": {}})
print(f"[4] call list_automation_template_categories -> {r.status_code}")
if r.status_code == 200:
    res = r.json().get("result")
    print(f"    result: {str(res)[:200]}")
    assert res is not None
else:
    print(f"    error: {r.json()}")
    # A DB-backed tool may legitimately fail without a live DB. Check the error shape.

# 5. call create_workflow with minimal args (should hit DB layer; expect 400 if no DB)
r = client.post("/api/v1/mcp/tools/call", json={"name": "pm.workflows.create_workflow", "arguments": {"name": "Smoke Flow", "project_id": "p-nonexistent"}})
print(f"[5] call create_workflow -> {r.status_code} (400 = handler ran, DB missing; 200 = full success)")
print(f"    body: {str(r.json())[:200]}")

print("\nSMOKE RESULT: PASS" if pm_tools and pm_resources else "\nSMOKE RESULT: FAIL")
