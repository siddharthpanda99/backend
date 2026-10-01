"""Regression tests for ``app/modules/triggers/routes.py``.

The headline defect: ``POST /{id}/fire`` incremented ``fire_count`` and committed it
*before* calling ``TriggerManager.fire``. The dispatch then failed — the in-memory
manager still held a DRAFT copy, because ``create_trigger`` and ``transition_state``
write straight to the DB and never refresh the manager — so the row recorded a
completed fire for work that never happened, and the endpoint still answered HTTP 200
with a body containing ``"error"``.

Uses a throwaway SQLite file. Never touches the live Postgres.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def client(monkeypatch):
    db_path = tempfile.mktemp(suffix=".sqlite")
    engine = create_engine(f"sqlite:///{db_path}")

    import app.modules.triggers.routes as routes

    SQLModel.metadata.create_all(engine, tables=[routes.TriggerDB.__table__])

    # A fresh manager per test so no state leaks between them.
    import common_lib.modules.triggers.manager as manager_mod

    monkeypatch.setattr(manager_mod, "_global_manager", None, raising=False)

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    app.dependency_overrides[routes.get_session] = lambda: Session(engine)

    with TestClient(app) as c:
        yield c

    engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)


def _create(client, **overrides):
    body = {
        "name": "T",
        "trigger_type": "event",
        "target_type": "hook",
        "target_id": "hook-1",
    }
    body.update(overrides)
    resp = client.post("/api/v1/triggers", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_fire_returns_200_with_a_dispatch_result(client):
    """The happy path still works end to end."""
    tid = _create(client)
    resp = client.put(f"/api/v1/triggers/{tid}/state", json={"state": "active"})
    assert resp.status_code == 200

    resp = client.post(f"/api/v1/triggers/{tid}/fire")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "error" not in body, body
    assert body["trigger_id"] == str(tid)


def test_fire_does_not_count_a_dispatch_that_never_happened(client):
    """A fire that did not reach its target must not bump fire_count.

    Before: `t.fire_count += 1; session.commit()` ran before dispatch, so a failed
    fire still left the count incremented.
    """
    tid = _create(client)
    # Deliberately do NOT activate: the trigger is a DRAFT and cannot fire.
    resp = client.post(f"/api/v1/triggers/{tid}/fire")

    assert resp.status_code == 409, resp.text
    # HTTPException.detail carries the message, not an error envelope.
    assert "cannot fire" in resp.json()["detail"], resp.json()

    row = client.get(f"/api/v1/triggers/{tid}").json()
    assert row["fire_count"] == 0, f"failed fire was counted: {row}"
    assert row["last_fired_at"] is None, f"failed fire was timestamped: {row}"


def test_fire_reports_failure_instead_of_a_bare_200(client):
    """A failed fire must not answer 200 with an error buried in the body."""
    tid = _create(client)
    resp = client.post(f"/api/v1/triggers/{tid}/fire")
    assert resp.status_code != 200, (
        f"a fire that could not run must not return 200; body was {resp.text}"
    )


def test_fire_respects_the_disabled_flag(client):
    """`enabled=False` is a hard stop."""
    tid = _create(client)
    client.put(f"/api/v1/triggers/{tid}/state", json={"state": "active"})
    client.put(f"/api/v1/triggers/{tid}", json={"enabled": False})

    resp = client.post(f"/api/v1/triggers/{tid}/fire")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Trigger is disabled"


def test_fire_unknown_trigger_is_404(client):
    assert client.post("/api/v1/triggers/999999/fire").status_code == 404


def test_state_endpoint_is_visible_to_the_manager(client):
    """Activating a trigger must leave the manager able to fire it.

    Before: the endpoint wrote `state` to the row only, so the manager's copy stayed
    DRAFT and every subsequent fire failed with "Trigger not found or cannot fire".
    """
    tid = _create(client)

    from common_lib.modules.triggers.manager import get_trigger_manager

    assert get_trigger_manager().get(str(tid)).state.value == "draft"

    assert client.put(
        f"/api/v1/triggers/{tid}/state", json={"state": "active"}
    ).status_code == 200

    in_memory = get_trigger_manager().get(str(tid))
    assert in_memory.state.value == "active", (
        f"manager still holds {in_memory.state}; the fire endpoint would fail"
    )
    assert in_memory.can_fire() is True


def test_fire_counts_exactly_once_per_successful_fire(client):
    """fire_count must match the number of fires that actually dispatched."""
    tid = _create(client)
    client.put(f"/api/v1/triggers/{tid}/state", json={"state": "active"})

    successes = 0
    for _ in range(3):
        if client.post(f"/api/v1/triggers/{tid}/fire").status_code == 200:
            successes += 1

    assert successes > 0, "no fire succeeded — the test would be vacuous"

    row = client.get(f"/api/v1/triggers/{tid}").json()
    assert row["fire_count"] == successes, (
        f"fire_count={row['fire_count']} but {successes} fires succeeded"
    )
    # last_fired_at must be stamped by a successful fire.
    assert row["last_fired_at"] is not None


def test_delete_unregisters_from_the_manager(client):
    """Deleting a trigger removes it from the manager too."""
    tid = _create(client)
    client.put(f"/api/v1/triggers/{tid}/state", json={"state": "active"})

    from common_lib.modules.triggers.manager import get_trigger_manager

    assert get_trigger_manager().get(str(tid)) is not None

    assert client.delete(f"/api/v1/triggers/{tid}").status_code == 200
    assert get_trigger_manager().get(str(tid)) is None


def test_update_trigger_rejects_unknown_state(client):
    tid = _create(client)
    resp = client.put(f"/api/v1/triggers/{tid}/state", json={"state": "bogus"})
    assert resp.status_code == 400
    assert "bogus" in resp.json()["detail"]
