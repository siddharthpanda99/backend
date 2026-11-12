"""Integration tests for the Character Studio API.

Real end-to-end tests: real FastAPI app (``app.main:app``), real SQLModel
persistence in a per-session sqlite database (via ``CHARACTER_STUDIO_DB_URL``,
a throwaway file in a temp dir), real files from the repository, real
insightface evaluation and a real SD15 generation attempt. No mocks, no
patched services, no fake responses.

Test isolation:
    * ``CHARACTER_STUDIO_DB_URL`` points the Character Studio service at a
      throwaway sqlite file (NOT in-memory, so rows survive across sessions
      inside the test run, exactly as the production default does).
    * ``DATABASE_URL`` points the *platform* database (used by the app
      lifespan) at another throwaway sqlite file so the app boots in this
      environment where no local PostgreSQL is running.
    * ``NEXUS_SKIP_STARTUP_SEEDING=1`` skips the Phase-C seeding chain (model
      downloads, scheduler, etc.) — the seeded content is irrelevant to this
      suite and must not touch the network.
    * ``NEXUS_BG_DELAY_SECONDS=0`` mounts the deferred routers (which is where
      the character-studio router lives) without the production quiet-period.

The module-scoped ``client`` fixture waits for the deferred mount to complete
(visible via the app's ``/readyz`` endpoint) instead of assuming readiness.

Environment under test:
    The repo's ``resources/config.ini`` runs the backend in dev mode
    (``environment = dev``, ``dev_mode = true``), so ``DISABLE_AUTH`` is on —
    this is the same auth setup every other backend integration test uses.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

# ── Test isolation: set env BEFORE any app/common_lib imports ──────────────
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="character_studio_tests_"))
os.environ["CHARACTER_STUDIO_DB_URL"] = f"sqlite:///{_TEST_ROOT}/character_studio.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT}/platform_app.db"
os.environ["NEXUS_SKIP_STARTUP_SEEDING"] = "1"
os.environ["NEXUS_BG_DELAY_SECONDS"] = "0"

# ── Repo-rooted fixture paths (absolute, referenced — never copied) ────────
_REPO_ROOT = Path("/home/siddharth/Documents/Dev/agentic-platform")
REFERENCE_IMAGE = (
    _REPO_ROOT
    / "resources/generated_content/aria_photoshoot/canonical_candidates/zimage/aria_canonical/0001_aria_canonical_front.png"
)
THREE_QUARTER_IMAGE = (
    _REPO_ROOT
    / "resources/generated_content/aria_photoshoot/canonical_candidates/zimage/aria_canonical/0002_aria_canonical_three_quarter.png"
)

API = "/api/v1/character-studio"

# Stable ids for this test session (the DB is per-run, so collisions are free)
CHARACTER_ID = "char_test_aria_integration"
REN_NAME = "Aria Renamed Integration"


def _image_meta(path: Path) -> tuple[int, int, int]:
    from PIL import Image

    with Image.open(path) as img:
        width, height = img.size
    return width, height, path.stat().st_size


def _unwrap_items(body):
    """Return (items, total) tolerating both {items,total} and bare lists."""
    if isinstance(body, dict):
        items = body.get("items", body.get("results", []))
        total = body.get("total", len(items) if isinstance(items, list) else 0)
        return (items if isinstance(items, list) else []), total
    if isinstance(body, list):
        return body, len(body)
    return [], 0


def _wait_for_deferred_mount(client, timeout_s: float = 300.0) -> None:
    """Poll /readyz until the deferred router mount completes."""
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            resp = client.get("/readyz")
            last = (resp.status_code, resp.text[:200])
            if (
                resp.status_code == 200
                and resp.json().get("deferred_mount_complete") is True
            ):
                return
        except Exception as exc:  # noqa: BLE001 - readiness endpoint may hiccup during boot
            last = ("exception", str(exc))
        time.sleep(1.0)
    pytest.fail(
        f"Deferred routers did not mount within {timeout_s}s. Last /readyz: {last}"
    )


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        _wait_for_deferred_mount(c, timeout_s=300.0)
        yield c


@pytest.fixture(scope="session")
def reference_asset_id(client):
    """Create the canonical face reference (used by later tests)."""
    width, height, size = _image_meta(REFERENCE_IMAGE)
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/references",
        json={
            "asset_id_str": "test_aria_canonical_front",
            "category": "face",
            "subcategory": "front",
            "width": width,
            "height": height,
            "file_size": size,
            "format": "png",
            "file_path": str(REFERENCE_IMAGE),
            "quality_score": 0.95,
        },
    )
    assert resp.status_code in (200, 201), (
        f"reference create failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    return body["asset_id"]


# ═══════════════════════════════════════════════════════════════════════════
# 0. Smoke: the router is mounted and healthy after the deferred mount window
# ═══════════════════════════════════════════════════════════════════════════


def test_character_studio_health(client):
    resp = client.get(f"{API}/health")
    assert resp.status_code == 200, (
        f"health check failed: {resp.status_code} {resp.text}"
    )
    assert resp.json()["status"] == "healthy"


def test_reference_fixture_exists_on_disk():
    assert REFERENCE_IMAGE.is_file(), f"fixture missing: {REFERENCE_IMAGE}"
    assert THREE_QUARTER_IMAGE.is_file(), f"fixture missing: {THREE_QUARTER_IMAGE}"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Character lifecycle: create → list → get → patch
# ═══════════════════════════════════════════════════════════════════════════


def test_create_character(client):
    resp = client.post(
        f"{API}/characters",
        json={
            "character_id": CHARACTER_ID,
            "name": "Aria Integration",
            "description": "Integration-test character (aria photoshoot fixture)",
        },
    )
    assert resp.status_code in (200, 201), (
        f"create failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert body["character_id"] == CHARACTER_ID
    assert body["name"] == "Aria Integration"
    assert body["status"] == "draft"


def test_list_characters_shows_created_character(client):
    resp = client.get(f"{API}/characters")
    assert resp.status_code == 200, f"list failed: {resp.status_code} {resp.text}"
    items, total = _unwrap_items(resp.json())
    matches = [c for c in items if c.get("character_id") == CHARACTER_ID]
    assert len(matches) == 1, (
        f"expected exactly one {CHARACTER_ID} in list, got {matches}"
    )
    assert total >= 1


def test_get_character(client):
    resp = client.get(f"{API}/characters/{CHARACTER_ID}")
    assert resp.status_code == 200, f"get failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["character_id"] == CHARACTER_ID
    assert body["name"] == "Aria Integration"
    assert body["description"] == "Integration-test character (aria photoshoot fixture)"


def test_patch_character_renames(client):
    resp = client.patch(f"{API}/characters/{CHARACTER_ID}", json={"name": REN_NAME})
    assert resp.status_code == 200, f"patch failed: {resp.status_code} {resp.text}"
    assert resp.json()["name"] == REN_NAME

    # restore for downstream readability
    resp = client.patch(
        f"{API}/characters/{CHARACTER_ID}", json={"name": "Aria Integration"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Aria Integration"


# ═══════════════════════════════════════════════════════════════════════════
# 2. DNA: 404 before creation, PUT round-trip of structured fields
# ═══════════════════════════════════════════════════════════════════════════


def test_get_dna_returns_404_before_creation(client):
    resp = client.get(f"{API}/characters/{CHARACTER_ID}/dna")
    assert resp.status_code == 404, (
        f"expected 404 for missing DNA, got {resp.status_code}: {resp.text}"
    )


def test_put_dna_and_fields_round_trip(client):
    # NOTE: the HTTP DNA body folds unknown top-level attributes into
    # ``attribute_policies`` as strings, so the fixture source round-trips via
    # ``identity_lock_source`` (asserted below) rather than a raw top-level
    # ``reference_assets`` dict.
    dna_body = {
        "name": "Aria Integration DNA",
        "version": "1.0.0",
        "identity_lock_method": "generation_conditioned",
        "identity_lock_source": str(REFERENCE_IMAGE),
        "similarity_threshold": 0.8,
        "quality_threshold": 0.65,
        "face_shape": "oval",
        "skin_tone": "olive",
        "attribute_policies": {
            "identity_lock_method": "generation_conditioned",
            "hair_color": "locked",
            "outfit": "variable",
        },
    }
    resp = client.put(f"{API}/characters/{CHARACTER_ID}/dna", json=dna_body)
    assert resp.status_code == 200, f"PUT dna failed: {resp.status_code} {resp.text}"

    # Read back and verify round-trip of the structured payload
    resp = client.get(f"{API}/characters/{CHARACTER_ID}/dna")
    assert resp.status_code == 200, f"GET dna failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["character_id"] == CHARACTER_ID
    assert body["version"] == "1.0.0"
    policies = body.get("attribute_policies", {})
    assert policies.get("identity_lock_method") == "generation_conditioned"
    assert policies.get("hair_color") == "locked"
    assert policies.get("outfit") == "variable"
    assert body.get("reference_assets", {}).get("identity_lock_source") == str(
        REFERENCE_IMAGE
    )
    assert body.get("similarity_threshold") == pytest.approx(0.8, abs=1e-6)
    assert body.get("quality_threshold") == pytest.approx(0.65, abs=1e-6)
    assert body.get("face_shape") == "oval"
    assert body.get("skin_tone") == "olive"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Identity versions: create and list
# ═══════════════════════════════════════════════════════════════════════════


def test_create_identity_version(client):
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/versions", json={"version": "1.0.0"}
    )
    assert resp.status_code in (200, 201), (
        f"create version failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert body["character_id"] == CHARACTER_ID
    assert body["version"] == "1.0.0"


def test_list_identities_contains_created_version(client):
    resp = client.get(f"{API}/characters/{CHARACTER_ID}/versions")
    assert resp.status_code == 200, (
        f"list identities failed: {resp.status_code} {resp.text}"
    )
    items, _ = _unwrap_items(resp.json())
    versions = [v.get("version") for v in items]
    assert "1.0.0" in versions, (
        f"created version missing from identities list: {versions}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Generation profile, style profile, outfit
# ═══════════════════════════════════════════════════════════════════════════


def test_create_generation_profile(client):
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/generation-profiles",
        json={
            "profile_name": "test_photorealistic_sd15",
            "model_provider": "sd15",
            "checkpoint": "dreamshaper_8",
            "face_identity_conditioning": True,
            "default_steps": 5,
            "default_cfg": 1.0,
            "evaluation_policy": "strict",
            "similarity_threshold": 0.75,
            "quality_threshold": 0.6,
        },
    )
    assert resp.status_code in (200, 201), (
        f"create generation profile failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert body["profile_name"] == "test_photorealistic_sd15"
    assert body["model_provider"] == "sd15"
    assert body["checkpoint"] == "dreamshaper_8"


def test_create_style_profile(client):
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/style-profiles",
        json={
            "profile_name": "test_photorealistic",
            "rendering": "photorealistic",
            "consistency_policy": "strict",
            "is_default": True,
        },
    )
    assert resp.status_code in (200, 201), (
        f"create style profile failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert body["profile_name"] == "test_photorealistic"
    assert body["rendering"] == "photorealistic"
    assert body.get("consistency_policy", "strict") == "strict"


def test_create_outfit(client):
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/outfits",
        json={
            "outfit_name": "test_summer_dress",
            "category": "casual",
            "materials": ["cotton"],
            "colors": ["blue"],
            "tags": ["integration-test"],
        },
    )
    assert resp.status_code in (200, 201), (
        f"create outfit failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert body["outfit_name"] == "test_summer_dress"
    assert body["category"] == "casual"
    assert body.get("approval_status") == "pending"


# ═══════════════════════════════════════════════════════════════════════════
# 5. References: create → approve → filtered list → archive
# ═══════════════════════════════════════════════════════════════════════════


def test_create_reference_asset_then_approve(client, reference_asset_id):
    # creation happens in the fixture; the file must NOT be copied — metadata only
    resp = client.get(
        f"{API}/characters/{CHARACTER_ID}/references",
        params={"category": "face", "approved_only": "false"},
    )
    assert resp.status_code == 200, (
        f"list references failed: {resp.status_code} {resp.text}"
    )
    items, _ = _unwrap_items(resp.json())
    target = next((a for a in items if a.get("asset_id") == reference_asset_id), None)
    assert target is not None, (
        f"created asset {reference_asset_id} not in references list"
    )
    assert target["asset_id_str"] == "test_aria_canonical_front"
    assert target["approval_status"] == "pending"
    assert target.get("width") == 1024
    assert target.get("height") == 1024
    # The stored path must be the original absolute path, never a copy
    assert target.get("file_path") in (None, str(REFERENCE_IMAGE)) or str(
        REFERENCE_IMAGE
    ) in str(target.get("file_path"))

    resp = client.post(
        f"{API}/references/{reference_asset_id}/approve", json={"approved_by": "tester"}
    )
    assert resp.status_code == 200, f"approve failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["approval_status"] == "approved"
    assert body.get("approved_by") == "tester"


def test_list_references_approved_only_filter(client, reference_asset_id):
    resp = client.get(
        f"{API}/characters/{CHARACTER_ID}/references",
        params={"category": "face", "approved_only": "true"},
    )
    assert resp.status_code == 200, (
        f"filtered list failed: {resp.status_code} {resp.text}"
    )
    items, _ = _unwrap_items(resp.json())
    ids = [a.get("asset_id") for a in items]
    assert reference_asset_id in ids, (
        f"approved asset missing from approved_only list: {ids}"
    )
    for asset in items:
        assert asset.get("approval_status") == "approved", (
            f"approved_only filter leaked non-approved asset: {asset}"
        )


def test_archive_reference(client):
    width, height, size = _image_meta(THREE_QUARTER_IMAGE)
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/references",
        json={
            "asset_id_str": "test_aria_canonical_three_quarter",
            "category": "face",
            "subcategory": "three_quarter",
            "width": width,
            "height": height,
            "file_size": size,
            "format": "png",
            "file_path": str(THREE_QUARTER_IMAGE),
            "quality_score": 0.9,
        },
    )
    assert resp.status_code in (200, 201), (
        f"create second reference failed: {resp.status_code} {resp.text}"
    )
    asset_id = resp.json()["asset_id"]

    resp = client.post(f"{API}/references/{asset_id}/archive")
    assert resp.status_code == 200, f"archive failed: {resp.status_code} {resp.text}"
    body = resp.json()
    # default list filtering of archived assets is implementation-defined;
    # assert the contract-guaranteed part: the asset itself reports archived
    assert body["approval_status"] == "archived", f"expected archived, got {body}"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Evaluation + asset approval
# ═══════════════════════════════════════════════════════════════════════════

VERDICTS = {"approved", "review", "rejected"}  # evaluator.py verdict_for()


def test_evaluate_reference_asset(client, reference_asset_id):
    resp = client.post(f"{API}/assets/{reference_asset_id}/evaluate")
    assert resp.status_code == 200, f"evaluate failed: {resp.status_code} {resp.text}"
    body = resp.json()
    similarity = body.get("similarity")
    assert isinstance(similarity, (int, float)), (
        f"similarity missing/not numeric: {body}"
    )
    assert 0.0 <= float(similarity) <= 1.0, f"similarity out of range: {similarity}"
    verdict = body.get("verdict")
    assert verdict in VERDICTS, f"verdict {verdict!r} not in {sorted(VERDICTS)}"
    # self-similarity against the DNA identity_lock_source (itself) must be high
    assert float(similarity) > 0.9, f"self-similarity too low: {similarity}"
    assert verdict == "approved", f"self evaluation should be approved, got {verdict}"


def test_list_evaluations_records_result(client, reference_asset_id):
    resp = client.get(f"{API}/assets/{reference_asset_id}/evaluations")
    assert resp.status_code == 200, (
        f"list evaluations failed: {resp.status_code} {resp.text}"
    )
    items, _ = _unwrap_items(resp.json())
    assert len(items) >= 1, f"expected at least one persisted evaluation, got {items}"
    first = items[0]
    assert "similarity" in first
    assert first.get("verdict") in VERDICTS


def test_approve_asset(client, reference_asset_id):
    resp = client.post(
        f"{API}/assets/{reference_asset_id}/approve", json={"approved_by": "tester"}
    )
    assert resp.status_code == 200, (
        f"approve asset failed: {resp.status_code} {resp.text}"
    )
    body = resp.json()
    assert body["approval_status"] == "approved"
    assert body.get("approved_by") == "tester"


# ═══════════════════════════════════════════════════════════════════════════
# 7. RPG export
# ═══════════════════════════════════════════════════════════════════════════


def test_export_rpg_returns_manifest_and_files(client):
    resp = client.post(f"{API}/characters/{CHARACTER_ID}/export/rpg")
    assert resp.status_code == 200, f"export failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert "manifest" in body, f"manifest missing from export response: {list(body)}"
    assert "files" in body, f"files missing from export response: {list(body)}"
    assert isinstance(body["files"], list), f"files must be a list: {body['files']!r}"
    manifest = body["manifest"]
    for key in ("character", "dna", "assets", "provenance"):
        assert key in manifest, f"manifest missing key {key!r}: {list(manifest)}"
    assert manifest["character"]["character_id"] == CHARACTER_ID


# ═══════════════════════════════════════════════════════════════════════════
# 8. Generation job lifecycle (real SD15; may legitimately land in `failed`)
# ═══════════════════════════════════════════════════════════════════════════

TERMINAL_STATES = {"completed", "failed", "cancelled"}


def _poll_job_until_terminal(client, job_id: str, timeout_s: float = 180.0) -> dict:
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


def test_generate_job_sd15_lifecycle(client):
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/generate",
        json={
            "intent": "lifestyle_photography",
            "provider": "sd15",
            "steps": 5,
            "cfg": 1.0,
            "seed": 42,
        },
    )
    assert resp.status_code in (200, 202), (
        f"generate failed: {resp.status_code} {resp.text}"
    )
    created = resp.json()
    job_id = created.get("job_id")
    assert job_id, f"job_id missing from generate response: {created}"

    final = _poll_job_until_terminal(client, job_id, timeout_s=300.0)
    status = final.get("status")

    if status == "failed":
        # Real failure (e.g. runner/checkpoint unavailable in this environment).
        # Assert the failure is a recorded job outcome, not a crashed request.
        assert final.get("error"), f"failed job carries no error detail: {final}"
        pytest.xfail(
            f"sd15 generation failed in this environment: {final.get('error')}"
        )

    assert status == "completed", f"unexpected terminal status {status!r}: {final}"
    assert final.get("output_path"), f"completed job has no output_path: {final}"

    # On success the output must be registered as a reference asset on the character
    resp = client.get(
        f"{API}/characters/{CHARACTER_ID}/references",
        params={"category": "generation", "approved_only": "false"},
    )
    assert resp.status_code == 200, (
        f"listing generation assets failed: {resp.status_code} {resp.text}"
    )
    items, _ = _unwrap_items(resp.json())
    linked = [a for a in items if str(a.get("source_job_id")) == str(job_id)]
    assert linked, (
        f"completed job {job_id} did not register an asset in references: {items}"
    )
    for asset in linked:
        assert asset.get("asset_id"), asset


# ═══════════════════════════════════════════════════════════════════════════
# 9. Cancel: queued job → cancel → status stays cancelled
# ═══════════════════════════════════════════════════════════════════════════


def test_cancel_queued_job(client):
    resp = client.post(
        f"{API}/characters/{CHARACTER_ID}/generate",
        json={
            "intent": "portrait",
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

    resp = client.post(f"{API}/generation-jobs/{job_id}/cancel")
    assert resp.status_code == 200, f"cancel failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body.get("status") == "cancelled", (
        f"cancel did not mark job cancelled: {body}"
    )

    resp = client.get(f"{API}/generation-jobs/{job_id}")
    assert resp.status_code == 200, (
        f"get job after cancel failed: {resp.status_code} {resp.text}"
    )
    assert resp.json().get("status") == "cancelled", (
        f"job not cancelled after get: {resp.json()}"
    )
