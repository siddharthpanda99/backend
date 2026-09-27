"""Background-job executor for the agentic loop (agent turn).

Moves a full agent turn OFF the FastAPI event loop onto the jobs module:
the blocking executor drives ``stream_agent_generator`` (the LangGraph
``astream_events`` loop in ``core/streaming.py``) with ``asyncio.run`` inside
the jobs worker thread, collects the SSE transcript, and persists it as a
refs-only JSON artifact (``transcript.json``). Only the ref string lands in
``result_refs`` — raw bytes never touch ``JobRecord``.

Live token-level streaming cannot be precomputed, so the interactive
``POST /agents/runtime/stream`` endpoint stays inline (async I/O, not blocking);
the job-backed ``POST /agents/runtime/stream/job`` + status/SSE-poll endpoints
are the off-loop alternative.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

AGENT_TURN_KIND = "agent.turn"
AGENT_TURN_DEVICE = "cpu"
AGENT_TURN_TIMEOUT = 600.0


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


async def _collect_turn_async(
    params: dict[str, Any],
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> dict[str, Any]:
    """Iterate the agent SSE generator, capturing the transcript."""
    from app.modules.agents.runtime.core.streaming import stream_agent_generator

    gen = stream_agent_generator(
        message=str(params.get("message", "")),
        session_id=str(params.get("session_id", "")),
        decision=params.get("decision"),
        agent_id=params.get("agent_id"),
        system_prompt=params.get("system_prompt"),
        model_path=params.get("model_path"),
        provider=params.get("provider"),
        loop_id=params.get("loop_id"),
        reasoning_mode=bool(params.get("reasoning_mode", False)),
        reasoning_plan_id=params.get("reasoning_plan_id"),
        reasoning_level=str(params.get("reasoning_level") or "brief"),
    )
    transcript: list[dict[str, Any]] = []
    final_answer: str = ""
    error: Optional[str] = None
    event_count: int = 0
    async for chunk in gen:
        if check_cancel():
            raise asyncio.CancelledError()
        event_count += 1
        report_progress(min(95.0, 5.0 + float(event_count)))
        text: str = chunk if isinstance(chunk, str) else str(chunk)
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            raw: str = line[len("data:") :].strip()
            try:
                payload: Any = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(payload, dict):
                transcript.append(payload)
                if payload.get("event_type") == "agent_complete" and not final_answer:
                    final_answer = str(payload.get("content", ""))
                if payload.get("event_type") == "error" and error is None:
                    error = str(payload.get("content", ""))
    report_progress(95.0)
    return {
        "status": "completed" if error is None else "failed",
        "final_answer": final_answer,
        "events_count": event_count,
        "error": error,
    }


def agent_turn_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``agent.turn`` jobs."""
    from common_lib.modules.jobs.artifacts import save_artifact

    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    logger.info(
        "jobs: agent turn started job=%s session=%s", job_id, params.get("session_id")
    )
    report_progress(5.0)
    if check_cancel():
        return {"result_refs": [], "status": "cancelled"}
    if not params.get("message") or not params.get("session_id"):
        return {"result_refs": [], "status": "failed"}
    result: dict[str, Any] = asyncio.run(
        _collect_turn_async(params, check_cancel, report_progress)
    )
    if check_cancel():
        return {"result_refs": [], "status": "cancelled"}
    payload: bytes = json.dumps(result, default=str).encode("utf-8")
    ref: str = save_artifact(job_id, "transcript.json", payload)
    report_progress(100.0)
    return {"result_refs": [ref], "status": str(result.get("status", "unknown"))}


def ensure_agent_executors_registered() -> bool:
    """Register the agent-turn executor (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        get_job_service().register_executor(
            AGENT_TURN_KIND,
            agent_turn_executor,
            device=AGENT_TURN_DEVICE,
            timeout=AGENT_TURN_TIMEOUT,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_agent_executors_registered failed: %s", exc)
        return False


__all__ = [
    "AGENT_TURN_DEVICE",
    "AGENT_TURN_KIND",
    "AGENT_TURN_TIMEOUT",
    "agent_turn_executor",
    "ensure_agent_executors_registered",
]
