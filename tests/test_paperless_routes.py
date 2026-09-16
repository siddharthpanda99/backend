"""Unit tests for Paperless FastAPI webhook and proxy routes (Wave 5)."""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.doc_processing.routes.paperless_proxy import router as proxy_router
from app.modules.doc_processing.routes.paperless_webhook import router as webhook_router
from common_lib.modules.doc_processing.config.flags import (
    PAPERLESS_INTEGRATION_ENABLED,
    clear_all_overrides,
    set_flag_override,
)
from common_lib.modules.doc_processing.paperless_client.models import (
    PaperlessDocument,
    PaperlessDocumentListResponse,
)
from common_lib.modules.doc_processing.tests.conftest_paperless import (
    SAMPLE_PAPERLESS_DOCUMENT,
    SAMPLE_POST_CONSUME_PAYLOAD,
)


class TestPaperlessRoutes(unittest.TestCase):
    """Test suite for FastAPI webhook receiver and proxy endpoints."""

    def setUp(self):
        clear_all_overrides()
        self.app = FastAPI()
        self.app.include_router(webhook_router, prefix="/api/v1/doc-processing")
        self.app.include_router(proxy_router, prefix="/api/v1/doc-processing")
        self.client = TestClient(self.app)

    def tearDown(self):
        clear_all_overrides()

    def test_webhook_disabled_when_flag_off(self):
        resp = self.client.post(
            "/api/v1/doc-processing/paperless/webhook",
            json=SAMPLE_POST_CONSUME_PAYLOAD,
            headers={"X-Paperless-Webhook-Secret": "paperless-platform-shared-secret"},
        )
        self.assertEqual(resp.status_code, 503)

    def test_webhook_unauthorized_bad_secret(self):
        set_flag_override(PAPERLESS_INTEGRATION_ENABLED, True)
        resp = self.client.post(
            "/api/v1/doc-processing/paperless/webhook",
            json=SAMPLE_POST_CONSUME_PAYLOAD,
            headers={"X-Paperless-Webhook-Secret": "wrong-secret"},
        )
        self.assertEqual(resp.status_code, 401)

    @patch("app.modules.doc_processing.routes.paperless_webhook.handle_paperless_post_consume")
    def test_webhook_accepted_valid_secret(self, mock_handler):
        set_flag_override(PAPERLESS_INTEGRATION_ENABLED, True)
        resp = self.client.post(
            "/api/v1/doc-processing/paperless/webhook",
            json=SAMPLE_POST_CONSUME_PAYLOAD,
            headers={"X-Paperless-Webhook-Secret": "paperless-platform-shared-secret"},
        )
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertEqual(data["status"], "ACCEPTED")
        self.assertEqual(data["document_id"], 101)

    @patch("app.modules.doc_processing.routes.paperless_proxy.get_paperless_client")
    def test_proxy_list_documents(self, mock_get_client):
        set_flag_override(PAPERLESS_INTEGRATION_ENABLED, True)
        mock_client = AsyncMock()
        mock_client.list_documents.return_value = PaperlessDocumentListResponse.model_validate(
            {
                "count": 1,
                "next": None,
                "previous": None,
                "all": [101],
                "results": [SAMPLE_PAPERLESS_DOCUMENT],
            }
        )
        mock_get_client.return_value = mock_client

        resp = self.client.get("/api/v1/doc-processing/paperless/documents?query=invoice")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], 101)

    @patch("app.modules.doc_processing.routes.paperless_proxy.get_paperless_client")
    def test_proxy_get_document(self, mock_get_client):
        set_flag_override(PAPERLESS_INTEGRATION_ENABLED, True)
        mock_client = AsyncMock()
        mock_client.get_document.return_value = PaperlessDocument.model_validate(SAMPLE_PAPERLESS_DOCUMENT)
        mock_get_client.return_value = mock_client

        resp = self.client.get("/api/v1/doc-processing/paperless/documents/101")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], 101)
        self.assertEqual(data["title"], "Vendor Invoice 2026-001")


if __name__ == "__main__":
    unittest.main()
