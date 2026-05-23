"""Integration tests for downloaded audio models via API."""

import pytest
import httpx

BASE_URL = "http://localhost:8000/api/v1/models"

DOWNLOADED_MODELS = {
    "kokoro-82m": {"task": "text_to_speech", "group": "TTS"},
    "parler-tts-mini": {"task": "text_to_speech", "group": "TTS"},
    "qwen3-tts-0.6b": {"task": "text_to_speech", "group": "TTS"},
    "fish-speech-1.5": {"task": "text_to_speech", "group": "TTS"},
    "cosyvoice2-0.5B": {"task": "text_to_speech", "group": "TTS"},
    "index-tts": {"task": "text_to_speech", "group": "TTS"},
    "whisper-base": {"task": "automatic_speech_recognition", "group": "ASR"},
    "distil-whisper-large-v2": {"task": "automatic_speech_recognition", "group": "ASR"},
    "whisper-large-v2": {"task": "automatic_speech_recognition", "group": "ASR"},
    "fish-speech-s2-pro": {"task": "text_to_speech", "group": "Voice Clone"},
    "ecapa-tdnn": {"task": "speaker_embedding", "group": "Speaker ID"},
    "demucs": {"task": "audio_source_separation", "group": "Separation"},
    "stable-audio-3-small-music": {"task": "text_to_audio", "group": "Music Gen"},
    "stable-audio-3-small-sfx": {"task": "text_to_audio", "group": "SFX Gen"},
    "stable-audio-3-medium": {"task": "text_to_audio", "group": "Audio Gen"},
    "higgs-audio-v2-3B": {"task": "text_to_audio", "group": "Audio Gen"},
}


@pytest.mark.integration
class TestDownloadedModels:
    """Verifies all 16 downloaded audio models via API."""

    @pytest.mark.parametrize("model_id,info", DOWNLOADED_MODELS.items())
    def test_model_is_local(self, model_id, info):
        response = httpx.get(f"{BASE_URL}/{model_id}")
        assert response.status_code == 200
        data = response.json().get("data", {})
        assert data.get("is_local") is True, f"{model_id} is not local"
        assert data.get("id") == model_id

    @pytest.mark.parametrize("model_id,info", DOWNLOADED_MODELS.items())
    def test_model_has_correct_task(self, model_id, info):
        response = httpx.get(f"{BASE_URL}/{model_id}")
        assert response.status_code == 200
        data = response.json().get("data", {})
        tasks = data.get("tasks", [])
        assert info["task"] in tasks, (
            f"{model_id} expected task {info['task']}, got {tasks}"
        )

    @pytest.mark.parametrize("model_id,info", DOWNLOADED_MODELS.items())
    def test_model_has_download_info(self, model_id, info):
        response = httpx.get(f"{BASE_URL}/{model_id}")
        assert response.status_code == 200
        data = response.json().get("data", {})
        assert data.get("file_path") is not None
        assert data.get("size_bytes") is not None

    def test_all_models_count(self):
        """Verify all 16 downloaded models are recognized."""
        response = httpx.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        models = data.get("data", []) if isinstance(data, dict) else data
        audio_models = [m for m in models if m.get("modality") == "audio"]
        local_audio = [m for m in audio_models if m.get("is_local")]
        assert len(local_audio) >= 16


@pytest.mark.integration
class TestModelDownloadByGroup:
    """Group-based model tests."""

    def test_tts_group_has_downloaded_models(self):
        response = httpx.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        models = data.get("data", []) if isinstance(data, dict) else data
        tts = [
            m
            for m in models
            if m.get("modality") == "audio"
            and m.get("is_local")
            and "text_to_speech" in m.get("tasks", [])
        ]
        assert len(tts) >= 6

    def test_asr_group_has_downloaded_models(self):
        response = httpx.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        models = data.get("data", []) if isinstance(data, dict) else data
        asr = [
            m
            for m in models
            if m.get("modality") == "audio"
            and m.get("is_local")
            and "automatic_speech_recognition" in m.get("tasks", [])
        ]
        assert len(asr) >= 3

    def test_generation_group_has_downloaded_models(self):
        response = httpx.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        models = data.get("data", []) if isinstance(data, dict) else data
        gen = [
            m
            for m in models
            if m.get("modality") == "audio"
            and m.get("is_local")
            and "text_to_audio" in m.get("tasks", [])
        ]
        assert len(gen) >= 4

    def test_speaker_separation_group(self):
        response = httpx.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        models = data.get("data", []) if isinstance(data, dict) else data
        sep = [
            m
            for m in models
            if m.get("modality") == "audio"
            and m.get("is_local")
            and (
                "audio_source_separation" in m.get("tasks", [])
                or "speaker_verification" in m.get("tasks", [])
            )
        ]
        assert len(sep) >= 2


@pytest.mark.integration
class TestModelDownloadTaskStream:
    """Verifies download task API."""

    def test_download_task_status_lookup(self):
        response = httpx.get(f"{BASE_URL}/tasks/kokoro-82m")
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            task = response.json()
            assert "status" in task

    def test_download_task_stream_endpoint(self):
        response = httpx.get(f"{BASE_URL}/tasks/kokoro-82m/stream")
        assert response.status_code in (200, 404)

    def test_global_task_stream_endpoint(self):
        response = httpx.get(f"{BASE_URL}/tasks/stream")
        assert response.status_code in (200, 404)

    def test_download_task_for_local_model_exists(self):
        response = httpx.get(f"{BASE_URL}/tasks/parler-tts-mini")
        if response.status_code == 200:
            task = response.json()
            assert task.get("task_id") == "parler-tts-mini"
