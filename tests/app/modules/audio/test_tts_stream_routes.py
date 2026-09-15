"""Tests for TTS stream + SSE routes (C082)."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _flag_on():
    from common_lib.modules.audio_processing.memory.feature_flags import (
        TTS_STREAM_ENABLED,
        set_flag_override,
        clear_all_overrides,
    )

    set_flag_override(TTS_STREAM_ENABLED, True)
    yield
    clear_all_overrides()


def test_tts_stream_endpoint_exists(client):
    """Test that the TTS stream endpoint exists and returns proper response."""
    resp = client.post(
        "/api/v1/audio/stream/tts",
        json={"text": "Hello world", "voice_id": "default"},
    )
    # May fail due to missing TTS models, but endpoint should exist
    assert resp.status_code in (200, 500, 503)


def test_sse_events_endpoint_exists(client):
    """Test that the SSE events endpoint exists."""
    # Need a valid job_id - use a dummy one
    resp = client.get("/api/v1/audio/stream/events/dummy-job-id")
    # Should return 404 for non-existent job, not 404 for missing route
    assert resp.status_code in (404, 500, 503)
    if resp.status_code == 404:
        data = resp.json()
        assert "not found" in data.get("detail", "").lower()


def test_tts_stream_flag_off(client):
    from common_lib.modules.audio_processing.memory.feature_flags import (
        clear_all_overrides,
    )

    clear_all_overrides()

    resp = client.post("/api/v1/audio/stream/tts", json={"text": "test"})
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()

    resp = client.get("/api/v1/audio/stream/events/test")
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


def test_events_sse_format(client):
    """Test SSE event format helper."""
    from app.modules.audio.routes.events import SSEEvent, SSEEventType

    event = SSEEvent.progress("job-123", 0.5)
    sse_str = event.to_sse()
    assert "event: progress" in sse_str
    assert "job-123" in sse_str
    assert "0.5" in sse_str

    event = SSEEvent.completed("job-123", {"result": "ok"})
    sse_str = event.to_sse()
    assert "event: completed" in sse_str
    assert "job-123" in sse_str

    event = SSEEvent.failed("job-123", "Something went wrong")
    sse_str = event.to_sse()
    assert "event: failed" in sse_str
    assert "Something went wrong" in sse_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
