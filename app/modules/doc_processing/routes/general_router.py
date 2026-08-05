"""DocProcessingService REST API routes — universal document operations.

Thin routing layer over common_lib.modules.doc_processing.service.DocProcessingService.
Covers file read/inspect/detect/scan, format listing, archive ops,
cross-cutting search/chunk/diff/metadata, and job management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================================
# Schemas
# =========================================================================


class FilePathRequest(BaseModel):
    file_path: str


class ReadRequest(BaseModel):
    file_path: str
    options: Optional[Dict[str, Any]] = None


class SecurityScanRequest(BaseModel):
    file_path: str
    policy: Optional[str] = None


class ArchiveExtractRequest(BaseModel):
    archive_path: str
    dest_dir: str
    policy: Optional[Dict[str, Any]] = None


class ArchiveReadRecursiveRequest(BaseModel):
    archive_path: str
    options: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    text: str
    query: str
    case_sensitive: bool = False


class ChunkRequest(BaseModel):
    text: str
    strategy: str = "paragraph"
    params: Dict[str, Any] = Field(default_factory=dict)


class DiffRequest(BaseModel):
    text_a: str
    text_b: str


class CreateJobRequest(BaseModel):
    job_type: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ListJobsRequest(BaseModel):
    status: Optional[str] = None


# =========================================================================
# Helpers
# =========================================================================


def _get_svc():
    from common_lib.modules.doc_processing.service._service import (
        DocProcessingService,
    )

    svc = DocProcessingService()
    return svc


# =========================================================================
# File Operations
# =========================================================================


@router.post("/files/read", summary="Read any document file")
async def read_file(req: ReadRequest) -> Dict[str, Any]:
    """Read any document through the universal reader. Supports PDF, Word,
    Excel, text, JSON, CSV, and 20+ formats."""
    try:
        svc = _get_svc()
        result = svc.read(req.file_path, req.options)
        return {"result": result}
    except Exception as e:
        logger.error("read_file failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/inspect", summary="Inspect a document without full parsing")
async def inspect_file(req: FilePathRequest) -> Dict[str, Any]:
    """Quickly inspect a document: size, type, page count, structure."""
    try:
        svc = _get_svc()
        result = svc.inspect(req.file_path)
        return {"result": result}
    except Exception as e:
        logger.error("inspect_file failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/detect", summary="Detect document format")
async def detect_format(req: FilePathRequest) -> Dict[str, Any]:
    """Detect the format of a file using extension, MIME, and magic bytes."""
    try:
        svc = _get_svc()
        result = svc.detect(req.file_path)
        return {"result": result}
    except Exception as e:
        logger.error("detect_format failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/security-scan", summary="Run security checks on a file")
async def security_scan(req: SecurityScanRequest) -> Dict[str, Any]:
    """Run security checks on a file before processing (macros, embedded
    objects, suspicious patterns)."""
    try:
        svc = _get_svc()
        result = svc.security_scan(req.file_path, req.policy)
        return {"result": result}
    except Exception as e:
        logger.error("security_scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Format Operations
# =========================================================================


@router.get("/formats", summary="List all registered document formats")
async def list_formats() -> Dict[str, Any]:
    """List all registered document format handlers with their metadata."""
    try:
        svc = _get_svc()
        formats = svc.list_formats()
        return {"formats": formats, "count": len(formats)}
    except Exception as e:
        logger.error("list_formats failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/formats/{format_id}/capabilities",
    summary="Get format capabilities",
)
async def get_format_capabilities(format_id: str) -> Dict[str, Any]:
    """Get capabilities for a specific format handler."""
    try:
        svc = _get_svc()
        result = svc.get_format_capabilities(format_id)
        return {"result": result}
    except Exception as e:
        logger.error("get_format_capabilities failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Archive Operations
# =========================================================================


@router.post("/archives/inspect", summary="Inspect an archive")
async def inspect_archive(req: FilePathRequest) -> Dict[str, Any]:
    """List contents of an archive (ZIP, TAR, GZIP, etc.) without extracting."""
    try:
        svc = _get_svc()
        result = svc.inspect_archive(req.file_path)
        return {"result": result}
    except Exception as e:
        logger.error("inspect_archive failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archives/extract", summary="Extract an archive")
async def extract_archive(req: ArchiveExtractRequest) -> Dict[str, Any]:
    """Extract archive contents securely with zip-bomb and path-traversal
    protection."""
    try:
        svc = _get_svc()
        result = svc.extract_archive(req.archive_path, req.dest_dir, req.policy)
        return {"result": result}
    except Exception as e:
        logger.error("extract_archive failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/archives/read-recursive",
    summary="Read an archive recursively",
)
async def read_archive_recursive(
    req: ArchiveReadRecursiveRequest,
) -> Dict[str, Any]:
    """Read all files inside an archive recursively through the universal
    reader."""
    try:
        svc = _get_svc()
        result = svc.read_archive(req.archive_path, req.options)
        return {"result": result}
    except Exception as e:
        logger.error("read_archive_recursive failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Cross-Cutting Services
# =========================================================================


@router.post("/documents/search", summary="Search document text")
async def search_document(req: SearchRequest) -> Dict[str, Any]:
    """Search for keywords or patterns in document text."""
    try:
        svc = _get_svc()
        result = svc.search_content(req.text, req.query, req.case_sensitive)
        return {"result": result}
    except Exception as e:
        logger.error("search_document failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/chunk", summary="Chunk document text")
async def chunk_document(req: ChunkRequest) -> Dict[str, Any]:
    """Split text into chunks for AI processing. Strategies: paragraph,
    sentence, token, heading, fixed."""
    try:
        svc = _get_svc()
        result = svc.chunk_document(req.text, method=req.strategy, **req.params)
        return {"result": result}
    except Exception as e:
        logger.error("chunk_document failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/diff", summary="Diff two text documents")
async def diff_documents(req: DiffRequest) -> Dict[str, Any]:
    """Compare two text documents and return structured differences."""
    try:
        svc = _get_svc()
        result = svc.diff_text(req.text_a, req.text_b)
        return {"result": result}
    except Exception as e:
        logger.error("diff_documents failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/documents/extract-metadata",
    summary="Extract metadata from a file",
)
async def extract_file_metadata(req: FilePathRequest) -> Dict[str, Any]:
    """Extract metadata from a file: size, hashes, timestamps, format info."""
    try:
        svc = _get_svc()
        basic = svc.extract_metadata(req.file_path)
        hashes = svc.extract_hashes(req.file_path)
        return {"result": {**basic, "hashes": hashes}}
    except Exception as e:
        logger.error("extract_file_metadata failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Job Operations
# =========================================================================


@router.post("/jobs", summary="Create a processing job")
async def create_job(req: CreateJobRequest) -> Dict[str, Any]:
    """Create a new document processing job."""
    try:
        svc = _get_svc()
        job_id = svc.create_job(req.job_type, req.params)
        return {"job_id": job_id}
    except Exception as e:
        logger.error("create_job failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", summary="Get job status")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """Get the status of a document processing job."""
    try:
        svc = _get_svc()
        result = svc.get_job_status(job_id)
        return {"result": result}
    except Exception as e:
        logger.error("get_job_status failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", summary="List document processing jobs")
async def list_jobs(status: Optional[str] = None) -> Dict[str, Any]:
    """List all document processing jobs, optionally filtered by status."""
    try:
        svc = _get_svc()
        result = svc.list_jobs(status)
        return {"jobs": result, "count": len(result)}
    except Exception as e:
        logger.error("list_jobs failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
