"""API smoke test for agentic-pipelines routes (list + run + get + artifacts)."""
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.agentic_pipelines.routes import router

app = FastAPI()
app.include_router(router, prefix="/api/v1/agentic-pipelines")
client = TestClient(app)

# 1. List pipelines (definitions synced to nexus_db)
r = client.get("/api/v1/agentic-pipelines")
print("list:", r.status_code, "count:", len(r.json()))

# 1b. The new internet_research definition must be present
defs = r.json() if r.status_code == 200 else []
slugs = [d.get("slug") for d in defs]
print("internet_research present:", "internet_research" in slugs)

# 2. Stub run (deterministic, no LLM) to verify API CRUD + persistence round-trip
r = client.post(
    "/api/v1/agentic-pipelines/runs",
    json={
        "pipeline_slug": "internet_research",
        "input": "What is trending in SOTA image models on reddit?",
        "use_llm": False,
        "export_formats": ["txt", "json", "yaml", "markdown"],
    },
)
print("run:", r.status_code)
if r.status_code == 200:
    body = r.json()
    print("  status:", body.get("status"))
    run_id = body.get("id")
    artifacts = body.get("artifacts") or []
    print("  artifacts:", [(a.get("format"), a.get("filename")) for a in artifacts])
    print("  txt artifact present:", any(a.get("format") == "txt" for a in artifacts))

    # 3. Get the run back
    rg = client.get(f"/api/v1/agentic-pipelines/runs/{run_id}")
    print("get run:", rg.status_code, "status:", rg.json().get("status") if rg.status_code == 200 else rg.text[:160])

    # 4. List runs (was shadowed by GET /{pipeline_id} before the fix)
    rl = client.get("/api/v1/agentic-pipelines/runs")
    print("list runs:", rl.status_code, "count:", len(rl.json()) if rl.status_code == 200 else rl.text[:160])

    # 5. Export round-trip via the real POST endpoint
    rx = client.post(f"/api/v1/agentic-pipelines/runs/{run_id}/export", json={"formats": ["txt", "json"]})
    print("post export:", rx.status_code)
    if rx.status_code == 200:
        arts = rx.json().get("artifacts", [])
        print("  exported:", [(a.get("format"), a.get("size_bytes")) for a in arts])

    # 6. Requirements list (was also shadowed before the fix)
    rq = client.get("/api/v1/agentic-pipelines/requirements")
    print("list requirements:", rq.status_code, "count:", len(rq.json()) if rq.status_code == 200 else rq.text[:160])
else:
    print("  body:", r.text[:200])
