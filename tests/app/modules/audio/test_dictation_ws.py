"""W2 C028 tests — WS dictation endpoints (pure-router TestClient smoke)."""

import struct
import unittest

from starlette.websockets import WebSocketDisconnect

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.audio.routes.dictation import router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _pcm(sr: int = 16000, ms: int = 100, amp: int = 2000) -> bytes:
    import math

    n = int(sr * ms / 1000)
    return b"".join(
        struct.pack("<h", int(amp * math.sin(2 * math.pi * 220 * i / sr)))
        for i in range(n)
    )


class TestDictationWS(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_app())

    def test_remote_client_rejected_before_accept(self):
        # Simulate a remote origin via X-Forwarded-For (proxy hop): the guard
        # closes with code 1008 BEFORE accepting — no ready frame ever flows.
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(
                "/ws/transcribe", headers={"X-Forwarded-For": "203.0.113.9"}
            ) as ws:
                ws.receive_json()

    def test_flag_off_degrades_with_error_frame(self):
        from common_lib.modules.audio_processing.transcription import (
            dictation as dc,
        )

        with unittest.mock.patch.object(dc, "is_enabled", return_value=False):
            with self.client.websocket_connect("/ws/transcribe") as ws:
                msg = ws.receive_json()
        self.assertEqual(msg["type"], "error")
        self.assertIn("OFF", msg["reason"])
        self.assertTrue(msg["recoverable"])

    def test_flag_on_wheel_missing_error_frame(self):
        from common_lib.modules.audio_processing.transcription import (
            dictation as dc,
        )

        with unittest.mock.patch.object(dc, "is_enabled", return_value=True):
            with unittest.mock.patch.object(
                dc, "sherpa_available",
                return_value=(False, "sherpa-onnx not installed: x"),
            ):
                with self.client.websocket_connect("/ws/transcribe") as ws:
                    msg = ws.receive_json()
        self.assertEqual(msg["type"], "error")
        self.assertIn("sherpa-onnx", msg["reason"])
        self.assertFalse(msg["recoverable"])

    def test_ready_then_end_control(self):
        from common_lib.modules.audio_processing.transcription import (
            dictation as dc,
        )

        with unittest.mock.patch.object(dc, "is_enabled", return_value=True):
            with unittest.mock.patch.object(
                dc, "sherpa_available", return_value=(True, "ready")
            ):
                with self.client.websocket_connect(
                    "/ws/transcribe?sample_rate=16000"
                ) as ws:
                    ready = ws.receive_json()
                    self.assertEqual(ready["type"], "ready")
                    self.assertEqual(ready["sample_rate"], 16000)
                    ws.send_text("__end__")
                    final = ws.receive_json()
        self.assertEqual(final["type"], "final")

    def test_silence_frames_skipped(self):
        from common_lib.modules.audio_processing.transcription import (
            dictation as dc,
        )

        with unittest.mock.patch.object(dc, "is_enabled", return_value=True):
            with unittest.mock.patch.object(
                dc, "sherpa_available", return_value=(True, "ready")
            ):
                with self.client.websocket_connect("/ws/transcribe") as ws:
                    self.assertEqual(ws.receive_json()["type"], "ready")
                    ws.send_bytes(b"\x00\x00" * 1600)  # pure digital silence
                    ws.send_text("__end__")
                    final = ws.receive_json()
        self.assertEqual(final["type"], "final")

    def test_platform_stream_path_same_protocol(self):
        from common_lib.modules.audio_processing.transcription import (
            dictation as dc,
        )

        with unittest.mock.patch.object(dc, "is_enabled", return_value=True):
            with unittest.mock.patch.object(
                dc, "sherpa_available", return_value=(True, "ready")
            ):
                with self.client.websocket_connect(
                    "/ws/platform/audio/stream"
                ) as ws:
                    ready = ws.receive_json()
        self.assertEqual(ready["type"], "ready")

    def test_oversized_frame_rejected_without_close(self):
        from common_lib.modules.audio_processing.transcription import (
            dictation as dc,
        )

        with unittest.mock.patch.object(dc, "is_enabled", return_value=True):
            with unittest.mock.patch.object(
                dc, "sherpa_available", return_value=(True, "ready")
            ):
                with self.client.websocket_connect("/ws/transcribe") as ws:
                    ws.receive_json()
                    ws.send_bytes(b"\x01\x00" * 100_000)  # > MAX_FRAME_BYTES
                    err = ws.receive_json()
                    self.assertEqual(err["type"], "error")
                    ws.send_text("__end__")
                    ws.receive_json()


if __name__ == "__main__":
    unittest.main()
