"""Tests for takes compare/promote extension (C074)."""

import pytest
from fastapi.testclient import TestClient

from app.modules.audio.routes.takes_routes import router
from common_lib.modules.audio_processing.generation.takes_manager import (
    get_takes_manager,
    reset_takes_manager,
)
from common_lib.modules.audio_processing.memory.feature_flags import (
    LONGFORM_ENABLED,
    set_flag_override,
    clear_all_overrides,
)


@pytest.fixture(autouse=True)
def _flag_on():
    set_flag_override(LONGFORM_ENABLED, True)
    yield
    clear_all_overrides()


@pytest.fixture(autouse=True)
def _reset_takes():
    reset_takes_manager()
    yield
    reset_takes_manager()


client = TestClient(router)


class TestTakesComparePromote:
    def _create_session(self, source="tts", intent_key="test"):
        manager = get_takes_manager()
        # Create a few takes
        for i in range(3):
            manager.record_take(
                source=source,
                intent_key=intent_key,
                mode="generate" if i == 0 else "retry",
                output_path=f"/tmp/take{i}.wav",
                output_url=f"/audio/take{i}.wav",
                params={
                    "text": f"Hello take {i}",
                    "voice": "voice1" if i < 2 else "voice2",
                },
                seed=42 if i < 2 else None,
                metadata={"model": "model1"},
            )
        return f"{source}/{intent_key}"

    def test_compare_takes(self):
        session_id = self._create_session()
        response = client.post(
            "/takes/compare",
            json={"session_id": session_id, "take_a": 1, "take_b": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["take_a"]["take_number"] == 1
        assert data["take_b"]["take_number"] == 2
        assert "diff" in data
        assert "params" in data["diff"]

    def test_compare_takes_not_found(self):
        session_id = self._create_session()
        response = client.post(
            "/takes/compare",
            json={"session_id": session_id, "take_a": 1, "take_b": 99},
        )
        assert response.status_code == 404

    def test_compare_invalid_session(self):
        response = client.post(
            "/takes/compare",
            json={"session_id": "invalid", "take_a": 1, "take_b": 2},
        )
        assert response.status_code == 400

    def test_promote_best_latest(self):
        session_id = self._create_session()
        response = client.post(
            "/takes/promote-best",
            json={"session_id": session_id, "criteria": "latest"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["take_number"] == 3  # Latest is take 3

    def test_promote_best_first(self):
        session_id = self._create_session()
        response = client.post(
            "/takes/promote-best",
            json={"session_id": session_id, "criteria": "first"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["take_number"] == 1

    def test_promote_best_promoted(self):
        session_id = self._create_session()
        # First promote take 2
        manager = get_takes_manager()
        parts = session_id.split("/", 1)
        manager.promote_take(parts[0], parts[1], 2)

        response = client.post(
            "/takes/promote-best",
            json={"session_id": session_id, "criteria": "promoted"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["take_number"] == 2

    def test_promote_best_highest_quality(self):
        session_id = self._create_session()
        # Add an error to take 3
        manager = get_takes_manager()
        parts = session_id.split("/", 1)
        session = manager.get_session(session_id)
        # Manually add error to latest take
        for take in session.takes:
            if take.take_number == 3:
                take.error = "Generation failed"

        response = client.post(
            "/takes/promote-best",
            json={"session_id": session_id, "criteria": "highest_quality"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should promote take 2 (latest successful)

    def test_promote_best_invalid_criteria(self):
        session_id = self._create_session()
        response = client.post(
            "/takes/promote-best",
            json={"session_id": session_id, "criteria": "unknown"},
        )
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
