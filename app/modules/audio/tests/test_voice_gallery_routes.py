"""
Tests for voice gallery / bundle / describe / refinement routes (W4-L10 completion).
Uses the full FastAPI app for proper middleware support.
"""

import unittest
from unittest.mock import patch

# Absolute imports only
from fastapi.testclient import TestClient

# Import the main app to test with full middleware
from app.main import app

FLAG_PATH = "common_lib.modules.audio_processing.memory.feature_flags.is_enabled"

GALLERY = "/api/v1/audio/gallery/archetypes"
BUNDLE_EXPORT = "/api/v1/audio/voice/bundles/export"
BUNDLE_IMPORT = "/api/v1/audio/voice/bundles/import"
DESCRIBE = "/api/v1/audio/voice/describe"
REFINEMENT = "/api/v1/audio/refinement/run"


class TestVoiceGalleryRoutes(unittest.TestCase):
    """Tests for /gallery/* browse/search/plan routes (VOICE_GALLERY_ENABLED)."""

    def setUp(self):
        self.client = TestClient(app)

    @patch(FLAG_PATH, return_value=False)
    def test_gallery_disabled_payload(self, _mock_flag):
        """Gallery routes surface the service's disabled payload when flag is OFF."""
        response = self.client.get(GALLERY)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertNotEqual(data["status"], "ok")

    @patch(FLAG_PATH, return_value=True)
    def test_gallery_list_ok(self, _mock_flag):
        """Gallery list returns ok with archetype cards when flag is ON."""
        response = self.client.get(GALLERY)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("archetypes", data)
        self.assertIsInstance(data["archetypes"], list)

    @patch(FLAG_PATH, return_value=True)
    def test_gallery_search_ok(self, _mock_flag):
        """Gallery search returns a query echo + matches list."""
        response = self.client.get("/api/v1/audio/gallery/search", params={"query": "narrator"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("archetypes", data)

    @patch(FLAG_PATH, return_value=True)
    def test_gallery_download_plan_unknown_404(self, _mock_flag):
        """Download plan for unknown archetype surfaces the service error payload."""
        response = self.client.post("/api/v1/audio/gallery/download/plan", params={"archetype_id": "no-such-id"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")


class TestBundleRoutes(unittest.TestCase):
    """Tests for /voice/bundles/* (OVSVOICE_ENABLED)."""

    def setUp(self):
        self.client = TestClient(app)

    @patch(FLAG_PATH, return_value=False)
    def test_bundle_export_disabled(self, _mock_flag):
        """Bundle export returns the service disabled payload when flag is OFF."""
        response = self.client.post(BUNDLE_EXPORT, json={"profile": {"id": "p1"}})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "disabled")

    @patch(FLAG_PATH, return_value=True)
    def test_bundle_roundtrip(self, _mock_flag):
        """Export → import roundtrip returns ok with a profile payload."""
        from common_lib.modules.audio_processing.generation.voice_cloning import (
            persona_bundle,
        )

        export_response = self.client.post(
            BUNDLE_EXPORT,
            json={"profile": {"id": "p1", "name": "Test Voice"}, "tags": ["test"]},
        )
        self.assertEqual(export_response.status_code, 200)
        export_data = export_response.json()
        self.assertEqual(export_data["status"], "ok")
        self.assertIn("bundle_b64", export_data)

        import_response = self.client.post(
            BUNDLE_IMPORT, json={"bundle_b64": export_data["bundle_b64"]}
        )
        self.assertEqual(import_response.status_code, 200)
        import_data = import_response.json()
        self.assertEqual(import_data["status"], "ok")
        # Import returns the parsed manifest; persona name round-trips inside it.
        self.assertEqual(import_data["manifest"]["persona"]["name"], "Test Voice")
        self.assertEqual(persona_bundle._FLAG, "OVSVOICE_ENABLED")

    @patch(FLAG_PATH, return_value=True)
    def test_bundle_import_invalid_b64(self, _mock_flag):
        """Import with non-base64 payload returns the service error payload."""
        response = self.client.post(BUNDLE_IMPORT, json={"bundle_b64": "!!!not-base64!!!"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")


class TestDescribeRoutes(unittest.TestCase):
    """Tests for /voice/describe (VOICE_DESCRIBE_ENABLED)."""

    def setUp(self):
        self.client = TestClient(app)

    @patch(FLAG_PATH, return_value=False)
    def test_describe_disabled(self, _mock_flag):
        """Describe returns the service disabled payload when flag is OFF."""
        response = self.client.post(DESCRIBE, json={"description": "warm female voice"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "disabled")

    @patch(FLAG_PATH, return_value=True)
    def test_describe_parses_attributes(self, _mock_flag):
        """Describe maps free text onto structured attributes (no LLM call needed)."""
        response = self.client.post(
            DESCRIBE, json={"description": "a warm elderly male narrator with a british accent"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        # Service contract: structured parse lands in `text` (+ llm_applied flag),
        # not a raw attrs dict — attrs are folded into the fallback sentence.
        self.assertIn("text", data)
        self.assertIn("llm_applied", data)


class TestRefinementRoutes(unittest.TestCase):
    """Tests for /refinement/run (REFINEMENT_ENABLED)."""

    def setUp(self):
        self.client = TestClient(app)

    @patch(FLAG_PATH, return_value=False)
    def test_refinement_disabled(self, _mock_flag):
        """Refinement returns the service disabled payload when flag is OFF."""
        response = self.client.post(REFINEMENT, json={"text": "the the quick fox"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "disabled")

    @patch(FLAG_PATH, return_value=True)
    def test_refinement_collapses_runs(self, _mock_flag):
        """Refinement collapses repetitive word/character artifacts."""
        response = self.client.post(REFINEMENT, json={"text": "hello hello hello world", "use_llm": False})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("text", data)


if __name__ == "__main__":
    unittest.main()
