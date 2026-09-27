"""DIP (Document Ingestion Pipeline) background-job executors.

Moves blocking document processing operations OFF the FastAPI event loop onto the jobs module.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

INGESTION_PROCESS_KIND = "dip.ingestion.process"
INGESTION_PROCESS_DEVICE = "cpu"
INGESTION_PROCESS_TIMEOUT = 1800.0

INGESTION_COMPARE_KIND = "dip.ingestion.compare"
INGESTION_COMPARE_DEVICE = "cpu"
INGESTION_COMPARE_TIMEOUT = 600.0

EXTRACTION_PROCESS_KIND = "dip.extraction.process"
EXTRACTION_PROCESS_DEVICE = "cpu"
EXTRACTION_PROCESS_TIMEOUT = 600.0

EMBEDDINGS_GENERATE_KIND = "dip.embeddings.generate"
EMBEDDINGS_GENERATE_DEVICE = "gpu"
EMBEDDINGS_GENERATE_TIMEOUT = 1800.0

PIPELINE_RUN_KIND = "dip.pipeline.run"
PIPELINE_RUN_DEVICE = "cpu"
PIPELINE_RUN_TIMEOUT = 3600.0

RAG_QUERY_KIND = "dip.rag.query"
RAG_QUERY_DEVICE = "gpu"
RAG_QUERY_TIMEOUT = 300.0

KG_BUILD_KIND = "dip.kg.build"
KG_BUILD_DEVICE = "cpu"
KG_BUILD_TIMEOUT = 1800.0

STORAGE_SYNC_KIND = "dip.storage.sync"
STORAGE_SYNC_DEVICE = "cpu"
STORAGE_SYNC_TIMEOUT = 600.0


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _record_params(record: Any) -> dict[str, Any]:
    try:
        params: Any = record.get_params()
    except Exception:
        return {}
    return params if isinstance(params, dict) else {}


def _record_id(record: Any) -> str:
    try:
        job_id: Any = record.id
    except Exception:
        return "unknown"
    return str(job_id)


def _cancelled_result() -> dict[str, Any]:
    return {"result_refs": [], "status": "cancelled"}


async def _run_async(coro_factory: Callable[[], Any]) -> Any:
    import asyncio
    return asyncio.run(coro_factory())


def _finish(
    job_id: str,
    payload: dict[str, Any],
    *,
    extra_files: tuple[bytes, str] | tuple = (),
    status: str = "success",
) -> dict[str, Any]:
    from common_lib.modules.jobs.artifacts import save_artifact
    refs: list[str] = []
    for file_bytes, filename in extra_files:
        if file_bytes:
            refs.append(save_artifact(job_id, filename, file_bytes))
    clean: dict[str, Any] = dict(payload)
    clean["artifact_files"] = [r for r in refs if not r.endswith("result.json")]
    refs.append(save_artifact(job_id, "result.json", json.dumps(clean, default=str).encode("utf-8")))
    return {"result_refs": refs, "status": status}


# ---------------------------------------------------------------------------
# DIP operation executors
# ---------------------------------------------------------------------------


def ingestion_process_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``dip.ingestion.process`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    files_data = params.get("files", [])
    parser = params.get("parser", "pypdf")
    compare_mode = params.get("compare_mode", False)
    output_dest = params.get("output_dest", "raw")

    if not files_data:
        return _finish(job_id, {"error": "No files provided"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.dip.ingestion.controller import process_documents
    import base64
    import io

    # Reconstruct file objects from base64 data
    file_objects = []
    for f in files_data:
        content = base64.b64decode(f.get("content", ""))
        file_obj = io.BytesIO(content)
        file_obj.filename = f.get("filename", "unknown")
        file_obj.content_type = f.get("content_type", "application/octet-stream")
        file_objects.append(file_obj)

    result = _run_async(lambda: process_documents(file_objects, parser, compare_mode, output_dest))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def ingestion_compare_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``dip.ingestion.compare`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    file_content = params.get("file_content")
    filename = params.get("filename")
    parsers = params.get("parsers")

    if not file_content or not filename:
        return _finish(job_id, {"error": "Missing file_content or filename"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.dip.ingestion.controller import parse_file_with_comparator_content
    import base64

    content = base64.b64decode(file_content)
    parser_list = parsers.split(",") if parsers else None

    result = _run_async(lambda: parse_file_with_comparator_content(content, filename, parser_list, job_id=job_id))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def extraction_process_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``dip.extraction.process`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    text = params.get("text")
    parser = params.get("parser", "pypdf")
    filename = params.get("filename", "document.txt")
    destination = params.get("destination", "local")

    if not text:
        return _finish(job_id, {"error": "No text provided"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.dip.ingestion.controller import save_extracted_text

    result = _run_async(lambda: save_extracted_text(text, parser, filename, destination))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def embeddings_generate_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``dip.embeddings.generate`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    texts = params.get("texts", [])
    model = params.get("model", "default")

    if not texts:
        return _finish(job_id, {"error": "No texts provided"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.dip.embeddings.controller import generate_embeddings

    result = _run_async(lambda: generate_embeddings(texts, model))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def pipeline_run_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``dip.pipeline.run`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    name = params.get("name")
    workflow_yaml = params.get("workflow_yaml")
    source_folder = params.get("source_folder")
    output_dest = params.get("output_dest", "raw")

    if not name or not workflow_yaml or not source_folder:
        return _finish(job_id, {"error": "Missing required params"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.dip.pipeline.controller import run_pipeline

    result = _run_async(lambda: run_pipeline(name, workflow_yaml, source_folder, output_dest))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def rag_query_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``dip.rag.query`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    query = params.get("query")
    top_k = params.get("top_k", 5)

    if not query:
        return _finish(job_id, {"error": "Missing query"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.dip.rag.controller import query_rag

    result = _run_async(lambda: query_rag(query, top_k))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def kg_build_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``dip.kg.build`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    source = params.get("source")
    if not source:
        return _finish(job_id, {"error": "Missing source"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.dip.kg.controller import build_knowledge_graph

    result = _run_async(lambda: build_knowledge_graph(source))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def storage_sync_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``dip.storage.sync`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    source_id = params.get("source_id")
    if not source_id:
        return _finish(job_id, {"error": "Missing source_id"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.dip.ingestion.controller import sync_ingestion_source

    result = _run_async(lambda: sync_ingestion_source(source_id))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    (INGESTION_PROCESS_KIND, ingestion_process_executor, INGESTION_PROCESS_DEVICE, INGESTION_PROCESS_TIMEOUT),
    (INGESTION_COMPARE_KIND, ingestion_compare_executor, INGESTION_COMPARE_DEVICE, INGESTION_COMPARE_TIMEOUT),
    (EXTRACTION_PROCESS_KIND, extraction_process_executor, EXTRACTION_PROCESS_DEVICE, EXTRACTION_PROCESS_TIMEOUT),
    (EMBEDDINGS_GENERATE_KIND, embeddings_generate_executor, EMBEDDINGS_GENERATE_DEVICE, EMBEDDINGS_GENERATE_TIMEOUT),
    (PIPELINE_RUN_KIND, pipeline_run_executor, PIPELINE_RUN_DEVICE, PIPELINE_RUN_TIMEOUT),
    (RAG_QUERY_KIND, rag_query_executor, RAG_QUERY_DEVICE, RAG_QUERY_TIMEOUT),
    (KG_BUILD_KIND, kg_build_executor, KG_BUILD_DEVICE, KG_BUILD_TIMEOUT),
    (STORAGE_SYNC_KIND, storage_sync_executor, STORAGE_SYNC_DEVICE, STORAGE_SYNC_TIMEOUT),
)


def ensure_dip_executors_registered() -> bool:
    """Register all DIP executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:
        logger.warning("ensure_dip_executors_registered failed: %s", exc)
        return False


__all__ = [
    "EMBEDDINGS_GENERATE_DEVICE",
    "EMBEDDINGS_GENERATE_KIND",
    "EMBEDDINGS_GENERATE_TIMEOUT",
    "EXTRACTION_PROCESS_DEVICE",
    "EXTRACTION_PROCESS_KIND",
    "EXTRACTION_PROCESS_TIMEOUT",
    "INGESTION_COMPARE_DEVICE",
    "INGESTION_COMPARE_KIND",
    "INGESTION_COMPARE_TIMEOUT",
    "INGESTION_PROCESS_DEVICE",
    "INGESTION_PROCESS_KIND",
    "INGESTION_PROCESS_TIMEOUT",
    "KG_BUILD_DEVICE",
    "KG_BUILD_KIND",
    "KG_BUILD_TIMEOUT",
    "PIPELINE_RUN_DEVICE",
    "PIPELINE_RUN_KIND",
    "PIPELINE_RUN_TIMEOUT",
    "RAG_QUERY_DEVICE",
    "RAG_QUERY_KIND",
    "RAG_QUERY_TIMEOUT",
    "STORAGE_SYNC_DEVICE",
    "STORAGE_SYNC_KIND",
    "STORAGE_SYNC_TIMEOUT",
    "embeddings_generate_executor",
    "ensure_dip_executors_registered",
    "extraction_process_executor",
    "ingestion_compare_executor",
    "ingestion_process_executor",
    "kg_build_executor",
    "pipeline_run_executor",
    "rag_query_executor",
    "storage_sync_executor",
]