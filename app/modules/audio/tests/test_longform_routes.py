"""Tests for longform routes (C072)."""

import pytest
from fastapi.testclient import TestClient

from app.modules.audio.routes.longform import router
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


client = TestClient(router)


class TestLongformRoutes:
    def test_import_txt(self):
        response = client.post(
            "/longform/import",
            files={"file": ("test.txt", b"Chapter 1\n\nHello world.", "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "chapters" in data
        assert data["chapters"] >= 1

    def test_import_empty_file(self):
        response = client.post(
            "/longform/import",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert response.status_code == 400

    def test_plan(self):
        response = client.post(
            "/longform/plan",
            json={"text": "# Chapter 1\n\nHello.\n\n# Chapter 2\n\nWorld."},
        )
        assert response.status_code == 200
        data = response.json()
        assert "chapters" in data
        assert len(data["chapters"]) == 2

    def test_plan_no_chapters(self):
        response = client.post(
            "/longform/plan",
            json={"text": "No headings here."},
        )
        # Should still create one chapter
        assert response.status_code == 200
        data = response.json()
        assert data["total_chapters"] == 1

    def test_cover_upload(self):
        # Create a minimal JPEG
        jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
        response = client.post(
            "/longform/cover",
            files={"cover": ("cover.jpg", jpeg_header, "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "path" in data
        assert data["path"].endswith(".jpg")

    def test_cover_invalid_type(self):
        response = client.post(
            "/longform/cover",
            files={"cover": ("cover.txt", b"not an image", "text/plain")},
        )
        assert response.status_code == 400

    def test_render_requires_text(self):
        response = client.post(
            "/longform/render",
            json={"text": ""},
        )
        assert response.status_code == 400

    def test_preview(self):
        response = client.post(
            "/longform/preview",
            json={"text": "# Chapter 1\n\nHello.", "chapter_index": 0},
        )
        # May fail if TTS not available, but should not be 404 (flag check)
        assert response.status_code != 404

    def test_resume_not_found(self):
        response = client.post("/longform/resume/nonexistent")
        assert response.status_code == 404

    def test_jobs_list(self):
        response = client.get("/longform/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
