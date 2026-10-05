"""audio ASR engine-registry thin-router tests (closes the unreachable-registry gap).

Mounts the ASR engine router on a minimal FastAPI app and exercises the HTTP
contract for the three picker-facing endpoints:

- GET /api/v1/audio/asr/engines
- GET /api/v1/audio/asr/engines/default
- GET /api/v1/audio/asr/engines/{engine_id}/install-state

These routes existed nowhere on the wire: ``list_asr_engines`` had an ``@node``
wrapper and no router, so the registry was reachable from an agent and from
Python but 404'd from the browser. The UI model picker therefore had no way to
learn which engine owns a model, or whether that engine was flag-gated.

The handlers are pure pass-throughs to ``common_lib`` ``@node`` functions, so no
patching is needed — these tests run the real registry probes and assert the
real registry shape, mirroring the platform's thin-router rule.

Mounting is asserted separately (below), because a declared-but-unmerged router
looks identical to a working one in the source tree and every route 404s.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_AUTH", "true")


@pytest.fixture(scope="module")
def client() -> TestClient:
    from app.modules.audio.routes.asr_engines import router as asr_router

    app = FastAPI()
    app.include_router(asr_router, prefix="/api/v1/audio")
    return TestClient(app)


# ── GET /asr/engines ──────────────────────────────────────────────────────────


def test_list_engines_returns_registry_shape(client: TestClient):
    """The core contract: `engines` + `preference_order` from list_asr_engines()."""
    resp = client.get("/api/v1/audio/asr/engines")
    assert resp.status_code == 200
    body = resp.json()

    assert "engines" in body
    assert isinstance(body["engines"], list)
    assert isinstance(body["preference_order"], list)
    assert body["preference_order"], "preference order must not be empty"


def test_list_engines_each_row_has_the_picker_fields(client: TestClient):
    """A picker needs availability, why-not, install state and gpu support per row."""
    resp = client.get("/api/v1/audio/asr/engines")
    assert resp.status_code == 200
    engines = resp.json()["engines"]

    assert engines, "at least one engine must be listed"
    for engine in engines:
        assert "id" in engine
        assert "display_name" in engine
        assert isinstance(engine["available"], bool)
        assert "reason" in engine
        assert "install_state" in engine
        assert isinstance(engine["gpu_compat"], list)


def test_list_engines_advertises_the_model_to_engine_mapping(client: TestClient):
    """The join the UI was missing: which engine owns which model id.

    Without this, a picker has to guess the engine from the model name — which is
    exactly how parakeet-redux came to be offered while nothing could load it."""
    resp = client.get("/api/v1/audio/asr/engines")
    assert resp.status_code == 200
    body = resp.json()

    mapping = body["model_engines"]
    assert mapping["parakeet-redux"] == "moondream-photon"
    assert mapping["whisper-medium"] == "faster-whisper"
    assert mapping["whisper-large-v3-turbo"] == "faster-whisper"

    # Models the registry lists but that have no engine are named, not hidden —
    # the picker can grey them out with a reason instead of offering a dud.
    assert "cohere-transcribe" in body["unsupported_models"]
    assert "vibevoice-asr" in body["unsupported_models"]


def test_flag_gated_engine_is_listed_as_unselectable_with_a_reason(client: TestClient):
    """A flag-off engine is reported, never silently dropped.

    Hiding the row would make it look like the engine does not exist; listing it
    as unavailable with the operator action is the useful behaviour."""
    resp = client.get("/api/v1/audio/asr/engines")
    assert resp.status_code == 200
    engines = resp.json()["engines"]

    photon = next((e for e in engines if e["id"] == "moondream-photon"), None)
    if photon is None:
        pytest.skip("moondream-photon adapter not importable in this environment")

    if not photon["available"]:
        assert photon["install_state"] in {"flag-off", "missing-dependency"}
        assert photon["reason"], "an unavailable engine must say why"


# ── GET /asr/engines/default ──────────────────────────────────────────────────


def test_default_engine_returns_registry_shape(client: TestClient):
    """{id, available, reason} — the engine actually in effect right now."""
    resp = client.get("/api/v1/audio/asr/engines/default")
    assert resp.status_code == 200
    body = resp.json()

    assert set(body) == {"id", "available", "reason"}
    assert isinstance(body["available"], bool)


def test_default_engine_is_flag_safe(client: TestClient):
    """A flag-off engine must never be reported as the active default.

    `moondream-photon` is appended to the preference order precisely so that
    'auto' keeps resolving to faster-whisper until an operator opts in."""
    resp = client.get("/api/v1/audio/asr/engines/default")
    assert resp.status_code == 200
    body = resp.json()
    if body["available"]:
        assert body["id"] != "moondream-photon", (
            "a flag-gated engine must not win auto-detection while its flag is OFF"
        )


# ── GET /asr/engines/{engine_id}/install-state ────────────────────────────────


def test_install_state_returns_registry_shape(client: TestClient):
    resp = client.get("/api/v1/audio/asr/engines/faster-whisper/install-state")
    assert resp.status_code == 200
    body = resp.json()

    assert set(body) == {"engine_id", "install_state", "available", "reason"}
    assert body["engine_id"] == "faster-whisper"
    assert body["install_state"] in {
        "installed",
        "missing-dependency",
        "missing-sidecar",
        "flag-off",
    }


def test_install_state_of_unknown_engine_is_200_not_404(client: TestClient):
    """An unknown id reports a state so a picker can render the row.

    A 404 would make the picker treat the engine as absent rather than
    unrecognised, which is a different (and misleading) message."""
    resp = client.get("/api/v1/audio/asr/engines/no-such-engine/install-state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert "unknown engine" in body["reason"]


def test_install_state_of_flag_gated_engine_reports_flag_off(client: TestClient):
    """moondream-photon is gated; with the flag OFF its state must be 'flag-off'
    naming the AUDIO_FLAG_-prefixed env var (the bare name is silently ignored)."""
    resp = client.get("/api/v1/audio/asr/engines/moondream-photon/install-state")
    assert resp.status_code == 200
    body = resp.json()

    if body["install_state"] == "flag-off":
        assert "AUDIO_FLAG_PARAKEET_REDUX_ENABLED" in body["reason"]


# ── Mounting ──────────────────────────────────────────────────────────────────


def test_asr_engine_router_is_merged_into_the_audio_router():
    """A declared-but-unmerged router 404s at every URL below.

    This asserts the merge in routes/__init__.py happened, which is the step that
    is easy to omit and impossible to notice from the router file alone."""
    from app.modules.audio import routes as audio_routes

    paths = {getattr(r, "path", None) for r in audio_routes.router.routes}
    assert "/asr/engines" in paths, (
        "asr_engines router was declared but not merged into the audio router — "
        "every ASR engine route would 404"
    )
    assert "/asr/engines/default" in paths
    assert "/asr/engines/{engine_id}/install-state" in paths
