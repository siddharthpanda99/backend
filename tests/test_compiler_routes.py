"""Nexus Cluster 1 compiler routes — endpoint tests (chunk KC-023).

Mounts the compiler router standalone (no full-app import, no auth) and
covers: flag gating (503 when OFF), compile dispatch, job fetch (200 +
404), and incremental compilation.

Run: cd "Backend Monorepo/Backend" && uv run pytest tests/test_compiler_routes.py -v
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.knowledge_engine.compiler.routes.router import router
from common_lib.modules.integration.ports.rip_port import (
    get_rip_feature_flag_api,
)
from common_lib.modules.knowledge_engine.compiler import worker as worker_mod

app = FastAPI()
app.include_router(router)
client = TestClient(app)

ALL_FLAGS = (
    "KNOWLEDGE_COMPILER_ENABLED",
    "COMPILER_INCREMENTAL_UPDATES_ENABLED",
    "COMPILER_DUAL_REPRESENTATION_ENABLED",
)


@pytest.fixture(autouse=True)
def _clean_state():
    api = get_rip_feature_flag_api()
    assert api is not None
    api["clear_all_overrides"]()
    worker_mod.clear_compilation_jobs()
    yield
    api["clear_all_overrides"]()
    worker_mod.clear_compilation_jobs()


def _enable_all():
    api = get_rip_feature_flag_api()
    assert api is not None
    for name in ALL_FLAGS:
        api["set_flag_override"](name, True)


class TestFlagGating:
    def test_compile_503_when_off(self):
        resp = client.post("/compiler/compile", json={"source_id": "s1", "text": "hi"})
        assert resp.status_code == 503

    def test_incremental_503_when_off(self):
        resp = client.post("/compiler/compile-incremental", json={"doc_id": "d1"})
        assert resp.status_code == 503


class TestCompile:
    def test_dispatch_and_fetch(self):
        _enable_all()
        resp = client.post(
            "/compiler/compile",
            json={
                "source_id": "s1",
                "text": "# Hello\n\nBody here.",
                "mime": "text/markdown",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "DONE"
        job_id = resp.json()["job_id"]
        fetched = client.get(f"/compiler/jobs/{job_id}")
        assert fetched.status_code == 200
        assert fetched.json()["job"]["job_id"] == job_id

    def test_job_404(self):
        _enable_all()
        resp = client.get("/compiler/jobs/does-not-exist")
        assert resp.status_code == 404


class TestIncremental:
    def test_delta_then_recompile(self):
        _enable_all()
        first = client.post(
            "/compiler/compile-incremental",
            json={
                "doc_id": "d1",
                "text": "# Acme\n\nAcme sells widgets.",
                "prior_graph": {"entities": [], "relations": []},
            },
        )
        assert first.json()["delta"]["status"] == "NEW"
        second = client.post(
            "/compiler/compile-incremental",
            json={
                "doc_id": "d1",
                "text": "# Acme\n\nAcme sells gadgets.",
                "prior_graph": {"entities": [], "relations": []},
            },
        )
        data = second.json()
        assert data["delta"]["status"] == "MODIFIED"
        assert data["recompiled_sections"] == ["Acme"]
