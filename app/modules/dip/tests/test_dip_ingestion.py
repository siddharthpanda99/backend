"""
Integration tests for DIP Ingestion routes.

Verifies that all DIP Ingestion endpoints (/api/v1/dip/ingestion/*) correctly
delegate to controller functions, handle edge cases, and return expected
response shapes.

Uses sync TestClient (httpx.Client) to avoid pytest-asyncio incompatibility
with pytest 9.x. External dependencies are patched at the route module path.

Endpoints tested:
    POST /process        — Upload and process documents
    POST /compare        — Compare parsers (background job)
    GET  /compare/stream — SSE stream for compare notifications
    GET  /status/{job_id} — Get processing status
    GET  /parsers        — List available parsers
    POST /save           — Save extraction results
    GET  /stats          — Extraction statistics
    GET  /sources        — Ingestion sources
    GET  /vault          — List vault documents
    GET  /vault/{id}     — Get single vault document
    DELETE /vault/{id}   — Delete vault document
    POST /vault/{id}/rename — Rename vault document
    POST /upload         — Simple upload endpoint
    GET  /jobs           — List ingestion jobs
    GET  /metrics        — Ingestion metrics alias

Usage:
    cd Backend Monorepo/Backend
    uv run python -m pytest app/modules/dip/tests/test_dip_ingestion.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.dip.routes.ingestion import router as dip_ingestion_router

# ── Sample data ──────────────────────────────────────────────────────────

SAMPLE_PARSERS = [
    {
        "id": "pypdf",
        "label": "PyPDF2",
        "description": "Fast PDF text extraction",
        "supports": ["pdf"],
        "mode": "text",
    },
    {
        "id": "pdfplumber",
        "label": "pdfplumber",
        "description": "Table & layout preservation",
        "supports": ["pdf"],
        "mode": "hybrid",
    },
    {
        "id": "paddleocr",
        "label": "PaddleOCR",
        "description": "OCR for scanned PDFs",
        "supports": ["pdf", "image"],
        "mode": "ocr",
    },
]

SAMPLE_PROCESS_RESULT = {
    "results": [
        {
            "job_id": "job-1",
            "filename": "report.pdf",
            "status": "completed",
            "records": 250,
            "tokens": 1200,
            "text": "Extracted text content...",
        }
    ],
    "total": 1,
}

SAMPLE_STATUS = {
    "job_id": "job-1",
    "filename": "report.pdf",
    "status": "completed",
    "records": 250,
}

SAMPLE_SAVE_RESULT = {
    "success": True,
    "path": "/tmp/extracted/report_pypdf.txt",
    "filename": "report_pypdf.txt",
    "chars": 5000,
}

SAMPLE_STATS = {
    "documents_processed": 42,
    "total_chars": 1024000,
    "extraction_accuracy": 98.2,
    "active_connectors": 12,
    "throughput_gb_h": 4.5,
}

SAMPLE_SOURCES = [
    {
        "id": "local-uploads",
        "name": "Manual Uploads",
        "type": "Local Storage",
        "status": "active",
        "documents": 8976,
    },
    {
        "id": "s3-main",
        "name": "AWS S3 Main",
        "type": "S3 Bucket",
        "status": "connected",
        "documents": 45234,
    },
]

SAMPLE_DOCUMENTS = [
    {
        "document_id": "doc-1",
        "filename": "quarterly_report.pdf",
        "status": "completed",
        "created_at": "2026-01-15T10:00:00Z",
        "extraction_count": 3,
    },
    {
        "document_id": "doc-2",
        "filename": "technical_specs.docx",
        "status": "completed",
        "created_at": "2026-02-01T14:30:00Z",
        "extraction_count": 1,
    },
]

SAMPLE_DOCUMENT = {
    "document_id": "doc-1",
    "filename": "quarterly_report.pdf",
    "status": "completed",
    "created_at": "2026-01-15T10:00:00Z",
    "extractions": [
        {"parser": "pypdf", "text_length": 5000, "records": 250}
    ],
}

SAMPLE_COMPARE_RESULT = {
    "job_id": "cmp-1",
    "filename": "report.pdf",
    "results": [
        {
            "parser": "pypdf",
            "records": 250,
            "tokens": 1200,
            "latency_ms": 340,
            "confidence": 0.94,
            "complexity": "Medium",
        },
        {
            "parser": "pdfplumber",
            "records": 280,
            "tokens": 1350,
            "latency_ms": 510,
            "confidence": 0.94,
            "complexity": "Medium",
        },
    ],
}


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    """Create a sync TestClient with the DIP Ingestion router."""
    app = FastAPI()
    app.include_router(dip_ingestion_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture
def mock_process_documents() -> MagicMock:
    """Mock process_documents returning a known result."""
    mock = AsyncMock(return_value=SAMPLE_PROCESS_RESULT.copy())
    return mock


@pytest.fixture
def mock_compare_content() -> MagicMock:
    """Mock parse_file_with_comparator_content returning a known result."""
    mock = AsyncMock(return_value=SAMPLE_COMPARE_RESULT.copy())
    return mock


@pytest.fixture
def mock_get_status() -> MagicMock:
    """Mock get_processing_status."""
    mock = AsyncMock(return_value=SAMPLE_STATUS.copy())
    return mock


@pytest.fixture
def mock_list_parsers() -> MagicMock:
    """Mock list_parsers."""
    mock = AsyncMock(return_value=SAMPLE_PARSERS.copy())
    return mock


@pytest.fixture
def mock_save_text() -> MagicMock:
    """Mock save_extracted_text."""
    mock = AsyncMock(return_value=SAMPLE_SAVE_RESULT.copy())
    return mock


@pytest.fixture
def mock_get_stats() -> MagicMock:
    """Mock get_extraction_stats."""
    mock = AsyncMock(return_value=SAMPLE_STATS.copy())
    return mock


@pytest.fixture
def mock_get_sources() -> MagicMock:
    """Mock get_ingestion_sources."""
    mock = AsyncMock(return_value=SAMPLE_SOURCES.copy())
    return mock


@pytest.fixture
def mock_list_docs() -> MagicMock:
    """Mock list_documents."""
    mock = MagicMock(return_value=SAMPLE_DOCUMENTS.copy())
    return mock


@pytest.fixture
def mock_get_doc() -> MagicMock:
    """Mock get_document."""
    mock = MagicMock(return_value=SAMPLE_DOCUMENT.copy())
    return mock


@pytest.fixture
def mock_delete_doc() -> MagicMock:
    """Mock delete_document returning True."""
    mock = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_rename_doc() -> MagicMock:
    """Mock rename_document returning True."""
    mock = MagicMock(return_value=True)
    return mock


# ═══════════════════════════════════════════════════════════════════════════
# POST /process
# ═══════════════════════════════════════════════════════════════════════════


class TestProcessEndpoint:
    """POST /api/v1/dip/ingestion/process — upload and process documents."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.process_documents"

    def test_process_returns_job_results(
        self, client: TestClient, mock_process_documents: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_process_documents):
            response = client.post(
                "/api/v1/dip/ingestion/process",
                files=[("files", ("test.pdf", b"%PDF-1.4 mock content", "application/pdf"))],
                data={"parser": "pypdf", "compare_mode": False, "output_dest": "raw"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["results"]) == 1
        assert body["results"][0]["filename"] == "report.pdf"
        assert body["results"][0]["status"] == "completed"

    def test_process_delegates_correct_params(
        self, client: TestClient, mock_process_documents: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_process_documents) as mock:
            client.post(
                "/api/v1/dip/ingestion/process",
                files=[("files", ("test.pdf", b"data", "application/pdf"))],
                data={"parser": "pdfplumber", "compare_mode": True, "output_dest": "vault"},
            )
            mock.assert_awaited_once()
            args, kwargs = mock.call_args
            # First positional arg is the files list
            assert isinstance(args[0], list)
            # Second positional is parser string
            assert "pdfplumber" in args
            # Third positional is compare_mode bool
            assert True in args or "compare_mode" in kwargs

    def test_process_handles_multiple_files(
        self, client: TestClient, mock_process_documents: MagicMock
    ) -> None:
        multi_result = {
            "results": [
                {"job_id": "j1", "filename": "a.pdf", "status": "completed", "records": 100, "tokens": 500, "text": "..."},
                {"job_id": "j2", "filename": "b.pdf", "status": "completed", "records": 200, "tokens": 1000, "text": "..."},
            ],
            "total": 2,
        }
        mock_process_documents.return_value = multi_result
        with patch(self.MODULE_PATH, mock_process_documents):
            response = client.post(
                "/api/v1/dip/ingestion/process",
                files=[
                    ("files", ("a.pdf", b"content-a", "application/pdf")),
                    ("files", ("b.pdf", b"content-b", "text/plain")),
                ],
                data={"parser": "pypdf"},
            )
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_process_uses_default_parser(
        self, client: TestClient, mock_process_documents: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_process_documents) as mock:
            response = client.post(
                "/api/v1/dip/ingestion/process",
                files=[("files", ("doc.txt", b"hello", "text/plain"))],
            )
        assert response.status_code == 200
        mock.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════
# POST /compare
# ═══════════════════════════════════════════════════════════════════════════


class TestCompareEndpoint:
    """POST /api/v1/dip/ingestion/compare — compare parsers via background task."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.parse_file_with_comparator_content"

    def test_compare_returns_job_metadata(
        self, client: TestClient, mock_compare_content: MagicMock
    ) -> None:
        # Patch inside the compare handler to verify job is started
        with patch(self.MODULE_PATH, mock_compare_content):
            response = client.post(
                "/api/v1/dip/ingestion/compare",
                files=[("file", ("report.pdf", b"%PDF-1.4 data", "application/pdf"))],
            )
        assert response.status_code == 200
        body = response.json()
        assert "job_id" in body
        assert body["filename"] == "report.pdf"
        assert body["status"] == "started"

    def test_compare_with_custom_parsers(
        self, client: TestClient
    ) -> None:
        with patch(self.MODULE_PATH, AsyncMock()):
            response = client.post(
                "/api/v1/dip/ingestion/compare",
                files=[("file", ("doc.pdf", b"data", "application/pdf"))],
                data={"parsers": "pypdf,pdfplumber,paddleocr"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "started"

    def test_compare_without_parsers_uses_default(
        self, client: TestClient
    ) -> None:
        mock = AsyncMock()
        with patch(self.MODULE_PATH, mock):
            response = client.post(
                "/api/v1/dip/ingestion/compare",
                files=[("file", ("doc.pdf", b"data", "application/pdf"))],
            )
        assert response.status_code == 200
        assert response.json()["status"] == "started"


# ═══════════════════════════════════════════════════════════════════════════
# GET /compare/stream
# ═══════════════════════════════════════════════════════════════════════════


class TestCompareStreamEndpoint:
    """GET /api/v1/dip/ingestion/compare/stream — SSE stream."""

    def test_compare_stream_returns_sse(
        self, client: TestClient
    ) -> None:
        """The stream endpoint returns a StreamingResponse with event-stream content type."""
        # Patch stream_notifications to return an empty async generator
        async def _empty_gen():
            return
            yield  # pragma: no cover

        with patch(
            "app.modules.dip.routes.ingestion.stream_notifications",
            return_value=_empty_gen(),
        ):
            response = client.get("/api/v1/dip/ingestion/compare/stream")
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/event-stream")
        assert response.headers.get("cache-control") == "no-cache"




# ═══════════════════════════════════════════════════════════════════════════
# GET /status/{job_id}
# ═══════════════════════════════════════════════════════════════════════════


class TestStatusEndpoint:
    """GET /api/v1/dip/ingestion/status/{job_id} — processing status."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.get_processing_status"

    def test_get_status_returns_job_info(
        self, client: TestClient, mock_get_status: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_status):
            response = client.get("/api/v1/dip/ingestion/status/job-1")
        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == "job-1"
        assert body["status"] == "completed"
        assert body["records"] == 250

    def test_get_status_delegates_correctly(
        self, client: TestClient, mock_get_status: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_status) as mock:
            client.get("/api/v1/dip/ingestion/status/job-custom-42")
            mock.assert_awaited_once_with("job-custom-42")

    def test_get_status_not_found(
        self, client: TestClient
    ) -> None:
        mock = AsyncMock(return_value={"error": "Job not found"})
        with patch(self.MODULE_PATH, mock):
            response = client.get("/api/v1/dip/ingestion/status/unknown-job")
        assert response.status_code == 200
        assert response.json()["error"] == "Job not found"


# ═══════════════════════════════════════════════════════════════════════════
# GET /parsers
# ═══════════════════════════════════════════════════════════════════════════


class TestParsersEndpoint:
    """GET /api/v1/dip/ingestion/parsers — list available parsers."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.list_parsers"

    def test_list_parsers_returns_parsers(
        self, client: TestClient, mock_list_parsers: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_list_parsers):
            response = client.get("/api/v1/dip/ingestion/parsers")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 3
        assert body[0]["id"] == "pypdf"
        assert body[0]["label"] == "PyPDF2"
        assert "pdf" in body[0]["supports"]

    def test_list_parsers_has_required_fields(
        self, client: TestClient, mock_list_parsers: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_list_parsers):
            response = client.get("/api/v1/dip/ingestion/parsers")
        for parser in response.json():
            assert "id" in parser
            assert "label" in parser
            assert "description" in parser
            assert "supports" in parser
            assert "mode" in parser

    def test_list_parsers_delegates(
        self, client: TestClient, mock_list_parsers: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_list_parsers) as mock:
            client.get("/api/v1/dip/ingestion/parsers")
            mock.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════
# POST /save
# ═══════════════════════════════════════════════════════════════════════════


class TestSaveEndpoint:
    """POST /api/v1/dip/ingestion/save — save extraction results."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.save_extracted_text"

    def test_save_returns_result(
        self, client: TestClient, mock_save_text: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_save_text):
            response = client.post(
                "/api/v1/dip/ingestion/save",
                data={
                    "text": "Extracted content here",
                    "parser": "pypdf",
                    "filename": "document.txt",
                    "destination": "local",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["chars"] == 5000

    def test_save_with_metadata(
        self, client: TestClient, mock_save_text: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_save_text):
            response = client.post(
                "/api/v1/dip/ingestion/save",
                data={
                    "text": "Content",
                    "parser": "pypdf",
                    "filename": "doc.pdf",
                    "destination": "vault",
                    "metadata": '{"source": "api-test", "tags": ["test"]}',
                    "content_type": "application/pdf",
                },
                files={"file_content": b"binary content"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_save_invalid_metadata_does_not_crash(
        self, client: TestClient, mock_save_text: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_save_text) as mock:
            response = client.post(
                "/api/v1/dip/ingestion/save",
                data={
                    "text": "Content",
                    "parser": "plain-text",
                    "filename": "notes.txt",
                    "destination": "local",
                    "metadata": "not-valid-json",
                },
            )
        assert response.status_code == 200
        # Handler catches JSONError and passes metadata=None
        mock.assert_awaited_once()
        _args, kwargs = mock.call_args
        assert kwargs.get("metadata") is None or kwargs.get("metadata") == {}
        # extraction_results should also be None since not provided
        assert kwargs.get("extraction_results") is None

    def test_save_without_text_returns_422(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/v1/dip/ingestion/save",
            data={"parser": "pypdf", "filename": "doc.txt", "destination": "local"},
        )
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# GET /stats
# ═══════════════════════════════════════════════════════════════════════════


class TestStatsEndpoint:
    """GET /api/v1/dip/ingestion/stats — extraction statistics."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.get_extraction_stats"

    def test_get_stats_returns_expected_fields(
        self, client: TestClient, mock_get_stats: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_stats):
            response = client.get("/api/v1/dip/ingestion/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["documents_processed"] == 42
        assert data["total_chars"] == 1024000
        assert data["extraction_accuracy"] == 98.2
        assert data["active_connectors"] == 12
        assert data["throughput_gb_h"] == 4.5

    def test_get_stats_delegates(
        self, client: TestClient, mock_get_stats: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_stats) as mock:
            client.get("/api/v1/dip/ingestion/stats")
            mock.assert_awaited_once()

    def test_get_stats_all_keys_present(
        self, client: TestClient, mock_get_stats: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_stats):
            response = client.get("/api/v1/dip/ingestion/stats")
        keys = set(response.json().keys())
        expected = {"documents_processed", "total_chars", "extraction_accuracy",
                     "active_connectors", "throughput_gb_h"}
        assert keys == expected


# ═══════════════════════════════════════════════════════════════════════════
# GET /sources
# ═══════════════════════════════════════════════════════════════════════════


class TestSourcesEndpoint:
    """GET /api/v1/dip/ingestion/sources — list ingestion sources."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.get_ingestion_sources"

    def test_get_sources_returns_sources(
        self, client: TestClient, mock_get_sources: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_sources):
            response = client.get("/api/v1/dip/ingestion/sources")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["id"] == "local-uploads"
        assert body[0]["type"] == "Local Storage"

    def test_get_sources_has_required_fields(
        self, client: TestClient, mock_get_sources: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_sources):
            response = client.get("/api/v1/dip/ingestion/sources")
        for source in response.json():
            assert "id" in source
            assert "name" in source
            assert "type" in source
            assert "status" in source
            assert "documents" in source

    def test_get_sources_delegates(
        self, client: TestClient, mock_get_sources: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_sources) as mock:
            client.get("/api/v1/dip/ingestion/sources")
            mock.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════
# Vault Endpoints
# ═══════════════════════════════════════════════════════════════════════════


class TestVaultListEndpoint:
    """GET /api/v1/dip/ingestion/vault — list vault documents."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.list_documents"

    def test_vault_list_returns_documents(
        self, client: TestClient, mock_list_docs: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_list_docs):
            response = client.get("/api/v1/dip/ingestion/vault")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["document_id"] == "doc-1"
        assert body[0]["filename"] == "quarterly_report.pdf"

    def test_vault_list_has_required_fields(
        self, client: TestClient, mock_list_docs: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_list_docs):
            response = client.get("/api/v1/dip/ingestion/vault")
        for doc in response.json():
            assert "document_id" in doc
            assert "filename" in doc
            assert "status" in doc
            assert "created_at" in doc

    def test_vault_list_passes_limit(
        self, client: TestClient
    ) -> None:
        mock = MagicMock(return_value=SAMPLE_DOCUMENTS[:1])
        with patch(self.MODULE_PATH, mock) as mock_list:
            response = client.get("/api/v1/dip/ingestion/vault?limit=1")
        assert response.status_code == 200
        mock_list.assert_called_once_with(1)
        assert len(response.json()) == 1

    def test_vault_list_empty(
        self, client: TestClient
    ) -> None:
        mock = MagicMock(return_value=[])
        with patch(self.MODULE_PATH, mock):
            response = client.get("/api/v1/dip/ingestion/vault")
        assert response.status_code == 200
        assert response.json() == []


class TestVaultGetEndpoint:
    """GET /api/v1/dip/ingestion/vault/{document_id} — get single document."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.get_document"

    def test_vault_get_returns_document(
        self, client: TestClient, mock_get_doc: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_doc):
            response = client.get("/api/v1/dip/ingestion/vault/doc-1")
        assert response.status_code == 200
        body = response.json()
        assert body["document_id"] == "doc-1"
        assert body["filename"] == "quarterly_report.pdf"
        assert "extractions" in body

    def test_vault_get_returns_404_on_missing(
        self, client: TestClient
    ) -> None:
        mock = MagicMock(return_value=None)
        with patch(self.MODULE_PATH, mock):
            response = client.get("/api/v1/dip/ingestion/vault/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_vault_get_delegates_correct_id(
        self, client: TestClient, mock_get_doc: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_doc) as mock:
            client.get("/api/v1/dip/ingestion/vault/custom-doc-id")
            mock.assert_called_once_with("custom-doc-id")


class TestVaultDeleteEndpoint:
    """DELETE /api/v1/dip/ingestion/vault/{document_id} — delete document."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.delete_document"

    def test_vault_delete_returns_success(
        self, client: TestClient, mock_delete_doc: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_delete_doc):
            response = client.delete("/api/v1/dip/ingestion/vault/doc-1")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_vault_delete_returns_404_on_missing(
        self, client: TestClient
    ) -> None:
        mock = MagicMock(return_value=False)
        with patch(self.MODULE_PATH, mock):
            response = client.delete("/api/v1/dip/ingestion/vault/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_vault_delete_delegates_correct_id(
        self, client: TestClient, mock_delete_doc: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_delete_doc) as mock:
            client.delete("/api/v1/dip/ingestion/vault/doc-to-delete")
            mock.assert_called_once_with("doc-to-delete")


class TestVaultRenameEndpoint:
    """POST /api/v1/dip/ingestion/vault/{document_id}/rename — rename document."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.rename_document"

    def test_vault_rename_returns_success(
        self, client: TestClient, mock_rename_doc: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_rename_doc):
            response = client.post(
                "/api/v1/dip/ingestion/vault/doc-1/rename",
                data={"new_filename": "renamed_report.pdf"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_vault_rename_returns_404_on_missing(
        self, client: TestClient
    ) -> None:
        mock = MagicMock(return_value=False)
        with patch(self.MODULE_PATH, mock):
            response = client.post(
                "/api/v1/dip/ingestion/vault/nonexistent/rename",
                data={"new_filename": "new_name.pdf"},
            )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_vault_rename_delegates_correctly(
        self, client: TestClient, mock_rename_doc: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_rename_doc) as mock:
            client.post(
                "/api/v1/dip/ingestion/vault/doc-42/rename",
                data={"new_filename": "updated.pdf"},
            )
            mock.assert_called_once_with("doc-42", "updated.pdf")


# ═══════════════════════════════════════════════════════════════════════════
# POST /upload
# ═══════════════════════════════════════════════════════════════════════════


class TestUploadEndpoint:
    """POST /api/v1/dip/ingestion/upload — simple upload for UI wizard."""

    MODULE_PATH = "app.modules.dip.routes.ingestion.process_documents"

    def test_upload_returns_data_and_status(
        self, client: TestClient, mock_process_documents: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_process_documents):
            response = client.post(
                "/api/v1/dip/ingestion/upload",
                files=[("file", ("doc.pdf", b"content", "application/pdf"))],
                data={"parser": "pypdf"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "uploaded"
        assert "data" in body
        assert body["data"]["total"] == 1

    def test_upload_with_parser(
        self, client: TestClient, mock_process_documents: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_process_documents) as mock:
            client.post(
                "/api/v1/dip/ingestion/upload",
                files=[("file", ("specs.pdf", b"data", "application/pdf"))],
                data={"parser": "docling"},
            )
            # process_documents should be called with parser="docling"
            _args, kwargs = mock.call_args
            # parser is the 2nd positional arg or a keyword
            assert kwargs.get("parser") == "docling" or _args[1] == "docling"


# ═══════════════════════════════════════════════════════════════════════════
# GET /jobs
# ═══════════════════════════════════════════════════════════════════════════


class TestJobsEndpoint:
    """GET /api/v1/dip/ingestion/jobs — list ingestion jobs (hardcoded)."""

    def test_list_jobs_returns_hardcoded_data(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/dip/ingestion/jobs")
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert len(body["data"]) == 2

    def test_list_jobs_has_required_fields(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/dip/ingestion/jobs")
        for job in response.json()["data"]:
            assert "id" in job
            assert "name" in job
            assert "status" in job
            assert "progress" in job

    def test_list_jobs_has_completed_and_processing(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/dip/ingestion/jobs")
        statuses = {j["status"] for j in response.json()["data"]}
        assert "completed" in statuses
        assert "processing" in statuses

    def test_list_jobs_progress_is_integer(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/dip/ingestion/jobs")
        for job in response.json()["data"]:
            assert isinstance(job["progress"], int)
            assert 0 <= job["progress"] <= 100


# ═══════════════════════════════════════════════════════════════════════════
# GET /metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestMetricsEndpoint:
    """GET /api/v1/dip/ingestion/metrics — alias for /stats."""

    # The /metrics endpoint does a local import:
    #   from common_lib.modules.dip.ingestion.controller import get_extraction_stats
    # Patch at the controller module path so the local import picks it up.
    MODULE_PATH = "common_lib.modules.dip.ingestion.controller.get_extraction_stats"

    def test_get_metrics_returns_stats(
        self, client: TestClient, mock_get_stats: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_stats):
            response = client.get("/api/v1/dip/ingestion/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["documents_processed"] == 42
        assert data["total_chars"] == 1024000
        assert data["extraction_accuracy"] == 98.2

    def test_get_metrics_delegates(
        self, client: TestClient, mock_get_stats: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_stats) as mock:
            client.get("/api/v1/dip/ingestion/metrics")
            mock.assert_awaited_once()

    def test_get_metrics_has_all_keys(
        self, client: TestClient, mock_get_stats: MagicMock
    ) -> None:
        with patch(self.MODULE_PATH, mock_get_stats):
            response = client.get("/api/v1/dip/ingestion/metrics")
        keys = set(response.json().keys())
        expected = {"documents_processed", "total_chars", "extraction_accuracy",
                     "active_connectors", "throughput_gb_h"}
        assert keys == expected

    def test_get_metrics_error_handling(
        self, client: TestClient
    ) -> None:
        # Simulate the controller's fallback behavior when errors occur
        mock = AsyncMock(return_value={
            "documents_processed": 0,
            "total_chars": 0,
            "extraction_accuracy": 0,
            "active_connectors": 0,
            "throughput_gb_h": 0,
        })
        with patch(self.MODULE_PATH, mock):
            response = client.get("/api/v1/dip/ingestion/metrics")
        assert response.status_code == 200
        assert response.json()["documents_processed"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# OPTIONS / CORS test (routing integrity)
# ═══════════════════════════════════════════════════════════════════════════


class TestRoutingIntegrity:
    """Verify all routes are mounted at expected paths."""

    def test_all_ingestion_routes_registered(
        self, client: TestClient
    ) -> None:
        """OpenAPI schema includes all ingestion endpoints."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        ingestion_paths = {
            path for path in paths if "dip/ingestion" in path
        }
        expected_prefixes = {
            "/process",
            "/compare",
            "/compare/stream",
            "/status/",
            "/parsers",
            "/save",
            "/stats",
            "/sources",
            "/vault",
            "/upload",
            "/jobs",
            "/metrics",
        }
        # At minimum we should have most of these
        matching_paths = {
            p for p in ingestion_paths
            if any(ep in p for ep in expected_prefixes)
        }
        assert len(matching_paths) >= 10, (
            f"Expected at least 10 ingestion paths, got {len(matching_paths)}: {matching_paths}"
        )
