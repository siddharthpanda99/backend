from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any
import json
from app.modules.common.types.index import APIResponse

router = APIRouter()

_workflow_states = {}


@router.get("/")
def list_workflows():
    from common_lib.modules.workflows.standard.state import WorkflowState

    return APIResponse(data=[], message="No workflows")


@router.post("/run-stream")
async def run_workflow_stream(
    nodes: List[Dict[str, Any]] = [],
    edges: List[Dict[str, Any]] = [],
    inputs: Dict[str, Any] = {},
):
    from common_lib.modules.workflows.standard.execution.executor import GraphExecutor
    from common_lib.modules.workflows.standard.execution.core import ExecutionEngine
    from common_lib.modules.workflows.standard.execution.context import ExecutionContext
    from common_lib.modules.workflows.standard.observability import ConsoleTracer

    async def generate():
        try:
            from app.core.common_lib_integration import get_engine_manager

            em = get_engine_manager()
            registry = em.registry_svc if em else None
        except Exception:
            registry = None

        tracer = ConsoleTracer()
        engine = ExecutionEngine(registry=registry, tracer=tracer)
        executor = GraphExecutor(engine, tracer)
        context = ExecutionContext(agent_id="workflow", role="executor")

        from common_lib.modules.workflows.standard.execution.primitives import (
            Graph,
            State,
            Transition,
        )
        import uuid

        state_map = {}
        for n in nodes:
            s = State(
                id=n.get("id", str(uuid.uuid4())),
                tool_id=n.get("toolId", n.get("type", "unknown")),
                static_inputs=n.get("properties", {}),
            )
            state_map[s.id] = s

        if not nodes:
            yield {"event_type": "DONE", "message": "No nodes"}
            return

        graph = Graph(
            id=f"wf_{uuid.uuid4().hex[:8]}",
            name="Workflow",
            start_state_id=nodes[0].get("id", state_map.keys()[0])
            if state_map
            else "unknown",
        )

        for s in state_map.values():
            graph.add_state(s)

        for e in edges:
            if e.get("from") in state_map and e.get("to") in state_map:
                state_map[e["from"]].transitions.append(Transition(to_state_id=e["to"]))

        import asyncio

        loop = asyncio.get_event_loop()

        async def run():
            try:
                await loop.run_in_executor(
                    None, executor.execute, graph, inputs, context
                )
            except Exception as e:
                yield {"event_type": "ERROR", "error": str(e)}
            yield {"event_type": "DONE"}

        asyncio.create_task(run())

        while True:
            await asyncio.sleep(0.1)
            if tracer.last_event == "DONE":
                break
            yield {"event_type": "RUNNING", "message": "Executing..."}

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/{id}")
def get_workflow(id: str):
    return APIResponse(data={"id": id}, message="Use workflow execution")


__all__ = ["router"]
