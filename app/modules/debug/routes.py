from fastapi import APIRouter, HTTPException, status
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from common_lib.modules.debug.session_manager import (
    get_debug_session_manager,
    DebugSessionStatus,
)

router = APIRouter()


@router.get("/parallel-trace")
def get_mock_parallel_trace():
    """
    Simulates a SOTA Parallel Agentic Execution Trace.
    Demonstrates:
    1. Input Planning (Sequence)
    2. Parallel Fan-out (2 concurrent sub-agents)
    3. Async Context Merging
    4. Final Response Generation
    """
    base_time = datetime.now()

    spans = [
        {
            "id": "span-1",
            "node_id": "InputPlanner",
            "status": "COMPLETED",
            "duration": 1.2,
            "timestamp": (base_time - timedelta(seconds=10)).strftime("%H:%M:%S"),
            "type": "NODE",
        },
        {
            "id": "span-2",
            "node_id": "ParallelOrchestrator",
            "status": "COMPLETED",
            "duration": 3.5,
            "timestamp": (base_time - timedelta(seconds=8)).strftime("%H:%M:%S"),
            "type": "PLANNER",
        },
        {
            "id": "span-3",
            "node_id": "SubAgent-VibeCheck",
            "status": "COMPLETED",
            "duration": 2.1,
            "timestamp": (base_time - timedelta(seconds=7)).strftime("%H:%M:%S"),
            "type": "SUB_AGENT",
            "parent_id": "span-2",
        },
        {
            "id": "span-4",
            "node_id": "SubAgent-DataLookup",
            "status": "COMPLETED",
            "duration": 2.8,
            "timestamp": (base_time - timedelta(seconds=7)).strftime("%H:%M:%S"),
            "type": "SUB_AGENT",
            "parent_id": "span-2",
        },
        {
            "id": "span-5",
            "node_id": "AsyncContextMerger",
            "status": "COMPLETED",
            "duration": 0.4,
            "timestamp": (base_time - timedelta(seconds=4)).strftime("%H:%M:%S"),
            "type": "MERGER",
        },
        {
            "id": "span-6",
            "node_id": "FinalResponse",
            "status": "COMPLETED",
            "duration": 0.9,
            "timestamp": (base_time - timedelta(seconds=3)).strftime("%H:%M:%S"),
            "type": "NODE",
        },
    ]

    return spans


@router.post("/session/{workflow_id}/start", tags=["Debug"])
def start_debug_session_route(workflow_id: str):
    debug_manager = get_debug_session_manager()
    session = debug_manager.start_session(workflow_id)
    return {
        "session_id": session.session_id,
        "workflow_id": session.workflow_id,
        "status": session.status,
    }


@router.get("/session/{workflow_id}/status", tags=["Debug"])
def get_debug_session_status_route(workflow_id: str):
    debug_manager = get_debug_session_manager()
    session = debug_manager.get_session(workflow_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No debug session found for workflow ID: {workflow_id}",
        )
    return {
        "session_id": session.session_id,
        "workflow_id": session.workflow_id,
        "status": session.status,
        "current_node_id": session.current_node_id,
        "state_vars": session.state_vars,
        "pause_reason": session.pause_reason,
        "last_updated": session.last_updated,
    }


@router.post("/session/{workflow_id}/resume", tags=["Debug"])
def resume_debug_session_route(workflow_id: str):
    debug_manager = get_debug_session_manager()
    session = debug_manager.get_session(workflow_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No debug session found for workflow ID: {workflow_id}",
        )

    if session.status != DebugSessionStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow {workflow_id} is not paused. Current status: {session.status}",
        )

    debug_manager.resume_session(workflow_id)
    return {
        "message": f"Workflow {workflow_id} resumed.",
        "status": DebugSessionStatus.RUNNING,
    }


@router.post("/session/{workflow_id}/clear", tags=["Debug"])
def clear_debug_session_route(workflow_id: str):
    debug_manager = get_debug_session_manager()
    session = debug_manager.get_session(workflow_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No debug session found for workflow ID: {workflow_id}",
        )

    debug_manager.clear_session(workflow_id)
    return {
        "message": f"Debug session for workflow {workflow_id} cleared.",
        "status": DebugSessionStatus.IDLE,
    }
