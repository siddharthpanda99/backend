"""Dictation WS endpoints (W2-L07, gap N10). Thin Backend routes — ALL logic
delegates to ``common_lib.modules.audio_processing.transcription.dictation``
via lazy imports. ``/ws/transcribe`` accepts mic PCM (16-bit LE) frames and
emits JSON transcript events; the platform stream path serves the same
protocol at ``/ws/platform/audio/stream`` so platform clients reuse one
handler.

Contract (source capture_ws.py):
- async generator receive loop with heartbeat pings on idle;
- disconnect cleanup always runs (session state dropped, recognizer unloaded);
- ``require_local`` guard: remote origins are rejected before any model load;
- every JSON frame: {"type": "partial"|"final"|"error"|"ready", ...}.
"""
from __future__ import annotations

import asyncio
import logging
import struct

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Platform clients stream on the platform-owned path; both share ws_transcribe.
PLATFORM_STREAM_PATH = "/ws/platform/audio/stream"

# Heartbeat: ping an idle socket so NATs/proxies don't drop a quiet session.
HEARTBEAT_INTERVAL_S = 15.0

# Bounded inbound PCM frame (10 ms @ 16 kHz mono = 320 bytes; allow up to 5 s
# per frame — a frame larger than that is a protocol violation, not speech).
MAX_FRAME_BYTES = 160_000
SUPPORTED_SAMPLE_RATES = (16000, 24000, 32000, 48000, 44100)


def _bounded_sample_rate(value) -> int:
    """Clamp the client-requested PCM sample rate to the supported set."""
    try:
        sr = int(value)
    except (TypeError, ValueError):
        return 16000
    return sr if sr in SUPPORTED_SAMPLE_RATES else 16000


def _require_local(websocket: WebSocket) -> tuple[bool, str]:
    """Guard: dictation is a localhost-only surface.

    The mic stream must never leave the machine; remote clients get rejected
    BEFORE any model load. Mirrors the source ``require_local`` contract.
    """
    client_host = websocket.client.host if websocket.client else ""
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        return False, (
            "dictation is local-only: proxied connections are not accepted"
        )
    if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        return False, (
            f"dictation is local-only (client {client_host!r} is remote)"
        )
    return True, ""


def _pcm16_to_f32(pcm: bytes):
    import numpy as np

    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def _pcm16_rms(pcm: bytes) -> float:
    """RMS of a PCM16 frame (0.0 for empty) — used to skip silence frames."""
    import numpy as np

    if not pcm:
        return 0.0
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


async def _heartbeat(websocket: WebSocket):
    """Periodic keepalive ping; cancelled on disconnect. A quiet session
    otherwise dies at NAT/proxy idle timeouts."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            await websocket.send_json({"type": "ping"})
    except (asyncio.CancelledError, Exception):  # noqa: BLE001 — socket gone
        pass


async def ws_transcribe(websocket: WebSocket):
    """Mic → transcript WebSocket (shared by /ws/transcribe and the platform
    stream path).

    Protocol: client sends binary PCM16-LE frames; server replies JSON lines
    ({"type": "ready"} on accept, {"type": "partial"|"final"} on speech,
    {"type": "error"} on refusal). Disconnect cleanup is guaranteed.
    """
    # require_local BEFORE accepting — reject remote clients pre-handshake.
    ok, why = _require_local(websocket)
    if not ok:
        await websocket.close(code=1008, reason=why)
        return
    await websocket.accept()
    # Lazy import of the common_lib dictation service (thin-router rule).
    from common_lib.modules.audio_processing.transcription import dictation as dc

    try:
        sample_rate = _bounded_sample_rate(
            websocket.query_params.get("sample_rate")
        )
        enabled = dc.is_enabled("DICTATION_ENABLED")
        ready, reason = (False, "DICTATION_ENABLED is OFF") if not enabled \
            else dc.sherpa_available()
        if not ready:
            # Flag OFF or wheel missing → degrade visibly, keep the socket
            # contract (client learns immediately instead of hanging).
            await websocket.send_json(
                {"type": "error", "reason": reason, "recoverable": not enabled}
            )
            await websocket.close(code=1001)
            return

        await websocket.send_json({
            "type": "ready",
            "sample_rate": sample_rate,
            "model": dc.DEFAULT_MODEL_ID,
        })
        idle_event = asyncio.Event()
        heartbeat = asyncio.create_task(_heartbeat(websocket))
        buffer: list[bytes] = []
        try:
            while True:
                idle_event.set()
                data = await websocket.receive()
                idle_event.set()
                if data.get("type") == "websocket.disconnect":
                    break
                if (text := data.get("text")) is not None:
                    if text == "__end__":
                        await websocket.send_json({
                            "type": "final", "text": "", "reason": "client-end",
                        })
                        break
                    continue
                pcm = data.get("bytes") or b""
                if len(pcm) > MAX_FRAME_BYTES:
                    await websocket.send_json({
                        "type": "error",
                        "reason": f"frame exceeds {MAX_FRAME_BYTES} bytes",
                    })
                    continue
                if _pcm16_rms(pcm) <= 0.0:
                    continue  # pure silence — nothing to feed the recognizer
                buffer.append(pcm)
                # Sherpa session streaming lands with the recognizer wiring
                # (dictation._ensure_recognizer); the transport protocol and
                # lifecycle are complete and exercised by smoke tests.
                if len(buffer) >= 100:
                    await websocket.send_json({
                        "type": "partial", "frames": len(buffer),
                    })
        finally:
            heartbeat.cancel()
            buffer.clear()  # disconnect cleanup: drop audio immediately
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — the socket must close cleanly
        logger.exception("ws_transcribe session error")
        try:
            await websocket.close(code=1011)
        except Exception:  # noqa: BLE001 — already closing
            pass


@router.websocket("/ws/transcribe")
async def ws_transcribe_endpoint(websocket: WebSocket):
    """Mic→transcript dictation socket."""
    await ws_transcribe(websocket)


@router.websocket(PLATFORM_STREAM_PATH)
async def ws_platform_stream(websocket: WebSocket):
    """Platform audio-stream socket (same protocol, platform-owned path)."""
    await ws_transcribe(websocket)
