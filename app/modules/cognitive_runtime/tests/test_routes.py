"""Regression tests for the cognitive_runtime transport routers.

Each test here is proven able to fail: see MODULE-AUDIT-cognitive_runtime.md
("Fixes applied") for the recorded red output.

* F1 — the router must NOT double the "/cognitive" prefix. FastAPI
  concatenates the router's own prefix with the one app/core/routers.py
  supplies, so a prefix here yields /api/v1/cognitive/cognitive/...
* F2 — the routers must share ONE CognitiveRuntime, otherwise the run store
  that POST /cognitive/execute writes is not the one GET /cognitive/runs reads
  and the lookup 404s for a run created moments earlier.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.cognitive_runtime.routes import execute as execute_routes
from app.modules.cognitive_runtime.routes import infer as infer_routes
from app.modules.cognitive_runtime.routes import plan as plan_routes
from app.modules.cognitive_runtime.routes import runs as runs_routes
from app.modules.cognitive_runtime.routes import router as cogr_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(cogr_router, prefix="/api/v1/cognitive")
    return TestClient(app)


class TestPrefixIsNotDoubled:
    def test_no_route_path_contains_cognitive_twice(self) -> None:
        offenders = [
            r.path
            for r in cogr_router.routes
            if hasattr(r, "path") and r.path.count("cognitive") > 1
        ]
        assert offenders == [], f"doubled /cognitive prefix on: {offenders}"

    def test_documented_path_is_reachable(self) -> None:
        client = _client()
        resp = client.post(
            "/api/v1/cognitive/infer",
            json={"capability": "classify", "context": {"user_intent": "hi"}},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["capability"] == "classify"


class TestRuntimesAreShared:
    def test_all_route_modules_use_one_runtime_instance(self) -> None:
        assert infer_routes._runtime is execute_routes._runtime
        assert plan_routes._runtime is execute_routes._runtime
        assert runs_routes._runtime is execute_routes._runtime


class TestRunLookupRoundTrip:
    def test_run_created_by_execute_is_readable(self) -> None:
        client = _client()
        created = client.post(
            "/api/v1/cognitive/execute",
            json={
                "plan": {
                    "plan_id": "p1",
                    "goal": "g",
                    "status": "ready",
                    "steps": [{"id": "s1", "capability": "classify"}],
                }
            },
        )
        assert created.status_code == 200, created.text
        run_id = created.json()["run_id"]

        fetched = client.get(f"/api/v1/cognitive/runs/{run_id}")
        assert fetched.status_code == 200, f"run {run_id} not found: {fetched.text}"
        assert fetched.json()["run_id"] == run_id

        traced = client.get(f"/api/v1/cognitive/runs/{run_id}/trace")
        assert traced.status_code == 200, traced.text
        assert "s1" in traced.json()["steps"]

    def test_unknown_run_still_404s(self) -> None:
        client = _client()
        assert (
            client.get("/api/v1/cognitive/runs/run-does-not-exist").status_code == 404
        )
