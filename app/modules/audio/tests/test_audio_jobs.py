# Audio background-job executor tests (jobs migration)
"""Covers the contract the audio job executors must honour.

These tests deliberately stub ``_audio_service`` so nothing torch-scale is
constructed: they assert the *jobs contract* (dict params, float progress,
artifact refs, completion via the service) rather than model output.
"""

import asyncio
import json
import os
import shutil
import time

from common_lib.modules.jobs.artifacts import JOBS_ROOT
from common_lib.modules.jobs.models import JobRecord, JobStatus
from common_lib.modules.jobs.service import get_job_service
from fastapi import HTTPException

from app.modules.audio.runtime.job_executors import (
    _EXECUTORS,
    AUDIO_KIND_PREFIX,
    DUB_CLONE_KIND,
    DUB_INGEST_KIND,
    TTS_KIND,
    dub_clone_executor,
    dub_ingest_executor,
    ensure_audio_executors_registered,
    tts_executor,
)


class _FakeTTSResponse:
    """Minimal stand-in for ``TTSResponse`` (dict-able, exposes filename)."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.audio_url = f"/generated/audio/{filename}"

    def model_dump(self) -> dict:
        return {
            "audio_url": self.audio_url,
            "filename": self.filename,
            "duration_seconds": 1.5,
            "metadata": {"engine": "stub"},
        }


class _FakeAudioService:
    """Stub ``AudioService`` that writes one wav into its output dir."""

    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir

    async def generate_tts(self, request) -> _FakeTTSResponse:
        filename = "tts_out.wav"
        # Stub mirrors the async AudioService signature; writing a tiny fixture
        # file inline is intentional and never blocks real work.
        with open(os.path.join(self.output_dir, filename), "wb") as handle:  # noqa: ASYNC230
            handle.write(b"RIFF-fake-wav")
        return _FakeTTSResponse(filename)


def _cleanup(job_id: str) -> None:
    shutil.rmtree(JOBS_ROOT / job_id, ignore_errors=True)


def test_all_audio_kinds_are_namespaced_and_unique():
    kinds = [kind for kind, *_ in _EXECUTORS]
    assert kinds, "no audio executors declared"
    assert all(kind.startswith(AUDIO_KIND_PREFIX) for kind in kinds)
    assert len(kinds) == len(set(kinds)), "duplicate audio job kinds"


def test_ensure_audio_executors_registered_is_idempotent():
    assert ensure_audio_executors_registered() is True
    assert ensure_audio_executors_registered() is True
    service = get_job_service()
    for kind, *_ in _EXECUTORS:
        assert kind in service._executors, f"{kind} not registered"


def test_tts_executor_persists_artifacts_and_float_progress(tmp_path, monkeypatch):
    """Regression: the WIP version used record.params and dict progress."""
    import app.modules.audio.runtime.job_executors as executors

    audio_dir = tmp_path / "audio_out"
    audio_dir.mkdir()
    monkeypatch.setattr(
        executors, "_audio_service", lambda: _FakeAudioService(str(audio_dir))
    )

    job_id = "job_test_tts_artifacts"
    _cleanup(job_id)
    record = JobRecord(
        id=job_id,
        kind=TTS_KIND,
        params=json.dumps({"text": "hello"}),
    )
    assert isinstance(record.get_params(), dict), "params must decode to a dict"

    progress: list[float] = []
    result = tts_executor(record, lambda: False, progress.append)

    assert result["status"] == "success"
    refs = result["result_refs"]
    assert any(ref.endswith("tts_out.wav") for ref in refs), refs
    meta_ref = next(ref for ref in refs if ref.endswith("result.json"))
    with open(meta_ref, encoding="utf-8") as handle:
        meta = json.load(handle)
    assert meta["artifact_files"], "copied artifacts must be listed"
    assert all(isinstance(value, float) for value in progress), progress
    assert progress[-1] == 100.0
    _cleanup(job_id)


def test_cancelled_executor_returns_cancelled_payload(tmp_path, monkeypatch):
    import app.modules.audio.runtime.job_executors as executors

    audio_dir = tmp_path / "audio_out"
    audio_dir.mkdir()
    monkeypatch.setattr(
        executors, "_audio_service", lambda: _FakeAudioService(str(audio_dir))
    )
    record = JobRecord(
        id="job_test_cancel",
        kind=TTS_KIND,
        params=json.dumps({"text": "hi"}),
    )
    result = tts_executor(record, lambda: True, lambda _p: None)
    assert result["status"] == "cancelled"
    assert result["result_refs"] == []
    assert not (JOBS_ROOT / "job_test_cancel").exists()


def test_owned_job_service_stamps_authenticated_actor(tmp_path, monkeypatch):
    """Submits made through the audio proxy carry the request's subject id."""
    import app.modules.audio.runtime.job_executors as executors
    from app.modules.audio.runtime import actor as actor_module

    audio_dir = tmp_path / "owned_out"
    audio_dir.mkdir()
    monkeypatch.setattr(
        executors, "_audio_service", lambda: _FakeAudioService(str(audio_dir))
    )

    token = actor_module._actor.set("user-42")
    try:
        record = actor_module.owned_job_service().submit(
            TTS_KIND, params={"text": "hello"}
        )
        assert record.user_id == "user-42"
    finally:
        actor_module._actor.reset(token)

    assert actor_module.current_actor() == ""
    _cleanup(record.id)


def test_submit_runs_tts_executor_to_completion(tmp_path, monkeypatch):
    """End-to-end: JobService worker thread → executor → artifacts → terminal."""
    import app.modules.audio.runtime.job_executors as executors

    audio_dir = tmp_path / "out"
    audio_dir.mkdir()
    monkeypatch.setattr(
        executors, "_audio_service", lambda: _FakeAudioService(str(audio_dir))
    )
    ensure_audio_executors_registered()

    service = get_job_service()
    submitted = service.submit(TTS_KIND, params={"text": "hello"}, user_id="tester")

    deadline = time.time() + 15.0
    snapshot = None
    while time.time() < deadline:
        snapshot = service.get(submitted.id)
        if snapshot is not None and snapshot.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ):
            break
        time.sleep(0.05)

    assert snapshot is not None
    assert snapshot.status == JobStatus.COMPLETED, snapshot.error
    assert snapshot.progress == 100.0
    assert snapshot.user_id == "tester"
    assert snapshot.error is None
    assert any(ref.endswith("result.json") for ref in snapshot.get_result_refs())
    _cleanup(submitted.id)


# ---------------------------------------------------------------------------
# Dub routes (dub/clone, dub/ingest-url) — jobs contract
# ---------------------------------------------------------------------------


class _CaptureService:
    """Stands in for JobService.submit — records the call, returns a record."""

    def __init__(self) -> None:
        self.kind = ""
        self.params: dict = {}

    def submit(self, kind: str, params: dict | None = None, **_kw):
        import types

        self.kind = kind
        self.params = params or {}
        return types.SimpleNamespace(
            id="job_dub_capture",
            status="queued",
            kind=kind,
            progress=0.0,
            error=None,
            get_result_refs=list,
        )


def _dubbing_routes(monkeypatch, capture: _CaptureService):
    """Wire dubbing routes to the capture service with the flag ON."""
    from app.modules.audio.routes import dubbing

    monkeypatch.setattr(dubbing, "_flag_on", lambda: True)
    monkeypatch.setattr(dubbing, "_ensure_audio_jobs", lambda: capture)
    return dubbing


def test_dub_clone_route_submits_namespaced_job(monkeypatch):

    capture = _CaptureService()
    routes = _dubbing_routes(monkeypatch, capture)
    req = routes.DubCloneRequest(
        audio_path="in.wav", out_dir="out", segments=[{"start": 0.0}]
    )
    body = asyncio.run(routes.dub_clone(req))

    assert capture.kind == DUB_CLONE_KIND
    assert capture.params["audio_path"] == "in.wav"
    assert body["status"] == "queued"
    assert body["job_id"] == "job_dub_capture"
    assert body["kind"] == DUB_CLONE_KIND


def test_dub_clone_route_rejects_missing_paths_before_submit(monkeypatch):
    """Empty audio_path/out_dir must 400 at the route, not fail a GPU job."""
    capture = _CaptureService()
    routes = _dubbing_routes(monkeypatch, capture)
    req = routes.DubCloneRequest(audio_path="", out_dir="")

    try:
        asyncio.run(routes.dub_clone(req))
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected HTTPException 400")
    assert capture.kind == "", "job must not be submitted on invalid input"


def test_dub_ingest_url_route_submits_namespaced_job(monkeypatch):
    capture = _CaptureService()
    routes = _dubbing_routes(monkeypatch, capture)
    req = routes.DubIngestUrlRequest(url="https://example.com/v", fetch_subs=False)
    body = asyncio.run(routes.dub_ingest_url(req))

    assert capture.kind == DUB_INGEST_KIND
    assert capture.params["url"] == "https://example.com/v"
    assert capture.params["fetch_subs"] is False
    assert body["status"] == "queued"
    assert body["kind"] == DUB_INGEST_KIND


def test_dub_route_flag_gate_still_applies(monkeypatch):
    """DUBBING_ENABLED OFF → 503 before any job submit (unchanged behavior)."""
    from app.modules.audio.routes import dubbing

    capture = _CaptureService()
    monkeypatch.setattr(dubbing, "_flag_on", lambda: False)
    monkeypatch.setattr(dubbing, "_ensure_audio_jobs", lambda: capture)
    req = dubbing.DubIngestUrlRequest(url="https://example.com/v")

    try:
        asyncio.run(dubbing.dub_ingest_url(req))
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("expected HTTPException 503")
    assert capture.kind == ""


def test_dub_clone_executor_end_to_end(monkeypatch, tmp_path):
    """Executor honors the contract: dict params, float progress, result.json."""
    from common_lib.modules.audio_processing.dubbing import speaker_clone as sc

    out_dir = tmp_path / "clone_out"
    out_dir.mkdir()
    monkeypatch.setattr(sc, "ensure_vocals_track", lambda *a, **k: "vocals.wav")
    monkeypatch.setattr(
        sc, "extract_speaker_clones", lambda *a, **k: {"s1": "ref1.wav"}
    )
    monkeypatch.setattr(
        sc, "extract_segment_refs", lambda *a, **k: {0: "seg0.wav"}
    )

    job_id = "job_test_dub_clone"
    _cleanup(job_id)
    record = JobRecord(
        id=job_id,
        kind=DUB_CLONE_KIND,
        params=json.dumps(
            {
                "audio_path": "in.wav",
                "out_dir": str(out_dir),
                "segments": [{"start": 0.0}],
            }
        ),
    )
    progress: list[float] = []
    result = dub_clone_executor(record, lambda: False, progress.append)

    assert result["status"] == "success"
    meta_ref = next(
        ref for ref in result["result_refs"] if ref.endswith("result.json")
    )
    with open(meta_ref, encoding="utf-8") as handle:
        meta = json.load(handle)
    assert meta["found"] is True
    assert meta["clones"] == {"s1": "ref1.wav"}
    assert all(isinstance(value, float) for value in progress)
    assert progress[-1] == 100.0
    _cleanup(job_id)


def test_dub_ingest_executor_raises_on_error_status(monkeypatch):
    """ingest error dicts must fail the job (legacy route raised 400)."""
    from common_lib.modules.audio_processing.dubbing import ingest as dub_ingest

    monkeypatch.setattr(
        dub_ingest,
        "ingest_url",
        lambda *a, **k: {"status": "error", "reason": "blocked"},
    )
    record = JobRecord(
        id="job_test_dub_ingest_err",
        kind=DUB_INGEST_KIND,
        params=json.dumps({"url": "https://example.com/v"}),
    )
    try:
        dub_ingest_executor(record, lambda: False, lambda _p: None)
    except RuntimeError as exc:
        assert "blocked" in str(exc)
    else:
        raise AssertionError("expected RuntimeError from error ingest dict")
