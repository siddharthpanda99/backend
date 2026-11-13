"""Character Studio metrics smoke test — /metrics exposes job metrics.

Boots the real FastAPI app with throwaway sqlite files and asserts that
GET /metrics is reachable and renders the Character Studio Prometheus
metric family registered in ``observability/prometheus_registry.py``.

This is the wiring check for SQ.2: the metrics are registered in the
default ``prometheus_client.REGISTRY`` and served via
``prometheus_fastapi_instrumentator`` (which defaults to REGISTRY).

Not GPU-dependent; generation is not executed here.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="char_studio_metrics_"))
os.environ["CHARACTER_STUDIO_DB_URL"] = f"sqlite:///{_TEST_ROOT}/character_studio.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT}/platform_app.db"
os.environ["NEXUS_SKIP_STARTUP_SEEDING"] = "1"
os.environ["NEXUS_BG_DELAY_SECONDS"] = "0"

API = "/api/v1/character-studio"


def _wait_for_deferred_mount(client, timeout_s: float = 300.0) -> None:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            resp = client.get("/readyz-deep")
            last = (resp.status_code, resp.text[:200])
            if (
                resp.status_code == 200
                and resp.json().get("deferred_routers_mounted") is True
            ):
                return
        except Exception as exc:  # noqa: BLE001
            last = ("exception", str(exc))
        time.sleep(1.0)
    pytest.fail(f"deferred routers not mounted in {timeout_s}s; last: {last}")


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        _wait_for_deferred_mount(c, timeout_s=300.0)
        yield c


def test_metrics_endpoint_renders_character_studio_metrics(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200, (
        f"/metrics returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.text
    for family in (
        "character_studio_jobs_total",
        "character_studio_job_duration_seconds",
        "character_studio_jobs_active",
        "character_studio_evaluations_total",
        "character_studio_approvals_total",
    ):
        assert family in body, f"/metrics missing metric family {family!r}"


def test_character_studio_job_created_metric_increments(client):
    resp = client.post(
        f"{API}/characters",
        json={
            "character_id": "metrics_smoke_char",
            "name": "Metrics Smoke",
            "description": "SQ.2 smoke test character",
        },
    )
    assert resp.status_code in (200, 201), (
        f"create failed: {resp.status_code} {resp.text}"
    )

    resp = client.post(
        f"{API}/characters/metrics_smoke_char/generate",
        json={
            "intent": "metrics_smoke",
            "provider": "sd15",
            "steps": 1,
            "cfg": 1.0,
            "seed": 42,
        },
    )
    assert resp.status_code in (200, 201, 202), (
        f"generate failed: {resp.status_code} {resp.text}"
    )

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert (
        'character_studio_jobs_total{intent="metrics_smoke",provider="sd15",status="queued"}'
        in resp.text
    )
