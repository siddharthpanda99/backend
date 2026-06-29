"""Tests for playbook routes — CRUD, run execution, gates."""

import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import NullPool

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.models.playbook_models import (
    Playbook,
    PlaybookRun,
    PlaybookStepRun,
)
from common_lib.modules.agents.services.playbook_service import PlaybookService

_db_file = os.path.join(tempfile.gettempdir(), "test_playbook_api.db")
_test_engine = create_engine(
    f"sqlite:///{_db_file}",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)


def _override_get_session():
    with Session(_test_engine) as session:
        yield session


app = FastAPI()
from app.modules.agents.routes.playbook_routes import router as playbook_router

app.include_router(playbook_router, prefix="/playbooks")
app.dependency_overrides[get_db_session] = _override_get_session

client = TestClient(app)

_TABLES = [Playbook.__table__, PlaybookRun.__table__, PlaybookStepRun.__table__]

SIMPLE_YAML = """\
name: test_playbook
description: A test
steps:
  - name: step_a
  - name: step_b
    requires: [step_a]
"""

GATE_YAML = """\
name: gated
steps:
  - name: prepare
  - name: review
    gate: Approve
    requires: [prepare]
  - name: deploy
    requires: [review]
"""


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    SQLModel.metadata.create_all(_test_engine, tables=_TABLES)
    yield
    SQLModel.metadata.drop_all(_test_engine, tables=_TABLES)


class TestPlaybookCRUD:
    def test_list_empty(self):
        resp = client.get("/playbooks/")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_create(self):
        resp = client.post(
            "/playbooks/",
            json={"name": "test", "yaml_content": SIMPLE_YAML},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "test"

    def test_create_invalid_yaml(self):
        resp = client.post(
            "/playbooks/",
            json={"name": "bad", "yaml_content": "}{invalid"},
        )
        assert resp.status_code == 400

    def test_get(self):
        create = client.post(
            "/playbooks/",
            json={"name": "t", "yaml_content": SIMPLE_YAML},
        )
        pb_id = create.json()["data"]["id"]
        resp = client.get(f"/playbooks/{pb_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == pb_id

    def test_get_not_found(self):
        resp = client.get("/playbooks/nonexistent")
        assert resp.status_code == 404

    def test_delete(self):
        create = client.post(
            "/playbooks/",
            json={"name": "del", "yaml_content": SIMPLE_YAML},
        )
        pb_id = create.json()["data"]["id"]
        resp = client.delete(f"/playbooks/{pb_id}")
        assert resp.status_code == 200

    def test_delete_not_found(self):
        resp = client.delete("/playbooks/nonexistent")
        assert resp.status_code == 404


class TestPlaybookRuns:
    def _create_playbook(self):
        resp = client.post(
            "/playbooks/",
            json={"name": "r", "yaml_content": SIMPLE_YAML},
        )
        return resp.json()["data"]["id"]

    def test_start_run(self):
        pb_id = self._create_playbook()
        resp = client.post(
            "/playbooks/runs",
            json={"playbook_id": pb_id},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "running"

    def test_start_run_invalid(self):
        resp = client.post(
            "/playbooks/runs",
            json={"playbook_id": "nonexistent"},
        )
        assert resp.status_code == 400

    def test_get_run(self):
        pb_id = self._create_playbook()
        start = client.post(
            "/playbooks/runs",
            json={"playbook_id": pb_id},
        )
        run_id = start.json()["data"]["id"]
        resp = client.get(f"/playbooks/runs/{run_id}")
        assert resp.status_code == 200

    def test_get_run_not_found(self):
        resp = client.get("/playbooks/runs/nonexistent")
        assert resp.status_code == 404

    def test_get_steps(self):
        pb_id = self._create_playbook()
        start = client.post(
            "/playbooks/runs",
            json={"playbook_id": pb_id},
        )
        run_id = start.json()["data"]["id"]
        resp = client.get(f"/playbooks/runs/{run_id}/steps")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_advance(self):
        pb_id = self._create_playbook()
        start = client.post(
            "/playbooks/runs",
            json={"playbook_id": pb_id},
        )
        run_id = start.json()["data"]["id"]
        resp = client.post(f"/playbooks/runs/{run_id}/advance")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "completed"


class TestPlaybookGates:
    def _create_gated(self):
        resp = client.post(
            "/playbooks/",
            json={"name": "g", "yaml_content": GATE_YAML},
        )
        return resp.json()["data"]["id"]

    def test_gate_pauses(self):
        pb_id = self._create_gated()
        start = client.post(
            "/playbooks/runs",
            json={"playbook_id": pb_id},
        )
        run_id = start.json()["data"]["id"]
        client.post(f"/playbooks/runs/{run_id}/advance")
        resp = client.post(f"/playbooks/runs/{run_id}/advance")
        assert resp.json()["data"]["status"] == "gate_waiting"

    def test_gate_approve(self):
        pb_id = self._create_gated()
        start = client.post(
            "/playbooks/runs",
            json={"playbook_id": pb_id},
        )
        run_id = start.json()["data"]["id"]
        client.post(f"/playbooks/runs/{run_id}/advance")
        client.post(f"/playbooks/runs/{run_id}/advance")
        resp = client.post(
            f"/playbooks/runs/{run_id}/gate",
            json={"step_index": 1, "response": "OK", "approved": True},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "running"

    def test_gate_reject(self):
        pb_id = self._create_gated()
        start = client.post(
            "/playbooks/runs",
            json={"playbook_id": pb_id},
        )
        run_id = start.json()["data"]["id"]
        client.post(f"/playbooks/runs/{run_id}/advance")
        client.post(f"/playbooks/runs/{run_id}/advance")
        resp = client.post(
            f"/playbooks/runs/{run_id}/gate",
            json={"step_index": 1, "response": "No", "approved": False},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "failed"
