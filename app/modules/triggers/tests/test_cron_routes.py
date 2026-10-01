"""HTTP tests for the durable cron routes.

The point of these is the *status codes*. The defect being fixed was a surface
that reported success unconditionally, so the assertions that matter are the
ones that must **not** return 200: a disabled flag, an unresolvable target, a
missing schedule.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from sqlmodel import Session, create_engine

from app.modules.triggers import cron_routes
from common_lib.modules.triggers.cron.models import (
    CronFireHistory,
    CronSchedule,
    utcnow,
)
from common_lib.modules.triggers.cron.service import CronService
from common_lib.modules.triggers.cron.targets import (
    ResolvedTarget,
    UnresolvedTarget,
    set_override_resolver,
)


@pytest.fixture
def db(tmp_path):
    eng = create_engine(
        f"sqlite:///{tmp_path / 'routes.db'}",
        connect_args={"check_same_thread": False},
    )
    CronSchedule.__table__.create(eng)
    CronFireHistory.__table__.create(eng)
    return eng


@pytest.fixture
def client(db, monkeypatch):
    """A TestClient over the cron router with a real SQLite database.

    The session is swapped via FastAPI's ``dependency_overrides``, keyed on the
    *original* ``get_session`` callable. Monkeypatching the module attribute
    would not work: each route captured ``Depends(get_session)`` at decoration
    time, so a later rebinding is invisible and the handlers would quietly fall
    through to the platform engine — writing to the live database, which is
    exactly what these tests must never do.
    """
    monkeypatch.setattr(
        cron_routes, "CronService", lambda: CronService(worker_id="route-test")
    )

    def override_session():
        with Session(db) as s:
            yield s

    app = FastAPI()
    app.dependency_overrides[cron_routes.get_session] = override_session
    app.include_router(cron_routes.router)
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    monkeypatch.setenv("TRIGGERS_CRON_DURABLE_SCHEDULES", "1")
    monkeypatch.setenv("TRIGGERS_CRON_RESOLVE_TARGETS", "1")
    yield


@pytest.fixture
def registry():
    set_override_resolver(
        lambda t, i: (
            ResolvedTarget(t, i, callable=lambda **k: {"ok": True})
            if i == "known"
            else UnresolvedTarget(t, i, f"no such {i!r}")
        )
    )
    yield
    set_override_resolver(None)


def body(expression="0 9 * * mon-fri", target="known"):
    return {
        "cron_expression": expression,
        "target_id": target,
        "target_type": "node",
        "timezone": "UTC",
        "name": "morning",
    }


# ── flag gate ───────────────────────────────────────────────────────


def test_mutating_endpoints_refuse_while_the_flag_is_off(client, registry, monkeypatch):
    """A 200 while the flag is off would be a lie about persistence."""
    monkeypatch.delenv("TRIGGERS_CRON_DURABLE_SCHEDULES")
    assert client.post("/triggers/cron", json=body()).status_code == 503
    assert client.get("/triggers/cron").status_code == 503


def test_validate_works_even_while_the_flag_is_off(client, registry, monkeypatch):
    """Checking an expression writes nothing, so it needs no flag."""
    monkeypatch.delenv("TRIGGERS_CRON_DURABLE_SCHEDULES")
    response = client.post(
        "/triggers/cron/validate", json={"cron_expression": "0 9 * * *"}
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert len(response.json()["upcoming"]) == 5


# ── create ──────────────────────────────────────────────────────────


def test_create_returns_201_and_persists(client, registry, db):
    response = client.post("/triggers/cron", json=body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    assert payload["target_resolved"] is True
    with Session(db) as s:
        assert CronService().get_schedule(s, payload["schedule"]["id"]) is not None


def test_unresolvable_target_is_422_and_writes_nothing(client, registry, db):
    response = client.post("/triggers/cron", json=body(target="ghost"))
    assert response.status_code == 422
    assert "ghost" in response.json()["detail"]
    with Session(db) as s:
        assert CronService().list_schedules(s) == []


def test_invalid_cron_is_422(client, registry):
    response = client.post("/triggers/cron", json=body(expression="0 0 31 2 *"))
    assert response.status_code == 422
    assert "can never fire" in response.json()["detail"]


def test_validate_rejects_a_bad_expression_with_422(client, registry):
    response = client.post(
        "/triggers/cron/validate", json={"cron_expression": "99 * * * *"}
    )
    assert response.status_code == 422


# ── read ────────────────────────────────────────────────────────────


def test_list_and_get(client, registry):
    created = client.post("/triggers/cron", json=body()).json()
    sid = created["schedule"]["id"]

    listing = client.get("/triggers/cron").json()
    assert listing["count"] == 1
    assert listing["schedules"][0]["id"] == sid

    one = client.get(f"/triggers/cron/{sid}").json()
    assert one["cron_expression"] == "0 9 * * mon-fri"


def test_get_missing_is_404(client, registry):
    assert client.get("/triggers/cron/nope").status_code == 404


def test_preview_does_not_mutate(client, registry):
    created = client.post("/triggers/cron", json=body()).json()
    sid = created["schedule"]["id"]
    before = client.get(f"/triggers/cron/{sid}").json()["next_run_at"]

    preview = client.get(f"/triggers/cron/{sid}/preview?count=3").json()
    assert len(preview["upcoming"]) == 3
    assert client.get(f"/triggers/cron/{sid}").json()["next_run_at"] == before


def test_preview_of_missing_is_404(client, registry):
    assert client.get("/triggers/cron/nope/preview").status_code == 404


# ── update / runbook ────────────────────────────────────────────────


def test_patch_disables_without_deleting_and_history_survives(client, registry, db):
    created = client.post("/triggers/cron", json=body()).json()
    sid = created["schedule"]["id"]

    patched = client.patch(f"/triggers/cron/{sid}", json={"enabled": False})
    assert patched.status_code == 200
    assert patched.json()["status"] == "disabled"

    assert client.get(f"/triggers/cron/{sid}").status_code == 200
    with Session(db) as s:
        assert CronService().get_schedule(s, sid).enabled is False


def test_run_now_fires_and_is_recorded_as_manual(client, registry, db):
    created = client.post("/triggers/cron", json=body()).json()
    sid = created["schedule"]["id"]

    ran = client.post(f"/triggers/cron/{sid}/run").json()
    assert ran["outcome"] == "success"

    history = client.get(f"/triggers/cron/{sid}/history").json()
    assert history["count"] == 1
    assert history["history"][0]["manual"] is True
    assert history["history"][0]["outcome"] == "success"


def test_run_now_on_missing_is_404(client, registry):
    assert client.post("/triggers/cron/nope/run").status_code == 404


def test_history_of_missing_is_404(client, registry):
    assert client.get("/triggers/cron/nope/history").status_code == 404


def test_delete_removes_the_schedule(client, registry):
    sid = client.post("/triggers/cron", json=body()).json()["schedule"]["id"]
    assert client.delete(f"/triggers/cron/{sid}").status_code == 200
    assert client.get(f"/triggers/cron/{sid}").status_code == 404


def test_delete_missing_is_404(client, registry):
    assert client.delete("/triggers/cron/nope").status_code == 404


# ── engine status ───────────────────────────────────────────────────


def test_engine_status_reports_flag_state(client, registry):
    payload = client.get("/triggers/cron/-/engine").json()
    assert payload["durable_schedules_enabled"] is True
    assert payload["resolve_targets_enabled"] is True
    assert "running" in payload


def test_unresolved_target_history_is_visible_over_http(
    client, registry, db, monkeypatch
):
    """The honesty path, end to end: a row created without resolution still
    reports the failure when fired, over HTTP."""
    monkeypatch.delenv("TRIGGERS_CRON_RESOLVE_TARGETS")
    sid = client.post("/triggers/cron", json=body(target="ghost")).json()["schedule"][
        "id"
    ]
    assert (
        client.post(f"/triggers/cron/{sid}/run").json()["outcome"]
        == "target_unresolved"
    )
    history = client.get(f"/triggers/cron/{sid}/history").json()
    assert history["history"][0]["outcome"] == "target_unresolved"
    assert "ghost" in history["history"][0]["error"]
