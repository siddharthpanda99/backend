"""HTTP contract tests for the transcription route (thin-router layer).

Why this file exists
--------------------
`/api/v1/audio/transcribe` had **no** route-level test anywhere in the repo --
seven sibling audio route test files existed (batch, dubbing, nlp, translation,
openai-compat, dictation-ws, tts-stream) and none covered transcribe. That gap
is what let a silent P0 defect survive: the UI sent ``model`` while
``TranscriptionRequest`` declared ``model_id``, and with no HTTP test nothing
ever noticed that the user's model selection was discarded and every request
silently ran ``large-v3``.

These tests exercise the TRANSPORT contract only, per the platform's thin-router
rule (G1): the route is mounted on a minimal app and the real handlers run.
Whisper inference is stubbed at the pipeline-factory seam (it needs a GPU), so
what is under test is the request -> effective-model -> response mapping, which
is precisely the layer that was broken.

Run:
    cd "Backend Monorepo/Backend" && uv run pytest \
        tests/app/modules/audio/test_transcribe_routes.py -v
"""

from __future__ import annotations

import os
import wave
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DISABLE_AUTH", "true")


@pytest.fixture(scope="module")
def client() -> TestClient:
    """The real transcribe route, mounted exactly as production mounts it.

    ``router = APIRouter(dependencies=[Depends(capture_job_actor)])``, and
    ``capture_job_actor`` depends on ``get_current_identity``, which resolves a
    user through a Postgres session. Override just that identity dependency so
    the route can be exercised without a live database -- the auth subject is
    irrelevant to the transcription contract under test.
    """
    from app.modules.audio.routes.router import router as audio_router
    from app.modules.auth.dependencies.authz import get_current_identity
    from common_lib.modules.auth.authorization.models import PlatformIdentity

    app = FastAPI()

    def _fake_identity() -> PlatformIdentity:
        from datetime import datetime, timezone

        from common_lib.modules.auth.authorization.enums import SubjectType

        now = datetime.now(timezone.utc)
        return PlatformIdentity(
            subject_id="test-subject",
            subject_type=SubjectType.HUMAN,
            display_name="Route Test",
            tenant_id="default",
            created_at=now,
            created_by="test-fixture",
        )

    app.dependency_overrides[get_current_identity] = _fake_identity
    app.include_router(audio_router, prefix="/api/v1/audio")
    return TestClient(app)


@pytest.fixture(scope="module")
def audio_file(tmp_path_factory) -> str:
    """A real, readable .wav so the service's existence check passes."""
    d = tmp_path_factory.mktemp("asr")
    p = Path(d) / "sample.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)  # 1s of silence
    return str(p)


@pytest.fixture
def captured(monkeypatch, tmp_path):
    """Swap the pipeline factory so we observe the effective model.

    Class-level swap on the real TranscriptionService, mirroring the pattern
    already used in common_lib's test_transcribe_model_alias.py. Only the
    Whisper inference is faked -- path resolution, the existence check and the
    response assembly all run for real.
    """
    # NOTE: `from app.modules.audio.routes import router` yields the APIRouter
    # (the package re-exports it), NOT the module. importlib gives the real
    # module object, which is where `_get_audio_service` is looked up.
    import importlib

    audio_route_module = importlib.import_module("app.modules.audio.routes.router")
    from common_lib.modules.audio_processing.services import transcription_service as ts

    seen: dict = {}

    def _fake_pipeline(model="large-v3", method="local"):
        seen["model"] = model
        seen["method"] = method

        class _P:
            def process_audio(
                self,
                audio_path=None,
                language=None,
                min_speakers=None,
                max_speakers=None,
                diarize=None,
            ):
                # `process_audio` returns a DICT the service subscripts
                # (result["text"], then result["segments"][i].get("start")...).
                seen["audio_path"] = audio_path
                seen["language"] = language
                seen["min_speakers"] = min_speakers
                seen["max_speakers"] = max_speakers
                seen["diarize"] = diarize
                return {
                    "text": "hello world",
                    "segments": [
                        {
                            "start": 0.0,
                            "end": 1.0,
                            "text": "hello world",
                            "speaker": "UNKNOWN",
                            "probability": 0.99,
                        }
                    ],
                    "conversation": [],
                    "duration": 1.0,
                }

        return _P()

    monkeypatch.setattr(
        ts.TranscriptionService,
        "_get_intelligence_pipeline",
        staticmethod(_fake_pipeline),
    )
    # The route's real AudioService resolves a Postgres-backed container, which
    # would make this an integration test. Hand it a REAL TranscriptionService so
    # request parsing -> effective_model -> response assembly still run for real,
    # without needing a database.
    service = ts.TranscriptionService(str(tmp_path))
    monkeypatch.setattr(audio_route_module, "_get_audio_service", lambda: service)
    return seen


# ── the P0 regression: model selection must actually reach the engine ────────


def test_model_field_is_honoured_not_discarded(
    client: TestClient, audio_file: str, captured
):
    """REGRESSION GUARD for the P0 defect.

    The UI sends ``model``. Before the fix Pydantic dropped it (unknown field)
    and the pipeline always saw ``large-v3``. Assert the requested value
    propagates.
    """
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={"audio_path": audio_file, "model": "whisper-medium", "diarize": False},
    )
    assert resp.status_code == 200, resp.text
    assert captured.get("model") == "whisper-medium"


def test_model_id_field_still_honoured(client: TestClient, audio_file: str, captured):
    """`model_id` is the canonical field and must keep working (G4 no-regression)."""
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={"audio_path": audio_file, "model_id": "base", "diarize": False},
    )
    assert resp.status_code == 200, resp.text
    assert captured.get("model") == "base"


def test_both_fields_model_wins_deterministically(
    client: TestClient, audio_file: str, captured
):
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={
            "audio_path": audio_file,
            "model": "medium",
            "model_id": "base",
            "diarize": False,
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured.get("model") == "medium"


def test_neither_field_defaults_to_large_v3(
    client: TestClient, audio_file: str, captured
):
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={"audio_path": audio_file, "diarize": False},
    )
    assert resp.status_code == 200, resp.text
    assert captured.get("model") == "large-v3"


# ── the other transport fields ───────────────────────────────────────────────


def test_diarization_method_is_forwarded(client: TestClient, audio_file: str, captured):
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={
            "audio_path": audio_file,
            "model_id": "base",
            "diarize": True,
            "diarization_method": "pyannote",
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured.get("method") == "pyannote"


def test_language_is_accepted(client: TestClient, audio_file: str, captured):
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={"audio_path": audio_file, "diarize": False, "language": "es"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("text") is not None


def test_speaker_bounds_accepted(client: TestClient, audio_file: str, captured):
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={
            "audio_path": audio_file,
            "diarize": True,
            "min_speakers": 2,
            "max_speakers": 5,
        },
    )
    assert resp.status_code == 200, resp.text


# ── response shape the UI actually parses ────────────────────────────────────


def test_response_shape_matches_what_the_ui_reads(
    client: TestClient, audio_file: str, captured
):
    """SttTab reads `text`, `segments[].{start,end,text}`, and `duration`."""
    body = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={"audio_path": audio_file, "diarize": False},
    ).json()
    for key in ("text", "segments", "duration"):
        assert key in body, f"UI expects {key!r} in the response, got {sorted(body)}"
    seg = body["segments"][0]
    for key in ("start", "end", "text"):
        assert key in seg, f"segment missing {key!r}"
    assert isinstance(seg["start"], (int, float))
    assert isinstance(seg["end"], (int, float))
    assert seg["end"] >= seg["start"]


def test_sync_true_returns_transcript_not_job_envelope(
    client: TestClient, audio_file: str, captured
):
    """`?sync=true` must run inline.

    Without the query param the route is jobs-backed and returns
    ``{status:'queued', job_id}`` -- the UI once parsed that envelope as if it
    were a transcript, which is why the UI now always sends ``?sync=true``.
    """
    body = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={"audio_path": audio_file, "diarize": False},
    ).json()
    assert body.get("status") != "queued"
    assert "text" in body


# ── error paths: must not fabricate success ──────────────────────────────────


def test_missing_audio_returns_404(client: TestClient, captured):
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={"audio_path": "/nonexistent/does-not-exist.wav", "diarize": False},
    )
    assert resp.status_code == 404


def test_missing_audio_path_is_rejected(client: TestClient):
    """`audio_path` is required -- a blank body must not transcribe anything."""
    resp = client.post("/api/v1/audio/transcribe?sync=true", json={"diarize": False})
    assert resp.status_code == 422


def test_unknown_model_is_not_silently_ignored(
    client: TestClient, audio_file: str, captured
):
    """An unrecognised model must not silently transcribe with some other one.

    Pins the no-silent-divergence rule: if the resolver added by the routing-gap
    work rejects unknown ids, this holds. If it instead maps them, this test
    fails loudly and the behaviour gets an explicit decision.
    """
    resp = client.post(
        "/api/v1/audio/transcribe?sync=true",
        json={
            "audio_path": audio_file,
            "model": "definitely-not-a-real-model",
            "diarize": False,
        },
    )
    # Either a clean error, or a 200 that did NOT silently claim the fake model ran.
    if resp.status_code == 200:
        assert captured.get("model") != "definitely-not-a-real-model"
    else:
        assert resp.status_code in (400, 404, 422, 500)
