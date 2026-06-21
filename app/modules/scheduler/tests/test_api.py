"""API integration tests for scheduler endpoints.

Uses FastAPI TestClient to hit actual endpoints, not mock the service.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.modules.scheduler.routes import router as scheduler_router
from common_lib.modules.scheduler.service import (
    SchedulerService,
    get_scheduler_service,
    reset_scheduler_service,
)
from common_lib.modules.scheduler.store import JobStore
from common_lib.modules.scheduler.workflow_registry import register_workflow, _registry


@pytest.fixture(autouse=True)
def clear_registry():
    _registry.clear()
    yield
    _registry.clear()


@pytest.fixture(autouse=True)
def reset_service():
    reset_scheduler_service()
    yield
    reset_scheduler_service()


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield JobStore(Path(tmpdir) / "test_store.json")


@pytest.fixture
def mock_workflows():
    async def test_executor(inputs):
        await asyncio.sleep(0.01)
        return {"status": "ok", "inputs": inputs}

    async def failing_executor(inputs):
        raise ValueError("Workflow failed")

    register_workflow("test_workflow", test_executor)
    register_workflow("failing_workflow", failing_executor)


@pytest.fixture
def app(temp_store, mock_workflows):
    app = FastAPI()
    app.include_router(scheduler_router)

    service = SchedulerService(store=temp_store)
    global _scheduler_override
    _scheduler_override = service

    original = get_scheduler_service
    import common_lib.modules.scheduler.service as svc

    svc._scheduler = service

    yield app

    svc._scheduler = None


@pytest.fixture
def client(app):
    return TestClient(app)


class TestSchedulerAPI:
    def test_create_job(self, client):
        resp = client.post(
            "/scheduler/jobs",
            json={
                "name": "Test Job",
                "workflow_id": "test_workflow",
                "interval_minutes": 10,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["job"]["name"] == "Test Job"
        assert data["job"]["workflow_id"] == "test_workflow"

    def test_list_jobs(self, client):
        client.post(
            "/scheduler/jobs", json={"name": "A", "workflow_id": "test_workflow"}
        )
        client.post(
            "/scheduler/jobs", json={"name": "B", "workflow_id": "test_workflow"}
        )
        resp = client.get("/scheduler/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    def test_get_job(self, client):
        create = client.post(
            "/scheduler/jobs",
            json={
                "name": "Single",
                "workflow_id": "test_workflow",
            },
        )
        job_id = create.json()["job"]["id"]
        resp = client.get(f"/scheduler/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["job"]["name"] == "Single"

    def test_get_missing_job(self, client):
        resp = client.get("/scheduler/jobs/nonexistent")
        assert resp.status_code == 404

    def test_update_job(self, client):
        create = client.post(
            "/scheduler/jobs",
            json={
                "name": "Old",
                "workflow_id": "test_workflow",
            },
        )
        job_id = create.json()["job"]["id"]
        resp = client.put(
            f"/scheduler/jobs/{job_id}",
            json={
                "name": "New",
                "interval_minutes": 15,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["job"]["name"] == "New"
        assert resp.json()["job"]["interval_minutes"] == 15

    def test_delete_job(self, client):
        create = client.post(
            "/scheduler/jobs",
            json={
                "name": "ToDelete",
                "workflow_id": "test_workflow",
            },
        )
        job_id = create.json()["job"]["id"]
        resp = client.delete(f"/scheduler/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["message"] == f"Cron job '{job_id}' deleted"

    def test_enable_disable(self, client):
        create = client.post(
            "/scheduler/jobs",
            json={
                "name": "Toggle",
                "workflow_id": "test_workflow",
                "enabled": True,
            },
        )
        job_id = create.json()["job"]["id"]
        resp = client.post(f"/scheduler/jobs/{job_id}/disable")
        assert resp.status_code == 200
        assert resp.json()["job"]["enabled"] is False
        resp = client.post(f"/scheduler/jobs/{job_id}/enable")
        assert resp.status_code == 200
        assert resp.json()["job"]["enabled"] is True

    def test_pause_resume(self, client):
        create = client.post(
            "/scheduler/jobs",
            json={
                "name": "Pause",
                "workflow_id": "test_workflow",
            },
        )
        job_id = create.json()["job"]["id"]
        resp = client.post(f"/scheduler/jobs/{job_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["job"]["status"] == "paused"
        resp = client.post(f"/scheduler/jobs/{job_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["job"]["status"] == "active"

    def test_run_now(self, client):
        create = client.post(
            "/scheduler/jobs",
            json={
                "name": "RunMe",
                "workflow_id": "test_workflow",
                "workflow_inputs": {"key": "value"},
            },
        )
        job_id = create.json()["job"]["id"]
        resp = client.post(f"/scheduler/jobs/{job_id}/run")
        assert resp.status_code == 200
        assert resp.json()["result"]["success"] is True

    def test_run_now_failing(self, client):
        create = client.post(
            "/scheduler/jobs",
            json={
                "name": "FailMe",
                "workflow_id": "failing_workflow",
            },
        )
        job_id = create.json()["job"]["id"]
        resp = client.post(f"/scheduler/jobs/{job_id}/run")
        assert resp.status_code == 200
        assert resp.json()["result"]["success"] is False
        assert "Workflow failed" in resp.json()["result"]["error"]

    def test_stats(self, client):
        client.post(
            "/scheduler/jobs", json={"name": "A", "workflow_id": "test_workflow"}
        )
        client.post(
            "/scheduler/jobs", json={"name": "B", "workflow_id": "test_workflow"}
        )
        resp = client.get("/scheduler/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total_jobs"] == 2
        assert data["stats"]["active_jobs"] == 2

    def test_list_workflows(self, client):
        resp = client.get("/scheduler/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert "test_workflow" in data["workflows"]
        assert "sd_news_reddit" in data["templates"]

    def test_create_from_template(self, client):
        resp = client.post(
            "/scheduler/jobs/from-template",
            json={
                "template_id": "sd_news_reddit",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["job"]["name"] == "Reddit SD News"
        assert data["job"]["workflow_id"] == "sd_news_reddit"

    def test_create_from_missing_template(self, client):
        resp = client.post(
            "/scheduler/jobs/from-template",
            json={
                "template_id": "nonexistent",
            },
        )
        assert resp.status_code == 404

    def test_list_jobs_filter_status(self, client):
        client.post(
            "/scheduler/jobs", json={"name": "A", "workflow_id": "test_workflow"}
        )
        create_b = client.post(
            "/scheduler/jobs", json={"name": "B", "workflow_id": "test_workflow"}
        )
        job_b_id = create_b.json()["job"]["id"]
        client.post(f"/scheduler/jobs/{job_b_id}/pause")
        resp = client.get("/scheduler/jobs?status=paused")
        assert resp.json()["count"] == 1

    def test_list_jobs_filter_enabled(self, client):
        client.post(
            "/scheduler/jobs",
            json={"name": "A", "workflow_id": "test_workflow", "enabled": True},
        )
        client.post(
            "/scheduler/jobs",
            json={"name": "B", "workflow_id": "test_workflow", "enabled": False},
        )
        resp = client.get("/scheduler/jobs?enabled=false")
        assert resp.json()["count"] == 1
