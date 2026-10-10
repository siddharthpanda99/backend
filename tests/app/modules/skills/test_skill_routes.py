"""Route tests for the skill lifecycle (NEX-P5-001).

Thin-route gate (G9): mutations 404 while ``skills.lifecycle.enabled`` is
OFF; the flags endpoint stays ungated. Logic itself is covered in
common_lib (``modules/skills/tests/test_skill_lifecycle.py``); these tests
only pin the HTTP contract.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.skills.routes import router as skills_router

FLAG = "skills.lifecycle.enabled"


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(skills_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _restore_flag():
    from common_lib.modules.skills.flags import is_enabled, set_flag

    prev = is_enabled(FLAG)
    yield
    set_flag(FLAG, prev)


def test_mutations_404_when_flag_off(client):
    from common_lib.modules.skills.flags import set_flag

    set_flag(FLAG, False)
    body = {
        "version": "1.0.0",
        "owner": "t",
        "input_schema_ref": "schema://d/in",
        "output_schema_ref": "schema://d/out",
        "allowed_capabilities": ["d.run"],
    }
    assert client.post("/skills/demo/versions", json=body).status_code == 404
    assert client.post("/skills/demo/publish", json={"version": "1.0.0"}).status_code == 404
    assert client.post("/skills/demo/deprecate").status_code == 404
    assert client.post("/skills/demo/versions/1.0.0/evaluate", json={"pass_rate": 1.0}).status_code == 404


def test_flags_endpoint_ungated(client):
    from common_lib.modules.skills.flags import set_flag

    set_flag(FLAG, False)
    resp = client.get("/skills/lifecycle/flags")
    assert resp.status_code == 200
    assert resp.json() == {"flags": {FLAG: False}}
