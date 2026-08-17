"""MCP tools for Doc Processing — PDF extraction + universal document ops.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.doc_processing services.
"""

import logging
from typing import Any, Dict, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.doc_processing")


def _get_svc():
    from common_lib.modules.doc_processing.service._service import (
        DocProcessingService,
    )

    return DocProcessingService()


def register_doc_processing_tools(mcp: FastMCP):
    """Register tools for document processing."""

    # ── PDF Extraction (legacy) ──────────────────────────────────────

    @mcp.tool()
    async def doc_extract_full(
        file_path: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Full PDF extraction (text + metadata + tables)."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import (
                PDFExtractionPipeline,
            )

            svc = PDFExtractionPipeline()
            result = (
                svc.extract(file_path, **(options or {}))
                if hasattr(svc, "extract")
                else {"file": file_path}
            )
            return result if isinstance(result, dict) else {"file": file_path}
        except Exception as e:
            logger.error(f"doc_extract_full error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_extract_text(
        file_path: str, pages: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract text content from a PDF."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import (
                PDFExtractionPipeline,
            )

            svc = PDFExtractionPipeline()
            result = (
                svc.extract_text(file_path, pages=pages)
                if hasattr(svc, "extract_text")
                else {"text": ""}
            )
            return result if isinstance(result, dict) else {"text": str(result)}
        except Exception as e:
            logger.error(f"doc_extract_text error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_extract_tables(
        file_path: str, pages: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract tables from a PDF."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import (
                PDFExtractionPipeline,
            )

            svc = PDFExtractionPipeline()
            result = (
                svc.extract_tables(file_path, pages=pages)
                if hasattr(svc, "extract_tables")
                else {"tables": []}
            )
            return (
                result
                if isinstance(result, dict)
                else {"tables": result if isinstance(result, list) else []}
            )
        except Exception as e:
            logger.error(f"doc_extract_tables error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_pdf_metadata(file_path: str) -> Dict[str, Any]:
        """Extract metadata from a PDF (author, title, pages, etc)."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import (
                PDFExtractionPipeline,
            )

            svc = PDFExtractionPipeline()
            result = (
                svc.extract_metadata(file_path)
                if hasattr(svc, "extract_metadata")
                else {"metadata": {}}
            )
            return result if isinstance(result, dict) else {"metadata": result}
        except Exception as e:
            logger.error(f"doc_pdf_metadata error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_list_parsers() -> Dict[str, Any]:
        """List available document parsers (PDF backends)."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import (
                PDFExtractionPipeline,
            )

            svc = PDFExtractionPipeline()
            result = svc.list_parsers() if hasattr(svc, "list_parsers") else []
            return {
                "parsers": result if isinstance(result, list) else [],
                "count": len(result) if isinstance(result, list) else 0,
            }
        except Exception as e:
            logger.error(f"doc_list_parsers error: {e}")
            return {"parsers": [], "error": str(e)}

    # ── Universal Document Operations (DocProcessingService) ────────

    @mcp.tool()
    async def doc_read_file(
        file_path: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Read any document file through the universal reader.
        Supports PDF, Word, Excel, text, JSON, CSV, and 20+ formats."""
        try:
            svc = _get_svc()
            result = svc.read(file_path, options)
            return {"result": result}
        except Exception as e:
            logger.error(f"doc_read_file error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_inspect_file(file_path: str) -> Dict[str, Any]:
        """Quickly inspect a document without full parsing.
        Returns size, type, structure info."""
        try:
            svc = _get_svc()
            result = svc.inspect(file_path)
            return {"result": result}
        except Exception as e:
            logger.error(f"doc_inspect_file error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_detect_format(file_path: str) -> Dict[str, Any]:
        """Detect the format of a file using extension, MIME, and magic
        bytes."""
        try:
            svc = _get_svc()
            result = svc.detect(file_path)
            return {"result": result}
        except Exception as e:
            logger.error(f"doc_detect_format error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_security_scan(
        file_path: str, policy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run security checks on a file before processing.
        Scans for macros, embedded objects, and suspicious patterns."""
        try:
            svc = _get_svc()
            result = svc.security_scan(file_path, policy)
            return {"result": result}
        except Exception as e:
            logger.error(f"doc_security_scan error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_list_formats() -> Dict[str, Any]:
        """List all registered document format handlers."""
        try:
            svc = _get_svc()
            formats = svc.list_formats()
            return {"formats": formats, "count": len(formats)}
        except Exception as e:
            logger.error(f"doc_list_formats error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_file_metadata(file_path: str) -> Dict[str, Any]:
        """Extract metadata from a file (size, hashes, timestamps).
        Works on any file type."""
        try:
            svc = _get_svc()
            basic = svc.extract_metadata(file_path)
            hashes = svc.extract_hashes(file_path)
            return {"result": {**basic, "hashes": hashes}}
        except Exception as e:
            logger.error(f"doc_file_metadata error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_chunk_text(
        text: str,
        strategy: str = "paragraph",
        max_size: int = 1000,
        overlap: int = 100,
    ) -> Dict[str, Any]:
        """Split text into chunks for AI processing.
        Strategies: paragraph, sentence, token, heading, fixed."""
        try:
            svc = _get_svc()
            params = {"max_chunk_size": max_size, "overlap": overlap}
            result = svc.chunk_document(text, method=strategy, **params)
            return {"chunks": result, "count": len(result), "strategy": strategy}
        except Exception as e:
            logger.error(f"doc_chunk_text error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_diff_texts(text_a: str, text_b: str) -> Dict[str, Any]:
        """Compare two text documents and return structured differences."""
        try:
            svc = _get_svc()
            result = svc.diff_text(text_a, text_b)
            return {"result": result}
        except Exception as e:
            logger.error(f"doc_diff_texts error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_archive_inspect(archive_path: str) -> Dict[str, Any]:
        """List contents of an archive (ZIP, TAR, GZIP, etc.) without
        extracting."""
        try:
            svc = _get_svc()
            result = svc.inspect_archive(archive_path)
            return {"result": result}
        except Exception as e:
            logger.error(f"doc_archive_inspect error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_archive_extract(archive_path: str, dest_dir: str) -> Dict[str, Any]:
        """Extract archive contents securely with zip-bomb and
        path-traversal protection."""
        try:
            svc = _get_svc()
            result = svc.extract_archive(archive_path, dest_dir)
            return {"result": result}
        except Exception as e:
            logger.error(f"doc_archive_extract error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_search_text(
        text: str, query: str, case_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Search for keywords or patterns in document text."""
        try:
            svc = _get_svc()
            result = svc.search_content(text, query, case_sensitive)
            return {"results": result, "count": len(result)}
        except Exception as e:
            logger.error(f"doc_search_text error: {e}")
            return {"error": str(e)}

    logger.info("Registered %d doc_processing MCP tools", 5 + 11)
