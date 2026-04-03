from fastapi import APIRouter
import time
from datetime import datetime, timedelta

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
            "type": "NODE"
        },
        {
            "id": "span-2",
            "node_id": "ParallelOrchestrator",
            "status": "COMPLETED",
            "duration": 3.5,
            "timestamp": (base_time - timedelta(seconds=8)).strftime("%H:%M:%S"),
            "type": "PLANNER"
        },
        {
            "id": "span-3",
            "node_id": "SubAgent-VibeCheck",
            "status": "COMPLETED",
            "duration": 2.1,
            "timestamp": (base_time - timedelta(seconds=7)).strftime("%H:%M:%S"),
            "type": "SUB_AGENT",
            "parent_id": "span-2"
        },
        {
            "id": "span-4",
            "node_id": "SubAgent-DataLookup",
            "status": "COMPLETED",
            "duration": 2.8,
            "timestamp": (base_time - timedelta(seconds=7)).strftime("%H:%M:%S"),
            "type": "SUB_AGENT",
            "parent_id": "span-2"
        },
        {
            "id": "span-5",
            "node_id": "AsyncContextMerger",
            "status": "COMPLETED",
            "duration": 0.4,
            "timestamp": (base_time - timedelta(seconds=4)).strftime("%H:%M:%S"),
            "type": "MERGER"
        },
        {
            "id": "span-6",
            "node_id": "FinalResponse",
            "status": "COMPLETED",
            "duration": 0.9,
            "timestamp": (base_time - timedelta(seconds=3)).strftime("%H:%M:%S"),
            "type": "NODE"
        }
    ]
    
    return spans
