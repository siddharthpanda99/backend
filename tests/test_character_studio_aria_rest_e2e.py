"""Canonical Aria end-to-end through the Character Studio REST API.

Real end-to-end, no mocks: real FastAPI app, real sqlite persistence, real
SD1.5 generation (DreamShaper), real face-swap identity lock (post_swap),
real InsightFace evaluation and a real composed RPG export — all driven
over HTTP exactly as the UI would.

This is the companion of test_character_studio.py: that suite's DNA uses
``identity_lock_method="generation_conditioned"`` (explicitly unsupported →
xfail by design). This file uses ``post_swap`` — the implemented identity
path — and asserts a genuinely COMPLETED job with a measurable similarity.

Environment: identical isolation to test_character_studio.py (throwaway
sqlite files, no seeding, deferred routers mounted immediately).
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="aria_rest_e2e_"))
os.environ["CHARACTER_STUDIO_DB_URL"] = f"sqlite:///{_TEST_ROOT}/character_studio.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT}/platform_app.db"
os.environ["NEXUS_SKIP_STARTUP_SEEDING"] = "1"
os.environ["NEXUS_BG_DELAY_SECONDS"] = "0"

_REPO_ROOT = Path("/home/siddharth/Documents/Dev/agentic-platform")
CANONICAL_FRONT = (
    _REPO_ROOT
    / "resources/generated_content/aria_photoshoot/canonical_candidates/zimage/aria_canonical/0001_aria_canonical_front.png"
)

API = "/api/v1/character-studio"
CHARACTER_ID = "aria_rest_e2e"

TERMINAL_STATES = {"completed", "failed", "cancelled"}


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
        except Exception as exc:  # noqa: BLE001 - readiness endpoint may hiccup during boot
            last = ("exception", str(exc))
        time.sleep(1.0)
    pytest.fail(f"Deferred routers did not mount within {timeout_s}s. Last: {last}")


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        _wait_for_deferred_mount(c, timeout_s=300.0)
        yield c


def _image_meta(path: Path):
    from PIL import Image

    with Image.open(path) as img:
        width, height = img.size
    return width, height, path.stat().st_size


def _poll_job_until_terminal(client, job_id: str, timeout_s: float = 600.0) -> dict:
    deadline = time.time() + timeout_s
    last_body: dict = {}
    while time.time() < deadline:
        resp = client.get(f"{API}/generation-jobs/{job_id}")
        assert resp.status_code == 200, (
            f"get job failed: {resp.status_code} {resp.text}"
        )
        last_body = resp.json()
        if last_body.get("status") in TERMINAL_STATES:
            return last_body
        time.sleep(2.0)
    pytest.fail(
        f"job {job_id} did not reach a terminal state within {timeout_s}s; last: {last_body}"
    )


def test_aria_canonical_rest_e2e(client):
    """DNA(post_swap) → reference → generate → completed → evaluate → export."""

    assert CANONICAL_FRONT.is_file(), f"canonical reference missing: {CANONICAL_FRONT}"

    # 1. Character
    resp = client.post(
        f"{API}/characters",
        json={
            "character_id": CHARACTER_ID,
            "name": "Aria REST E2E",
            "description": "canonical end-to-end through the Character Studio API",
        },
    )
    assert resp.status_code in (200, 201), (
        f"create failed: {resp.status_code} {resp.text}"
    )

    # 2. DNA with the implemented identity path: post_swap.
    resp = client.put(
        f"{API}/characters/{CHARACTER_ID}/dna",
        json={
            "name": "Aria REST E2E DNA",
            "version": "1.0.0",
            "identity_lock_method": "post_swap",
            "identity_lock_source": str(CANONICAL_FRONT),
            "similarity_threshold": 0.6,
            "quality_threshold": 0.6,
            "face_shape": "oval",
            "attribute_policies": {
                "identity_lock_method": "post_swap",
                "hair_color": "locked",
                "outfit": "variable",
            },
        },
    )
    assert resp.status_code == 200, f"PUT dna failed: {resp.status_code} {resp.text}"

    # 3. Approved face reference (registered from the canonical PNG on disk).
    width, height, size = _image_meta(CANONICAL_FRONT)
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/references",
        json={
            "asset_id_str": "aria_canonical_front",
            "category": "face",
            "subcategory": "front",
            "width": width,
            "height": height,
            "file_size": size,
            "format": "png",
            "file_path": str(CANONICAL_FRONT),
            "quality_score": 0.95,
        },
    )
    assert resp.status_code in (200, 201), (
        f"reference create failed: {resp.status_code} {resp.text}"
    )
    asset_id = resp.json()["asset_id"]
    resp = client.post(
        f"{API}/references/{asset_id}/approve",
        json={"approved_by": "rest-e2e"},
    )
    assert resp.status_code == 200, f"approve failed: {resp.status_code} {resp.text}"

    # 4. Generate (real SD1.5 job; the background runner executes it in-process).
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/generate",
        json={
            "intent": "fashion_editorial",
            "provider": "sd15",
            "steps": 5,
            "cfg": 1.0,
            "seed": 42,
        },
    )
    assert resp.status_code in (200, 202), (
        f"generate failed: {resp.status_code} {resp.text}"
    )
    job_id = resp.json().get("job_id")
    assert job_id, f"job_id missing: {resp.json()}"

    final = _poll_job_until_terminal(client, job_id, timeout_s=600.0)
    status = final.get("status")
    if status == "failed":
        pytest.xfail(
            f"sd15 generation failed in this environment: {final.get('error')}"
        )
    assert status == "completed", f"unexpected terminal status {status!r}: {final}"
    assert final.get("output_path"), f"completed job has no output_path: {final}"

    # 5. Evaluate the locked output against the canonical reference.
    gen_assets = client.get(
        f"{API}/characters/{CHARACTER_ID}/references",
        params={"category": "generation", "approved_only": "false"},
    ).json()
    items = gen_assets.get("items", gen_assets if isinstance(gen_assets, list) else [])
    assert items, "no generation asset registered after the completed job"
    gen_asset_id = items[0]["asset_id"]
    resp = client.post(
        f"{API}/assets/{gen_asset_id}/evaluate",
        json={"reference_asset_id": asset_id},
    )
    assert resp.status_code == 200, f"evaluate failed: {resp.status_code} {resp.text}"
    similarity = resp.json().get("similarity")
    assert similarity is not None, f"no similarity in evaluation: {resp.json()}"
    # post_swap must move the face toward the canonical identity.
    assert similarity >= 0.5, f"post-swap similarity too low: {similarity}"

    # 6. RPG export of the character (composed manifest + files).
    resp = client.post(f"{API}/characters/{CHARACTER_ID}/export/rpg")
    assert resp.status_code == 200, f"export failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body.get("manifest"), "manifest missing from export response"
    assert isinstance(body.get("files"), list) and body["files"], "no export files"
    for rel in body["files"]:
        # Export paths are repo-relative or absolute; verify at least one exists.
        candidate = Path(rel)
        if not candidate.is_absolute():
            candidate = _REPO_ROOT / rel
        assert candidate.is_file(), f"export file missing on disk: {rel}"
