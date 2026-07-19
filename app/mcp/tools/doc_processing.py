"""MCP tools for Doc Processing — PDF extraction, text, metadata, tables.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.doc_processing services.
"""

import logging
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.doc_processing")


def register_doc_processing_tools(mcp: FastMCP):
    """Register tools for document processing."""

    @mcp.tool()
    async def doc_extract_full(file_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Full PDF extraction (text + metadata + tables)."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.extract(file_path, **(options or {})) if hasattr(svc, "extract") else {"file": file_path}
            return result if isinstance(result, dict) else {"file": file_path}
        except Exception as e:
            logger.error(f"doc_extract_full error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_extract_text(file_path: str, pages: Optional[str] = None) -> Dict[str, Any]:
        """Extract text content from a PDF."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.extract_text(file_path, pages=pages) if hasattr(svc, "extract_text") else {"text": ""}
            return result if isinstance(result, dict) else {"text": str(result)}
        except Exception as e:
            logger.error(f"doc_extract_text error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_extract_tables(file_path: str, pages: Optional[str] = None) -> Dict[str, Any]:
        """Extract tables from a PDF."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.extract_tables(file_path, pages=pages) if hasattr(svc, "extract_tables") else {"tables": []}
            return result if isinstance(result, dict) else {"tables": result if isinstance(result, list) else []}
        except Exception as e:
            logger.error(f"doc_extract_tables error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_extract_metadata(file_path: str) -> Dict[str, Any]:
        """Extract metadata from a PDF."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.extract_metadata(file_path) if hasattr(svc, "extract_metadata") else {"metadata": {}}
            return result if isinstance(result, dict) else {"metadata": result}
        except Exception as e:
            logger.error(f"doc_extract_metadata error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def doc_list_parsers() -> Dict[str, Any]:
        """List available document parsers."""
        try:
            from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
            svc = PDFExtractionPipeline()
            result = svc.list_parsers() if hasattr(svc, "list_parsers") else []
            return {"parsers": result if isinstance(result, list) else [], "count": len(result) if isinstance(result, list) else 0}
        except Exception as e:
            logger.error(f"doc_list_parsers error: {e}")
            return {"parsers": [], "error": str(e)}

    logger.info("Doc Processing: 5 MCP tools registered")
