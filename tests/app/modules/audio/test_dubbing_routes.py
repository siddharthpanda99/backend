"""W6 C067/C068 tests — dubbing thin routes (pure-router TestClient).

Covers: flag-gate 503, jobs CRUD + 404s, state transitions (409 on illegal),
generate planning (cache hit, timing, preview params), regen scope,
timing/clone/ingest/QC/export delegation, abort, and the SSE status stream.
"""

import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.audio.routes.dubbing import router

_FLAG_MOD = "common_lib.modules.audio_processing.memory.feature_flags"


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/audio")
    return app


def _flag_on():
    """Context manager stack turning DUBBING_ENABLED ON."""
    return mock.patch.dict("os.environ", {"AUDIO_FLAG_DUBBING_ENABLED": "1"})


class TestDubbingRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_app())
        # Fresh in-memory store + clean flag overrides per test (global
        # overrides are process-wide and can leak across test files).
        import common_lib.modules.audio_processing.dubbing.pipeline as dp
        from common_lib.modules.audio_processing.memory import feature_flags as ff

        dp._JOBS.clear()
        dp._ACTIVE_PROCS.clear()
        dp._ABORT_FLAGS.clear()
        ff.clear_all_overrides()
        self._env = _flag_on()
        self._env.start()

    def tearDown(self):
        self._env.stop()
        import common_lib.modules.audio_processing.dubbing.pipeline as dp
        from common_lib.modules.audio_processing.memory import feature_flags as ff

        ff.clear_all_overrides()
        dp._JOBS.clear()
        dp._ACTIVE_PROCS.clear()
        dp._ABORT_FLAGS.clear()

    # ── flag gate ───────────────────────────────────────────────────────
    def test_flag_off_returns_503(self):
        self._env.stop()  # drop the ON env for this test
        try:
            r = self.client.post(
                "/api/v1/audio/dub/jobs", json={"job_id": "x"},
            )
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.json()["detail"]["status"], "disabled")
            r = self.client.get("/api/v1/audio/dub/jobs")
            self.assertEqual(r.status_code, 503)
        finally:
            self._env.start()

    # ── jobs CRUD ───────────────────────────────────────────────────────
    def test_job_create_list_get_delete(self):
        r = self.client.post(
            "/api/v1/audio/dub/jobs",
            json={"job_id": "rt-job-1", "target_lang": "es"},
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["state"], "queued")

        r = self.client.get("/api/v1/audio/dub/jobs")
        self.assertEqual(len(r.json()["jobs"]), 1)

        r = self.client.get("/api/v1/audio/dub/jobs/rt-job-1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["job_id"], "rt-job-1")

        r = self.client.delete("/api/v1/audio/dub/jobs/rt-job-1")
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/api/v1/audio/dub/jobs/rt-job-1")
        self.assertEqual(r.status_code, 404)

    def test_job_create_invalid_id_400(self):
        r = self.client.post(
            "/api/v1/audio/dub/jobs", json={"job_id": "../evil"},
        )
        self.assertEqual(r.status_code, 400)

    def test_job_get_missing_404(self):
        r = self.client.get("/api/v1/audio/dub/jobs/nope")
        self.assertEqual(r.status_code, 404)

    def test_job_state_transition_409(self):
        self.client.post("/api/v1/audio/dub/jobs", json={"job_id": "rt-job-2"})
        r = self.client.post(
            "/api/v1/audio/dub/jobs/rt-job-2/state",
            json={"to_state": "generating"},
        )
        self.assertEqual(r.status_code, 409)
        r = self.client.post(
            "/api/v1/audio/dub/jobs/rt-job-2/state",
            json={"to_state": "preparing"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["state"], "preparing")

    # ── generate / regen / preview ──────────────────────────────────────
    def test_generate_plan_with_cache_hit(self):
        import os as _os
        import tempfile

        import common_lib.modules.audio_processing.dubbing.pipeline as dp

        with tempfile.TemporaryDirectory() as td:
            src = _os.path.join(td, "src.mp4")
            open(src, "wb").write(b"v")
            h = dp.compute_file_hash(src)
            dp.create_job("old", content_hash=h)
            for st in ("preparing", "transcribing", "translating",
                       "generating", "exporting", "done"):
                dp.update_state("old", st)
            vocals = _os.path.join(td, "vocals.wav")
            open(vocals, "wb").write(b"v")
            dp.set_artifacts("old", vocals_path=vocals)
            dp.create_job("new", content_hash=h)

            r = self.client.post(
                "/api/v1/audio/dub/generate",
                json={
                    "job_id": "new",
                    "segments": [{"id": "s1", "start": 0.0, "end": 4.0,
                                  "text": "hi"}],
                    "natural_durs_s": [1.0],
                    "total_dur_s": 6.0,
                    "timing_strategy": "smart_fit",
                    "options": {"num_step": 16},
                },
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["cache_hit"])
        self.assertEqual(body["cache_hit"]["job_id"], "old")
        self.assertEqual(body["timing"]["status"], "ok")
        self.assertEqual(body["regen_scope"]["mode"], "full")

    def test_generate_unknown_job_404(self):
        r = self.client.post(
            "/api/v1/audio/dub/generate", json={"job_id": "ghost"},
        )
        self.assertEqual(r.status_code, 404)

    def test_generate_bad_strategy_400(self):
        self.client.post("/api/v1/audio/dub/jobs", json={"job_id": "rt-job-3"})
        r = self.client.post(
            "/api/v1/audio/dub/generate",
            json={"job_id": "rt-job-3", "timing_strategy": "bogus"},
        )
        self.assertEqual(r.status_code, 400)

    def test_preview_params_via_route(self):
        self.client.post("/api/v1/audio/dub/jobs", json={"job_id": "rt-job-4"})
        r = self.client.post(
            "/api/v1/audio/dub/preview",
            json={"job_id": "rt-job-4", "options": {"num_step": 16}},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["options"]["num_step"], 8)

    def test_regen_scope_route(self):
        self.client.post("/api/v1/audio/dub/jobs", json={"job_id": "rt-job-5"})
        r = self.client.post(
            "/api/v1/audio/dub/regen",
            json={"job_id": "rt-job-5", "regen_only": [],
                  "timing_strategy": "strict_slot"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["mode"], "remix")

    # ── timing / export ─────────────────────────────────────────────────
    def test_timing_route(self):
        r = self.client.post(
            "/api/v1/audio/dub/timing",
            json={
                "segments": [{"id": "s1", "start": 0.0, "end": 4.0}],
                "natural_durs_s": [8.0],
                "total_dur_s": 6.0,
                "strategy": "smart_fit",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["segments"][0]["status"], "hybrid")

    def test_export_route_needs_retime(self):
        r = self.client.post(
            "/api/v1/audio/dub/export",
            json={
                "job_id": "rt-export",
                "plan": [{"orig_start": 1.0, "orig_end": 3.0,
                          "stretch_ratio": 1.4}],
                "orig_dur": 5.0,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["needs_retime"])
        self.assertIn("setpts=1.400000*PTS", r.json()["graph"])

    # ── QC ──────────────────────────────────────────────────────────────
    def test_qc_route_scores(self):
        r = self.client.post(
            "/api/v1/audio/dub/qc",
            json={
                "dub_segments": [{"id": "s1", "start": 0.0, "end": 2.0,
                                  "text": "hello world"}],
                "recognized": [{"start": 0.1, "end": 1.9,
                                "text": "hello moon"}],
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["verdicts"][0]["drift"], 0.5)

    # ── ingest (SSRF guard surfaced through the route) ──────────────────
    def test_ingest_url_ssrf_rejected_400(self):
        r = self.client.post(
            "/api/v1/audio/dub/ingest-url",
            json={"url": "http://127.0.0.1:8000/admin", "out_dir": "x"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("not allowed", r.json()["detail"])

    # ── abort ───────────────────────────────────────────────────────────
    def test_abort_known_and_unknown(self):
        self.client.post("/api/v1/audio/dub/jobs", json={"job_id": "rt-ab"})
        r = self.client.post("/api/v1/audio/dub/abort/rt-ab")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["state"], "aborted")

        r = self.client.post("/api/v1/audio/dub/abort/ghost")
        self.assertEqual(r.status_code, 404)

    # ── SSE status stream ───────────────────────────────────────────────
    def test_status_stream_terminal(self):
        import common_lib.modules.audio_processing.dubbing.pipeline as dp

        dp.create_job("rt-sse")
        for st in ("preparing", "transcribing", "translating",
                   "generating", "exporting", "done"):
            dp.update_state("rt-sse", st)
        with self.client.stream("GET", "/api/v1/audio/dub/status/rt-sse") as resp:
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.headers["content-type"].startswith("text/event-stream"))
            frames = b"".join(resp.iter_bytes()).decode("utf-8")
        self.assertIn("event: progress", frames)
        self.assertIn("event: end", frames)
        self.assertIn('"state": "done"', frames)

    def test_status_stream_unknown_job_errors(self):
        with self.client.stream("GET", "/api/v1/audio/dub/status/ghost") as resp:
            frames = b"".join(resp.iter_bytes()).decode("utf-8")
        self.assertIn("event: error", frames)


if __name__ == "__main__":
    unittest.main()
