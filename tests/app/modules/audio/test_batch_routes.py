"""Tests for batch routes (C078)."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _flag_on():
    from common_lib.modules.audio_processing.memory.feature_flags import (
        BATCH_ENABLED,
        set_flag_override,
        clear_all_overrides,
    )

    set_flag_override(BATCH_ENABLED, True)
    yield
    clear_all_overrides()


def test_batch_submit(client):
    resp = client.post(
        "/api/v1/audio/batch/submit",
        json={"job_type": "tts_batch", "payload": {"texts": ["hello"]}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data


def test_batch_get_job(client):
    # Submit first
    submit_resp = client.post(
        "/api/v1/audio/batch/submit",
        json={"job_type": "test", "payload": {}},
    )
    job_id = submit_resp.json()["job_id"]

    # Get job
    resp = client.get(f"/api/v1/audio/batch/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("pending", "running", "completed", "failed", "cancelled")


def test_batch_cancel(client):
    submit_resp = client.post(
        "/api/v1/audio/batch/submit",
        json={"job_type": "test", "payload": {}},
    )
    job_id = submit_resp.json()["job_id"]

    resp = client.post(f"/api/v1/audio/batch/{job_id}/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cancelled"] is True

    # Cancel again should fail
    resp2 = client.post(f"/api/v1/audio/batch/{job_id}/cancel")
    assert resp2.status_code == 409


def test_batch_list_jobs(client):
    client.post("/api/v1/audio/batch/submit", json={"job_type": "a", "payload": {}})
    client.post("/api/v1/audio/batch/submit", json={"job_type": "b", "payload": {}})

    resp = client.get("/api/v1/audio/batch/")
    assert resp.status_code == 200
    data = resp.json()
    assert "jobs" in data
    assert "total" in data
    assert data["total"] >= 2


def test_batch_generation_history(client):
    client.post(
        "/api/v1/audio/batch/submit", json={"job_type": "tts_batch", "payload": {}}
    )
    client.post("/api/v1/audio/batch/submit", json={"job_type": "other", "payload": {}})

    resp = client.get("/api/v1/audio/batch/history/generation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(j["job_type"] in ("tts_batch", "speak_batch") for j in data["jobs"])


def test_batch_flag_off(client):
    from common_lib.modules.audio_processing.memory.feature_flags import (
        clear_all_overrides,
    )

    clear_all_overrides()

    resp = client.post(
        "/api/v1/audio/batch/submit",
        json={"job_type": "test", "payload": {}},
    )
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
