"""
Tests for audio system routes (C091).
Uses the full FastAPI app for proper middleware support.
"""

import unittest
from unittest.mock import patch, MagicMock

# Absolute imports only
from fastapi.testclient import TestClient

# Import the main app to test with full middleware
from app.main import app


class TestSystemRoutes(unittest.TestCase):
    """Tests for system routes."""

    def setUp(self):
        self.client = TestClient(app)

    @patch(
        "common_lib.modules.audio_processing.memory.feature_flags.is_enabled",
        return_value=False,
    )
    def test_voice_convert_flag_off(self, mock_flag):
        """Voice convert should return 503 when RVC_ENABLED is OFF."""
        response = self.client.post(
            "/api/v1/audio/voice/convert",
            json={"source_path": "/tmp/test.wav", "target_voice": "voice1"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("RVC_ENABLED", response.json()["detail"])

    @patch(
        "common_lib.modules.audio_processing.memory.feature_flags.is_enabled",
        return_value=True,
    )
    @patch("app.modules.audio.routes.system.apply_rvc_post_step")
    def test_voice_convert_success(self, mock_rvc, mock_flag):
        """Voice convert should succeed when flag is ON."""
        mock_rvc.return_value = {
            "output_path": "/tmp/output.wav",
            "duration_seconds": 10.0,
            "success": True,
        }

        response = self.client.post(
            "/api/v1/audio/voice/convert",
            json={"source_path": "/tmp/test.wav", "target_voice": "voice1"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["output_path"], "/tmp/output.wav")
        self.assertEqual(data["duration_seconds"], 10.0)
        self.assertEqual(data["status"], "success")

    @patch(
        "common_lib.modules.audio_processing.memory.feature_flags.is_enabled",
        return_value=False,
    )
    def test_exports_flag_off(self, mock_flag):
        """Exports should return 503 when MEDIA_IO_ENABLED is OFF."""
        response = self.client.post(
            "/api/v1/audio/exports",
            json={"asset_ids": ["asset1"], "format": "wav"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("MEDIA_IO_ENABLED", response.json()["detail"])

    @patch(
        "common_lib.modules.audio_processing.memory.feature_flags.is_enabled",
        return_value=True,
    )
    @patch("app.modules.audio.routes.system.export_assets")
    def test_exports_success(self, mock_export, mock_flag):
        """Exports should succeed when flag is ON."""
        mock_export.return_value = {
            "export_path": "/tmp/export.zip",
            "asset_count": 1,
            "total_size_bytes": 1000,
            "success": True,
        }

        response = self.client.post(
            "/api/v1/audio/exports",
            json={"asset_ids": ["asset1"], "format": "wav"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["export_path"], "/tmp/export.zip")
        self.assertEqual(data["asset_count"], 1)

    def test_list_tools(self):
        """List tools should work without flag."""
        response = self.client.get("/api/v1/audio/tools/list")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tools", data)
        self.assertIsInstance(data["tools"], list)
        self.assertGreater(len(data["tools"]), 0)

    @patch(
        "common_lib.modules.audio_processing.memory.feature_flags.is_enabled",
        return_value=False,
    )
    def test_execute_tool_flag_off(self, mock_flag):
        """Tool execution should return 503 when flag is OFF."""
        response = self.client.post(
            "/api/v1/audio/tools/execute",
            json={"tool_name": "tts_synthesize", "parameters": {}},
        )
        self.assertEqual(response.status_code, 503)

    @patch(
        "common_lib.modules.audio_processing.memory.feature_flags.is_enabled",
        return_value=True,
    )
    @patch("common_lib.modules.audio_processing.service.AudioService.execute_tool")
    def test_execute_tool_not_implemented(self, mock_execute, mock_flag):
        """Tool execution should return 501 for unimplemented tools."""
        mock_execute.side_effect = AttributeError("Not implemented")

        response = self.client.post(
            "/api/v1/audio/tools/execute",
            json={"tool_name": "unknown_tool", "parameters": {}},
        )
        self.assertEqual(response.status_code, 501)

    @patch(
        "common_lib.modules.audio_processing.memory.feature_flags.is_enabled",
        return_value=False,
    )
    def test_diagnose_flag_off(self, mock_flag):
        """Diagnose should return 503 when OBSERVABILITY_ENABLED is OFF."""
        response = self.client.post("/api/v1/audio/system/diagnose", json={})
        self.assertEqual(response.status_code, 503)
        self.assertIn("OBSERVABILITY_ENABLED", response.json()["detail"])

    @patch(
        "common_lib.modules.audio_processing.memory.feature_flags.is_enabled",
        return_value=True,
    )
    @patch("common_lib.modules.audio_processing.service.AudioService.health_check")
    @patch("app.modules.audio.routes.system.get_stats")
    @patch(
        "common_lib.modules.audio_processing.library.storage_report.get_storage_report"
    )
    def test_diagnose_success(self, mock_storage, mock_stats, mock_health, mock_flag):
        """Diagnose should succeed when flag is ON."""
        mock_health.return_value = {"status": "healthy"}

        mock_stats.return_value = {"tts.latency_ms": {"count": 10, "mean": 150.0}}

        mock_storage.return_value = {"total_bytes": 1000000, "categories": {}}

        response = self.client.post("/api/v1/audio/system/diagnose", json={})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("health", data)
        self.assertIn("performance", data)
        self.assertIn("storage", data)
        self.assertIn("flags", data)
        self.assertIn("timestamp", data)

    def test_get_flags(self):
        """Get flags should work without flag."""
        response = self.client.get("/api/v1/audio/system/flags")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("flags", data)
        self.assertIn("effective", data)

    def test_health_check(self):
        """Health check should work without flag."""
        with patch(
            "common_lib.modules.audio_processing.service.AudioService.health_check"
        ) as mock_health:
            mock_health.return_value = {"status": "healthy"}

            response = self.client.get("/api/v1/audio/system/health")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
