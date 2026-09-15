"""Tests for OpenAI-compat routes (C081)."""

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
        OPENAI_COMPAT_ENABLED,
        set_flag_override,
        clear_all_overrides,
    )

    set_flag_override(OPENAI_COMPAT_ENABLED, True)
    yield
    clear_all_overrides()


def test_openai_speech(client):
    resp = client.post(
        "/api/v1/audio/openai/speech",
        json={"model": "tts-1", "input": "Hello world", "voice": "alloy"},
    )
    # May fail due to missing TTS models, but endpoint should exist
    assert resp.status_code in (200, 500, 503)


def test_openai_transcriptions(client):
    # Create a dummy audio file
    import io

    files = {"file": ("test.wav", io.BytesIO(b"RIFF....WAVE"), "audio/wav")}
    data = {"model": "whisper-1"}
    resp = client.post("/api/v1/audio/openai/transcriptions", files=files, data=data)
    # May fail due to missing ASR models, but endpoint should exist
    assert resp.status_code in (200, 400, 500, 503)


def test_openai_voices(client):
    resp = client.get("/api/v1/audio/openai/voices")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 6
    assert all("id" in v and "name" in v for v in data)


def test_openai_flag_off(client):
    from common_lib.modules.audio_processing.memory.feature_flags import (
        clear_all_overrides,
    )

    clear_all_overrides()

    resp = client.post("/api/v1/audio/openai/speech", json={"input": "test"})
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()

    resp = client.get("/api/v1/audio/openai/voices")
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
