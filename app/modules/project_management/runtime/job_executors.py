"""Project Management background-job executors.

Moves blocking PM operations OFF the FastAPI event loop onto the jobs module.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

# AI operations
PM_AI_GENERATE_KIND = "pm.ai.generate"
PM_AI_GENERATE_DEVICE = "gpu"
PM_AI_GENERATE_TIMEOUT = 600.0

PM_AI_ANALYZE_KIND = "pm.ai.analyze"
PM_AI_ANALYZE_DEVICE = "gpu"
PM_AI_ANALYZE_TIMEOUT = 600.0

PM_AI_SUMMARIZE_KIND = "pm.ai.summarize"
PM_AI_SUMMARIZE_DEVICE = "gpu"
PM_AI_SUMMARIZE_TIMEOUT = 300.0

PM_AI_ESTIMATE_KIND = "pm.ai.estimate"
PM_AI_ESTIMATE_DEVICE = "gpu"
PM_AI_ESTIMATE_TIMEOUT = 300.0

# CI/CD operations
PM_CICD_BUILD_KIND = "pm.cicd.build"
PM_CICD_BUILD_DEVICE = "cpu"
PM_CICD_BUILD_TIMEOUT = 1800.0

PM_CICD_DEPLOY_KIND = "pm.cicd.deploy"
PM_CICD_DEPLOY_DEVICE = "cpu"
PM_CICD_DEPLOY_TIMEOUT = 1800.0

PM_CICD_TEST_KIND = "pm.cicd.test"
PM_CICD_TEST_DEVICE = "cpu"
PM_CICD_TEST_TIMEOUT = 1800.0

# Import/Export operations
PM_IMPORT_KIND = "pm.import"
PM_IMPORT_DEVICE = "cpu"
PM_IMPORT_TIMEOUT = 3600.0

PM_EXPORT_KIND = "pm.export"
PM_EXPORT_DEVICE = "cpu"
PM_EXPORT_TIMEOUT = 3600.0

# Planning operations
PM_PLANNING_SCHEDULE_KIND = "pm.planning.schedule"
PM_PLANNING_SCHEDULE_DEVICE = "cpu"
PM_PLANNING_SCHEDULE_TIMEOUT = 600.0

PM_PLANNING_OPTIMIZE_KIND = "pm.planning.optimize"
PM_PLANNING_OPTIMIZE_DEVICE = "gpu"
PM_PLANNING_OPTIMIZE_TIMEOUT = 600.0

# Reporting
PM_REPORT_GENERATE_KIND = "pm.report.generate"
PM_REPORT_GENERATE_DEVICE = "cpu"
PM_REPORT_GENERATE_TIMEOUT = 600.0

# Bulk operations
PM_BULK_UPDATE_KIND = "pm.bulk.update"
PM_BULK_UPDATE_DEVICE = "cpu"
PM_BULK_UPDATE_TIMEOUT = 1800.0

PM_BULK_CREATE_KIND = "pm.bulk.create"
PM_BULK_CREATE_DEVICE = "cpu"
PM_BULK_CREATE_TIMEOUT = 1800.0


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
# PM operation executors
# ---------------------------------------------------------------------------


def _get_pm_ai_service():
    from common_lib.modules.project_management.ai.service import get_pm_ai_service
    return get_pm_ai_service()


def _get_pm_cicd_service():
    from common_lib.modules.project_management.cicd.service import get_pm_cicd_service
    return get_pm_cicd_service()


def _get_pm_import_export_service():
    from common_lib.modules.project_management.importexport.service import get_pm_importexport_service
    return get_pm_importexport_service()


def _get_pm_planning_service():
    from common_lib.modules.project_management.planning.service import get_pm_planning_service
    return get_pm_planning_service()


def _get_pm_reporting_service():
    from common_lib.modules.project_management.reporting.service import get_pm_reporting_service
    return get_pm_reporting_service()


def _get_pm_bulk_service():
    from common_lib.modules.project_management.bulk.service import get_pm_bulk_service
    return get_pm_bulk_service()


def ai_generate_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    prompt = params.get("prompt")
    context = params.get("context", {})
    model = params.get("model")
    if not prompt:
        return _finish(job_id, {"error": "Missing prompt"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_ai_service()
    result = _run_async(lambda: svc.generate(prompt, context=context, model=model))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def ai_analyze_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    data = params.get("data")
    analysis_type = params.get("analysis_type", "general")
    if not data:
        return _finish(job_id, {"error": "Missing data"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_ai_service()
    result = _run_async(lambda: svc.analyze(data, analysis_type=analysis_type))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def ai_summarize_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    text = params.get("text")
    max_length = params.get("max_length", 500)
    if not text:
        return _finish(job_id, {"error": "Missing text"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_ai_service()
    result = _run_async(lambda: svc.summarize(text, max_length=max_length))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def ai_estimate_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    tasks = params.get("tasks", [])
    if not tasks:
        return _finish(job_id, {"error": "Missing tasks"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_ai_service()
    result = _run_async(lambda: svc.estimate(tasks))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def cicd_build_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    pipeline_id = params.get("pipeline_id")
    config = params.get("config", {})
    if not pipeline_id:
        return _finish(job_id, {"error": "Missing pipeline_id"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_cicd_service()
    result = _run_async(lambda: svc.build(pipeline_id, config))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def cicd_deploy_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    deployment_id = params.get("deployment_id")
    environment = params.get("environment", "production")
    if not deployment_id:
        return _finish(job_id, {"error": "Missing deployment_id"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_cicd_service()
    result = _run_async(lambda: svc.deploy(deployment_id, environment))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def cicd_test_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    pipeline_id = params.get("pipeline_id")
    test_config = params.get("test_config", {})
    if not pipeline_id:
        return _finish(job_id, {"error": "Missing pipeline_id"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_cicd_service()
    result = _run_async(lambda: svc.test(pipeline_id, test_config))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def import_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    file_data = params.get("file")
    import_type = params.get("type", "jira")
    mapping = params.get("mapping", {})
    if not file_data:
        return _finish(job_id, {"error": "Missing file"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_import_export_service()
    import base64
    file_bytes = base64.b64decode(file_data) if isinstance(file_data, str) else file_data
    result = _run_async(lambda: svc.import_data(file_bytes, import_type, mapping))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def export_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    project_ids = params.get("project_ids", [])
    export_format = params.get("format", "json")
    include_attachments = params.get("include_attachments", False)

    if not project_ids:
        return _finish(job_id, {"error": "Missing project_ids"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_import_export_service()
    result = _run_async(lambda: svc.export_data(project_ids, export_format, include_attachments))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def planning_schedule_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    project_id = params.get("project_id")
    tasks = params.get("tasks", [])
    constraints = params.get("constraints", {})
    if not project_id or not tasks:
        return _finish(job_id, {"error": "Missing project_id or tasks"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_planning_service()
    result = _run_async(lambda: svc.schedule(project_id, tasks, constraints))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def planning_optimize_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    project_id = params.get("project_id")
    objectives = params.get("objectives", ["minimize_duration", "balance_workload"])
    if not project_id:
        return _finish(job_id, {"error": "Missing project_id"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_planning_service()
    result = _run_async(lambda: svc.optimize(project_id, objectives))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def report_generate_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    report_type = params.get("report_type", "status")
    project_ids = params.get("project_ids", [])
    date_range = params.get("date_range")
    format = params.get("format", "pdf")

    if not project_ids:
        return _finish(job_id, {"error": "Missing project_ids"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_reporting_service()
    result = _run_async(lambda: svc.generate(report_type, project_ids, date_range, format))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def bulk_update_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    updates = params.get("updates", [])
    entity_type = params.get("entity_type", "issue")
    if not updates:
        return _finish(job_id, {"error": "Missing updates"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_bulk_service()
    result = _run_async(lambda: svc.bulk_update(entity_type, updates))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def bulk_create_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    items = params.get("items", [])
    entity_type = params.get("entity_type", "issue")
    if not items:
        return _finish(job_id, {"error": "Missing items"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    svc = _get_pm_bulk_service()
    result = _run_async(lambda: svc.bulk_create(entity_type, items))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    # AI operations
    (PM_AI_GENERATE_KIND, ai_generate_executor, PM_AI_GENERATE_DEVICE, PM_AI_GENERATE_TIMEOUT),
    (PM_AI_ANALYZE_KIND, ai_analyze_executor, PM_AI_ANALYZE_DEVICE, PM_AI_ANALYZE_TIMEOUT),
    (PM_AI_SUMMARIZE_KIND, ai_summarize_executor, PM_AI_SUMMARIZE_DEVICE, PM_AI_SUMMARIZE_TIMEOUT),
    (PM_AI_ESTIMATE_KIND, ai_estimate_executor, PM_AI_ESTIMATE_DEVICE, PM_AI_ESTIMATE_TIMEOUT),
    # CI/CD operations
    (PM_CICD_BUILD_KIND, cicd_build_executor, PM_CICD_BUILD_DEVICE, PM_CICD_BUILD_TIMEOUT),
    (PM_CICD_DEPLOY_KIND, cicd_deploy_executor, PM_CICD_DEPLOY_DEVICE, PM_CICD_DEPLOY_TIMEOUT),
    (PM_CICD_TEST_KIND, cicd_test_executor, PM_CICD_TEST_DEVICE, PM_CICD_TEST_TIMEOUT),
    # Import/Export
    (PM_IMPORT_KIND, import_executor, PM_IMPORT_DEVICE, PM_IMPORT_TIMEOUT),
    (PM_EXPORT_KIND, export_executor, PM_EXPORT_DEVICE, PM_EXPORT_TIMEOUT),
    # Planning
    (PM_PLANNING_SCHEDULE_KIND, planning_schedule_executor, PM_PLANNING_SCHEDULE_DEVICE, PM_PLANNING_SCHEDULE_TIMEOUT),
    (PM_PLANNING_OPTIMIZE_KIND, planning_optimize_executor, PM_PLANNING_OPTIMIZE_DEVICE, PM_PLANNING_OPTIMIZE_TIMEOUT),
    # Reporting
    (PM_REPORT_GENERATE_KIND, report_generate_executor, PM_REPORT_GENERATE_DEVICE, PM_REPORT_GENERATE_TIMEOUT),
    # Bulk operations
    (PM_BULK_UPDATE_KIND, bulk_update_executor, PM_BULK_UPDATE_DEVICE, PM_BULK_UPDATE_TIMEOUT),
    (PM_BULK_CREATE_KIND, bulk_create_executor, PM_BULK_CREATE_DEVICE, PM_BULK_CREATE_TIMEOUT),
)


def ensure_pm_executors_registered() -> bool:
    """Register all PM executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:
        logger.warning("ensure_pm_executors_registered failed: %s", exc)
        return False


__all__ = [
    "PM_AI_ANALYZE_DEVICE",
    "PM_AI_ANALYZE_KIND",
    "PM_AI_ANALYZE_TIMEOUT",
    "PM_AI_ESTIMATE_DEVICE",
    "PM_AI_ESTIMATE_KIND",
    "PM_AI_ESTIMATE_TIMEOUT",
    "PM_AI_GENERATE_DEVICE",
    "PM_AI_GENERATE_KIND",
    "PM_AI_GENERATE_TIMEOUT",
    "PM_AI_SUMMARIZE_DEVICE",
    "PM_AI_SUMMARIZE_KIND",
    "PM_AI_SUMMARIZE_TIMEOUT",
    "PM_BULK_CREATE_DEVICE",
    "PM_BULK_CREATE_KIND",
    "PM_BULK_CREATE_TIMEOUT",
    "PM_BULK_UPDATE_DEVICE",
    "PM_BULK_UPDATE_KIND",
    "PM_BULK_UPDATE_TIMEOUT",
    "PM_CICD_BUILD_DEVICE",
    "PM_CICD_BUILD_KIND",
    "PM_CICD_BUILD_TIMEOUT",
    "PM_CICD_DEPLOY_DEVICE",
    "PM_CICD_DEPLOY_KIND",
    "PM_CICD_DEPLOY_TIMEOUT",
    "PM_CICD_TEST_DEVICE",
    "PM_CICD_TEST_KIND",
    "PM_CICD_TEST_TIMEOUT",
    "PM_EXPORT_DEVICE",
    "PM_EXPORT_KIND",
    "PM_EXPORT_TIMEOUT",
    "PM_IMPORT_DEVICE",
    "PM_IMPORT_KIND",
    "PM_IMPORT_TIMEOUT",
    "PM_PLANNING_OPTIMIZE_DEVICE",
    "PM_PLANNING_OPTIMIZE_KIND",
    "PM_PLANNING_OPTIMIZE_TIMEOUT",
    "PM_PLANNING_SCHEDULE_DEVICE",
    "PM_PLANNING_SCHEDULE_KIND",
    "PM_PLANNING_SCHEDULE_TIMEOUT",
    "PM_REPORT_GENERATE_DEVICE",
    "PM_REPORT_GENERATE_KIND",
    "PM_REPORT_GENERATE_TIMEOUT",
    "ai_analyze_executor",
    "ai_estimate_executor",
    "ai_generate_executor",
    "ai_summarize_executor",
    "bulk_create_executor",
    "bulk_update_executor",
    "cicd_build_executor",
    "cicd_deploy_executor",
    "cicd_test_executor",
    "ensure_pm_executors_registered",
    "export_executor",
    "import_executor",
    "planning_optimize_executor",
    "planning_schedule_executor",
    "report_generate_executor",
]