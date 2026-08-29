"""``app.modules.i2w.routes._helpers`` — thin dispatchers from the FastAPI
handler boundary to the ``i2w_*`` @node wrappers in ``common_lib``.

The I2W wrapper functions are stable, public, and well-typed. The
router layer imports them directly and invokes them by name. This is
intentional: the wrappers own their contract (input validation,
serialisation, error handling); the router is a one-line delegate
that adds auth + RBAC + rate-limit + audit at the request edge.

Per ``be-rules-boundary`` and the docs (``12_integration_points.md``),
the router layer MUST NOT import any other business module directly.
The only allowed import is ``common_lib.modules.orchestration.instruction_to_workflow``
(self) and the universal ``plugins.node`` for the decorator
metadata.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wrapper registry — direct import (router is allowed to know about
# the I2W package itself; it is not a "business module" relative to I2W).
# ---------------------------------------------------------------------------


# Lazy imports to keep module-level cold start fast. The dispatchers
# resolve the wrapper on first use and cache it in a dict.
_LAZY_WRAPPERS: Dict[str, str] = {
    # Composite
    "i2w_generate_and_execute": (
        "common_lib.modules.orchestration.instruction_to_workflow.nodes.service"
        ".instruction_to_workflow_generate_and_execute"
    ),
    "i2w_health": (
        "common_lib.modules.orchestration.instruction_to_workflow.nodes.service"
        ".instruction_to_workflow_health"
    ),
    # Ingest
    "i2w_ingest_audio": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_ingest_audio"
    ),
    "i2w_ingest_text": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_ingest_text"
    ),
    "i2w_ingest_screenshot": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_ingest_screenshot"
    ),
    "i2w_ingest_screen_recording": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_ingest_screen_recording"
    ),
    "i2w_ingest_file": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_ingest_file"
    ),
    "i2w_ingest_multi": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_ingest_multi"
    ),
    "i2w_ingest_health": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_ingest_health"
    ),
    "i2w_transcribe": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_transcribe"
    ),
    "i2w_scrub_pii": (
        "common_lib.modules.orchestration.instruction_to_workflow.ingestion"
        ".nodes.service.i2w_scrub_pii"
    ),
    # Reason
    "i2w_reason": (
        "common_lib.modules.orchestration.instruction_to_workflow.reasoning"
        ".nodes.service.i2w_reason"
    ),
    "i2w_reason_text": (
        "common_lib.modules.orchestration.instruction_to_workflow.reasoning"
        ".nodes.service.i2w_reason_text"
    ),
    "i2w_extract_steps": (
        "common_lib.modules.orchestration.instruction_to_workflow.reasoning"
        ".nodes.service.i2w_extract_steps"
    ),
    "i2w_analyze_dependencies": (
        "common_lib.modules.orchestration.instruction_to_workflow.reasoning"
        ".nodes.service.i2w_analyze_dependencies"
    ),
    "i2w_score_confidence": (
        "common_lib.modules.orchestration.instruction_to_workflow.reasoning"
        ".nodes.service.i2w_score_confidence"
    ),
    "i2w_resolve_ambiguity": (
        "common_lib.modules.orchestration.instruction_to_workflow.reasoning"
        ".nodes.service.i2w_resolve_ambiguity"
    ),
    "i2w_reasoning_health": (
        "common_lib.modules.orchestration.instruction_to_workflow.reasoning"
        ".nodes.service.i2w_reasoning_health"
    ),
    # Plan
    "i2w_plan": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_plan"
    ),
    "i2w_plan_yaml": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_plan_yaml"
    ),
    "i2w_validate_plan": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_validate_plan"
    ),
    "i2w_optimize_plan": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_optimize_plan"
    ),
    "i2w_detect_gaps": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_detect_gaps"
    ),
    "i2w_resolve_command": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_resolve_command"
    ),
    "i2w_fill_arguments": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_fill_arguments"
    ),
    "i2w_emit_yaml": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_emit_yaml"
    ),
    "i2w_parse_yaml": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_parse_yaml"
    ),
    "i2w_planning_health": (
        "common_lib.modules.orchestration.instruction_to_workflow.planning"
        ".nodes.service.i2w_planning_health"
    ),
    # Dispatch
    "i2w_execute": (
        "common_lib.modules.orchestration.instruction_to_workflow.dispatch"
        ".nodes.dispatch_service.i2w_execute"
    ),
    "i2w_get_execution": (
        "common_lib.modules.orchestration.instruction_to_workflow.dispatch"
        ".nodes.dispatch_service.i2w_get_execution"
    ),
    "i2w_cancel_execution": (
        "common_lib.modules.orchestration.instruction_to_workflow.dispatch"
        ".nodes.dispatch_service.i2w_cancel_execution"
    ),
    "i2w_rollback_execution": (
        "common_lib.modules.orchestration.instruction_to_workflow.dispatch"
        ".nodes.dispatch_service.i2w_rollback_execution"
    ),
    "i2w_list_executions": (
        "common_lib.modules.orchestration.instruction_to_workflow.dispatch"
        ".nodes.dispatch_service.i2w_list_executions"
    ),
    "i2w_dispatch_health": (
        "common_lib.modules.orchestration.instruction_to_workflow.dispatch"
        ".nodes.dispatch_service.i2w_dispatch_health"
    ),
    # Search
    "i2w_universal_search": (
        "common_lib.modules.orchestration.instruction_to_workflow.search"
        ".nodes.search_service.i2w_universal_search"
    ),
    "i2w_search_commands": (
        "common_lib.modules.orchestration.instruction_to_workflow.search"
        ".nodes.search_service.i2w_search_commands"
    ),
    "i2w_search_workflows": (
        "common_lib.modules.orchestration.instruction_to_workflow.search"
        ".nodes.search_service.i2w_search_workflows"
    ),
    "i2w_search_history": (
        "common_lib.modules.orchestration.instruction_to_workflow.search"
        ".nodes.search_service.i2w_search_history"
    ),
    "i2w_search_templates": (
        "common_lib.modules.orchestration.instruction_to_workflow.search"
        ".nodes.search_service.i2w_search_templates"
    ),
    "i2w_search_tutorials": (
        "common_lib.modules.orchestration.instruction_to_workflow.search"
        ".nodes.search_service.i2w_search_tutorials"
    ),
    "i2w_rag_search": (
        "common_lib.modules.orchestration.instruction_to_workflow.search"
        ".nodes.search_service.i2w_rag_search"
    ),
    "i2w_search_health": (
        "common_lib.modules.orchestration.instruction_to_workflow.search"
        ".nodes.search_service.i2w_search_health"
    ),
    # Training
    "i2w_training_collect_record": (
        "common_lib.modules.orchestration.instruction_to_workflow.training"
        ".nodes.training_service.i2w_training_collect_record"
    ),
    "i2w_training_list_records": (
        "common_lib.modules.orchestration.instruction_to_workflow.training"
        ".nodes.training_service.i2w_training_list_records"
    ),
    "i2w_training_export": (
        "common_lib.modules.orchestration.instruction_to_workflow.training"
        ".nodes.training_service.i2w_training_export"
    ),
    "i2w_training_submit_feedback": (
        "common_lib.modules.orchestration.instruction_to_workflow.training"
        ".nodes.training_service.i2w_training_submit_feedback"
    ),
    "i2w_training_evaluate": (
        "common_lib.modules.orchestration.instruction_to_workflow.training"
        ".nodes.training_service.i2w_training_evaluate"
    ),
    "i2w_training_health": (
        "common_lib.modules.orchestration.instruction_to_workflow.training"
        ".nodes.training_service.i2w_training_health"
    ),
}


_WRAPPER_CACHE: Dict[str, Callable[..., Any]] = {}


def _resolve_wrapper(name: str) -> Callable[..., Any]:
    """Resolve a wrapper function by name. Cached after first lookup."""
    if name in _WRAPPER_CACHE:
        return _WRAPPER_CACHE[name]
    if name not in _LAZY_WRAPPERS:
        raise RuntimeError(
            f"Unknown I2W wrapper '{name}' — "
            "not registered in app.modules.i2w.routes._helpers"
        )
    import importlib

    module_path, _, attr = _LAZY_WRAPPERS[name].rpartition(".")
    module = importlib.import_module(module_path)
    fn = getattr(module, attr)
    _WRAPPER_CACHE[name] = fn
    return fn


def invoke_i2w(
    name: str,
    *,
    defaults: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Invoke an ``i2w_*`` @node wrapper, merging ``defaults`` first.

    The defaults let handlers set platform-standard fields
    (``user_id_hash``, ``tenant_id``, ``trace_id``) that are pulled
    off the request and merged in before the wrapper sees them.
    """
    fn = _resolve_wrapper(name)
    payload: Dict[str, Any] = {}
    if defaults:
        payload.update(defaults)
    payload.update(kwargs)
    result = fn(**payload)
    if result is None:
        return {}
    if not isinstance(result, dict):
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        return {"result": result}
    return result


__all__ = ["invoke_i2w", "_LAZY_WRAPPERS"]
