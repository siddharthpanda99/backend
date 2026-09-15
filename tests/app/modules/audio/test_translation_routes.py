"""W5 C057 tests — translation thin routes (pure-router TestClient)."""

import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.audio.routes.translation import router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/audio")
    return app


class TestTranslationRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_app())

    # ── /translate ──────────────────────────────────────────────────────
    def test_translate_ok_via_llm_route(self):
        with mock.patch.dict(
            "common_lib.modules.audio_processing.translation.translator.os.environ",
            {"OPENAI_API_KEY": "k"},
        ):
            with mock.patch(
                "common_lib.modules.integration.ports.ai_gateway_port."
                "get_ai_gateway_chat",
                side_effect=lambda: (lambda m: "hola"),
            ):
                r = self.client.post(
                    "/api/v1/audio/translate",
                    json={"text": "hello", "source_lang": "en",
                          "target_lang": "es", "provider": "openai"},
                )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["text"], "hola")

    def test_translate_unknown_provider_400(self):
        r = self.client.post(
            "/api/v1/audio/translate",
            json={"text": "hi", "provider": "nope"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("unknown provider", r.json()["detail"])

    def test_translate_missing_key_400(self):
        with mock.patch.dict(
            "common_lib.modules.audio_processing.translation.engines.os.environ",
            {}, clear=True,
        ):
            r = self.client.post(
                "/api/v1/audio/translate",
                json={"text": "hi", "provider": "deepl"},
            )
        self.assertEqual(r.status_code, 400)
        self.assertIn("DEEPL_API_KEY", r.json()["detail"])

    # ── /translate/segments ─────────────────────────────────────────────
    def test_segments_literal_batch(self):
        with mock.patch.dict(
            "common_lib.modules.audio_processing.translation.translator.os.environ",
            {"OPENAI_API_KEY": "k"},
        ):
            with mock.patch(
                "common_lib.modules.integration.ports.ai_gateway_port."
                "get_ai_gateway_chat",
                side_effect=lambda: (lambda m: "bonjour"),
            ):
                r = self.client.post(
                    "/api/v1/audio/translate/segments",
                    json={"texts": ["hello", "world"],
                          "source_lang": "en", "target_lang": "fr",
                          "provider": "openai"},
                )
        self.assertEqual(r.status_code, 200)
        rows = r.json()["results"]
        self.assertEqual([x["text"] for x in rows], ["bonjour", "bonjour"])

    # ── /translate/quality ──────────────────────────────────────────────
    def test_quality_returns_context_or_none(self):
        body = "THEME: test show\nTERM: alpha || beta"
        with mock.patch(
            "common_lib.modules.integration.ports.ai_gateway_port."
            "get_ai_gateway_chat",
            side_effect=lambda: (lambda m: body),
        ):
            r = self.client.post(
                "/api/v1/audio/translate/quality",
                json={"segment_texts": ["alpha line"], "source_lang": "en",
                      "target_lang": "es"},
            )
        self.assertEqual(r.status_code, 200)
        ctx = r.json()["context"]
        self.assertEqual(ctx["theme"], "test show")
        self.assertEqual(ctx["terms"][0]["target"], "beta")

    def test_quality_never_500s_on_llm_failure(self):
        with mock.patch(
            "common_lib.modules.integration.ports.ai_gateway_port."
            "get_ai_gateway_chat",
            return_value=None,
        ):
            r = self.client.post(
                "/api/v1/audio/translate/quality",
                json={"segment_texts": ["x"], "source_lang": "en",
                      "target_lang": "es"},
            )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["context"])

    # ── glossary CRUD ───────────────────────────────────────────────────
    def test_glossary_crud_cycle(self):
        pid = "route-test-glossary"
        r = self.client.post(
            f"/api/v1/audio/translation/glossary/{pid}",
            json={"source": "Wren", "target": "Wren", "note": "name"},
        )
        self.assertEqual(r.status_code, 201)
        term_id = r.json()["id"]

        r = self.client.get(f"/api/v1/audio/translation/glossary/{pid}")
        self.assertEqual(len(r.json()["terms"]), 1)

        r = self.client.delete(f"/api/v1/audio/translation/glossary/{pid}/{term_id}")
        self.assertEqual(r.status_code, 200)

        r = self.client.delete(f"/api/v1/audio/translation/glossary/{pid}/{term_id}")
        self.assertEqual(r.status_code, 404)

    def test_glossary_add_requires_terms(self):
        r = self.client.post(
            "/api/v1/audio/translation/glossary/route-test-422",
            json={"source": "", "target": "b"},
        )
        self.assertEqual(r.status_code, 422)

    def test_glossary_clear(self):
        pid = "route-test-clear"
        self.client.post(
            f"/api/v1/audio/translation/glossary/{pid}",
            json={"source": "a", "target": "b"},
        )
        r = self.client.delete(f"/api/v1/audio/translation/glossary/{pid}")
        self.assertEqual(r.json()["deleted"], 1)


if __name__ == "__main__":
    unittest.main()
