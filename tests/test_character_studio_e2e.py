"""Character Studio E2E — the approval gate, driven over HTTP.

Covers the human-review portion of the pipeline end-to-end with a real
FastAPI app, real sqlite persistence, and real InsightFace evaluation:

    create character → upload reference → evaluate → audit trail records
    decision → approve → audit trail confirms → reject round-trip →
    export (wardrobe) → audit events readable via API.

GPU-dependent generation is covered separately by
``test_character_studio_aria_rest_e2e.py``. This file deliberately avoids
SD1.5 so it can run as a fast regression gate.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="char_studio_e2e_"))
os.environ["CHARACTER_STUDIO_DB_URL"] = f"sqlite:///{_TEST_ROOT}/character_studio.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT}/platform_app.db"
os.environ["NEXUS_SKIP_STARTUP_SEEDING"] = "1"
os.environ["NEXUS_BG_DELAY_SECONDS"] = "0"

_REPO_ROOT = Path("/home/siddharth/Documents/Dev/agentic-platform")
REFERENCE_IMAGE = (
    _REPO_ROOT
    / "resources/generated_content/aria_photoshoot/canonical_candidates/zimage/aria_canonical/0001_aria_canonical_front.png"
)

API = "/api/v1/character-studio"
CHARACTER_ID = "char_e2e_review_gate"


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


@pytest.fixture(scope="session")
def e2e_character(client):
    resp = client.post(
        f"{API}/characters",
        json={
            "character_id": CHARACTER_ID,
            "name": "E2E Review Gate",
            "description": "Approval-gate end-to-end test character",
        },
    )
    assert resp.status_code in (200, 201), (
        f"create failed: {resp.status_code} {resp.text}"
    )
    return CHARACTER_ID


@pytest.fixture(scope="session")
def reference_asset_id(client, e2e_character):
    from PIL import Image

    with Image.open(REFERENCE_IMAGE) as img:
        width, height = img.size

    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/references",
        json={
            "asset_id_str": "e2e_review_gate_front",
            "category": "face",
            "subcategory": "front",
            "width": width,
            "height": height,
            "file_size": REFERENCE_IMAGE.stat().st_size,
            "format": "png",
            "file_path": str(REFERENCE_IMAGE),
            "quality_score": 0.95,
        },
    )
    assert resp.status_code in (200, 201), (
        f"reference create failed: {resp.status_code} {resp.text}"
    )
    return resp.json()["asset_id"]


def test_reference_fixture_exists():
    assert REFERENCE_IMAGE.is_file(), f"canonical fixture missing: {REFERENCE_IMAGE}"


def test_evaluate_reference_against_itself(client, reference_asset_id):
    """InsightFace evaluation runs for real and returns a similarity score."""
    resp = client.post(
        f"{API}/assets/{reference_asset_id}/evaluate",
        params={"reference_asset_id": reference_asset_id},
    )
    assert resp.status_code == 200, f"evaluate failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body.get("similarity") is not None, f"no similarity in response: {body}"
    assert body["similarity"] >= 0.5, f"self-similarity too low: {body['similarity']}"
    assert body.get("verdict"), f"no verdict: {body}"


def test_approve_then_audit_trail_records_decision(client, reference_asset_id):
    resp = client.post(
        f"{API}/assets/{reference_asset_id}/approve",
        json={"approved_by": "e2e-reviewer"},
    )
    assert resp.status_code == 200, f"approve failed: {resp.status_code} {resp.text}"
    assert resp.json().get("approval_status") in ("approved", "APPROVED")

    resp = client.get(
        f"{API}/characters/{CHARACTER_ID}/audit-events",
        params={"action": "approve", "actor": "e2e-reviewer"},
    )
    assert resp.status_code == 200, f"audit list failed: {resp.status_code} {resp.text}"
    body = resp.json()
    items = body.get("items", [])
    assert any(e.get("asset_id") == reference_asset_id for e in items), (
        f"approve not in audit trail: {items}"
    )


def test_reject_round_trip_and_audit(client, reference_asset_id):
    resp = client.post(
        f"{API}/assets/{reference_asset_id}/reject",
        json={"reason": "e2e reject round-trip"},
    )
    assert resp.status_code == 200, f"reject failed: {resp.status_code} {resp.text}"
    assert resp.json().get("approval_status") in ("rejected", "REJECTED")

    resp = client.get(
        f"{API}/characters/{CHARACTER_ID}/audit-events",
        params={"action": "reject"},
    )
    assert resp.status_code == 200, f"audit list failed: {resp.status_code} {resp.text}"
    items = resp.json().get("items", [])
    assert any(e.get("asset_id") == reference_asset_id for e in items), (
        f"reject not in audit trail: {items}"
    )

    # restore to approved so the export step has a sane state
    resp = client.post(
        f"{API}/assets/{reference_asset_id}/approve",
        json={"approved_by": "e2e-reviewer"},
    )
    assert resp.status_code == 200


def test_export_wardrobe_returns_manifest_and_files(client, e2e_character):
    resp = client.post(f"{API}/characters/{CHARACTER_ID}/export/wardrobe")
    assert resp.status_code == 200, f"export failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert "manifest" in body, f"manifest missing: {list(body)}"
    assert "files" in body, f"files missing: {list(body)}"
    assert body["manifest"]["character"]["character_id"] == CHARACTER_ID
    assert body["manifest"].get("export_kind") == "wardrobe"
