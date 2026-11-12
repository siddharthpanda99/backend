"""Character Studio REST smoke test — NO generation run (too slow).

Covered: create character → fetch it → list (empty) references → queue a
job (provider NOT executed) → cancel it. Exercises the full transport path
through the common_lib operations layer against a throwaway sqlite DB.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHARACTER_ID = "smoke-char-001"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "character_studio_smoke.db"
    monkeypatch.setenv("CHARACTER_STUDIO_DB_URL", f"sqlite:///{db}")

    from common_lib.modules.image_processing.character_studio import operations

    if hasattr(operations, "init_db"):
        operations.init_db()
    else:
        # init_db() not exposed yet — create the schema directly from the
        # SQLModel metadata (same DDL A2's init path would emit).
        from sqlmodel import SQLModel, create_engine

        from common_lib.modules.image_processing.character_studio import models

        engine = create_engine(f"sqlite:///{db}")
        SQLModel.metadata.create_all(engine)

    from app.modules.character_studio.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/character-studio")
    return TestClient(app, raise_server_exceptions=False)


def test_character_studio_smoke(client):
    # 1. Create a character
    resp = client.post(
        "/character-studio/characters",
        json={
            "character_id": CHARACTER_ID,
            "name": "Smoke Hero",
            "description": "smoke",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["character_id"] == CHARACTER_ID

    # 2. Fetch it
    resp = client.get(f"/character-studio/characters/{CHARACTER_ID}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Smoke Hero"

    # 3. List references — must be empty
    resp = client.get(f"/character-studio/characters/{CHARACTER_ID}/references")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"items": [], "total": 0}

    # 4. Queue a generation job — provider must NOT be run by this test
    resp = client.post(
        f"/character-studio/characters/{CHARACTER_ID}/generate",
        json={"intent": "smoke_test", "provider": "sd15"},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    job_id = body["job_id"]

    # 5. Cancel the queued job
    resp = client.post(f"/character-studio/generation-jobs/{job_id}/cancel")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
