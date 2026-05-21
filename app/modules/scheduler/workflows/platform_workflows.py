"""Platform Workflow Executors for Scheduler.

Wraps existing platform workflows (data pipelines, memory maintenance)
into executor functions that can be triggered by the scheduler.

Each executor:
1. Loads the workflow definition from the entity registry
2. Sets up the ExecutionEngine with observability tracing
3. Runs the workflow with provided inputs
4. WorkflowExecution records are automatically created via SQLAlchemyBackend
5. Returns structured results
"""

import logging
import time
import asyncio
import uuid
from typing import Any, Dict, List, Optional

from common_lib.modules.workflows.standard.observability import EventTracer
from common_lib.modules.workflows.standard.observability.events import (
    EventType,
    WorkflowEvent,
)
from common_lib.modules.workflows.standard.observability.backends import (
    SQLAlchemyBackend,
)
from common_lib.modules.workflows.standard.execution.core import ExecutionEngine
from common_lib.modules.workflows.standard.execution.executor import GraphExecutor
from common_lib.modules.workflows.standard.execution.context import ExecutionContext
from common_lib.modules.workflows.standard.execution.primitives import (
    State,
    Graph,
    Transition,
)

logger = logging.getLogger(__name__)


def _get_registry():
    """Get the entity registry service."""
    try:
        from app.modules.entities.routes.registry import _get_registry_svc

        return _get_registry_svc()
    except Exception:
        return None


def _create_tracer(workflow_id: str, trace_id: str) -> EventTracer:
    """Create an EventTracer with SQLAlchemy backend for observability."""
    tracer = EventTracer()
    try:
        tracer.add_backend(SQLAlchemyBackend())
    except Exception as e:
        logger.warning(f"Could not add SQLAlchemy backend: {e}")
    return tracer


def _emit_start(
    tracer: EventTracer, trace_id: str, workflow_id: str, inputs: Dict[str, Any]
):
    """Emit WORKFLOW_STARTED event."""
    tracer.emit(
        WorkflowEvent(
            event_type=EventType.WORKFLOW_STARTED,
            trace_id=trace_id,
            workflow_id=workflow_id,
            workflow_name=workflow_id,
            agent_id="scheduler",
            span_id=str(uuid.uuid4()),
            initial_inputs=inputs,
        )
    )


def _emit_complete(
    tracer: EventTracer, trace_id: str, workflow_id: str, outputs: Dict[str, Any]
):
    """Emit WORKFLOW_COMPLETED event."""
    tracer.emit(
        WorkflowEvent(
            event_type=EventType.WORKFLOW_COMPLETED,
            trace_id=trace_id,
            workflow_id=workflow_id,
            span_id=str(uuid.uuid4()),
            metadata={"outputs": outputs},
        )
    )


def _emit_failed(tracer: EventTracer, trace_id: str, workflow_id: str, error: str):
    """Emit WORKFLOW_FAILED event."""
    tracer.emit(
        WorkflowEvent(
            event_type=EventType.WORKFLOW_FAILED,
            trace_id=trace_id,
            workflow_id=workflow_id,
            span_id=str(uuid.uuid4()),
            metadata={"error": error},
        )
    )


def _build_graph_for_procedures(procedures: List[Dict[str, Any]]) -> Graph:
    """Build a Graph from workflow procedures."""
    states = {}
    for proc in procedures:
        proc_id = proc["id"]
        tool_id = proc.get("procedure_id", proc.get("tool_id", "unknown"))
        config = proc.get("config", {})

        s = State(
            id=proc_id,
            tool_id=tool_id,
            static_inputs=config,
            metadata={
                "phase": proc.get("phase", "execute"),
                "enabled": proc.get("enabled", True),
            },
        )
        states[proc_id] = s

    graph = Graph(
        id=f"wf_{uuid.uuid4()}",
        name="workflow",
        start_state_id=procedures[0]["id"] if procedures else "start",
    )
    for s in states.values():
        graph.add_state(s)

    # Add sequential transitions
    proc_ids = [p["id"] for p in procedures]
    for i in range(len(proc_ids) - 1):
        states[proc_ids[i]].transitions.append(Transition(to_state_id=proc_ids[i + 1]))

    return graph


async def _execute_workflow_graph(
    workflow_id: str,
    procedures: List[Dict[str, Any]],
    inputs: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a workflow graph with full observability tracing."""
    trace_id = trace_id or str(uuid.uuid4())
    tracer = _create_tracer(workflow_id, trace_id)

    _emit_start(tracer, trace_id, workflow_id, inputs)

    start = time.time()
    try:
        registry = _get_registry()
        engine = ExecutionEngine(registry=registry, tracer=tracer)
        graph = _build_graph_for_procedures(procedures)

        context = ExecutionContext(
            trace_id=trace_id, agent_id="scheduler", role="cron_executor"
        )

        executor = GraphExecutor(engine, tracer, {})
        result = await asyncio.to_thread(executor.execute, graph, inputs, context)

        duration_ms = (time.time() - start) * 1000
        outputs = {"duration_ms": round(duration_ms, 2), "result": str(result)}
        _emit_complete(tracer, trace_id, workflow_id, outputs)

        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "trace_id": trace_id,
            "duration_ms": round(duration_ms, 2),
            "outputs": outputs,
        }

    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        error_msg = str(e)
        _emit_failed(tracer, trace_id, workflow_id, error_msg)
        logger.error(f"Workflow {workflow_id} failed: {error_msg}")

        return {
            "workflow_id": workflow_id,
            "status": "failed",
            "trace_id": trace_id,
            "error": error_msg,
            "duration_ms": round(duration_ms, 2),
        }


async def execute_rag_pipeline(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """RAG Pipeline: Document ingestion, chunking, embedding, retrieval.

    Inputs:
        source_type: "local" | "url"
        source_path: Path or URL to document
        query: Search query (optional, for retrieval phase)
        chunk_size: Text chunk size (default: 1000)
        top_k: Number of chunks to retrieve (default: 5)
    """
    procedures = [
        {
            "id": "ingest_document",
            "procedure_id": "ingestion.file_upload",
            "phase": "preprocess",
            "config": {
                "source_type": inputs.get("source_type", "local"),
                "source_path": inputs.get("source_path", ""),
            },
        },
        {
            "id": "clean_text",
            "procedure_id": "normalization.text_cleaner",
            "phase": "preprocess",
            "config": {"strip_html": True},
        },
        {
            "id": "scan_pii",
            "procedure_id": "security.pii_scan",
            "phase": "preprocess",
            "config": {"entities": "PERSON,EMAIL,PHONE_NUMBER"},
        },
        {
            "id": "chunk_text",
            "procedure_id": "extraction.text_chunker",
            "phase": "execute",
            "config": {
                "strategy": "recursive",
                "chunk_size": inputs.get("chunk_size", 1000),
            },
        },
        {
            "id": "generate_embeddings",
            "procedure_id": "embedding.text_embedder",
            "phase": "execute",
            "config": {"model": "text-embedding-3-small"},
        },
        {
            "id": "store_vectors",
            "procedure_id": "storage.vector_db",
            "phase": "execute",
            "config": {"index_name": "documents"},
        },
    ]

    if inputs.get("query"):
        procedures.extend(
            [
                {
                    "id": "search_chunks",
                    "procedure_id": "query.semantic_search",
                    "phase": "execute",
                    "config": {
                        "top_k": inputs.get("top_k", 5),
                        "query": inputs["query"],
                    },
                },
                {
                    "id": "generate_answer",
                    "procedure_id": "agent.invoke",
                    "phase": "finalize",
                    "config": {"temperature": 0.1},
                },
            ]
        )

    return await _execute_workflow_graph("rag_pipeline", procedures, inputs)


async def execute_pii_compliance(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """PII Compliance: Scan data for PII, anonymize, generate audit report."""
    procedures = [
        {
            "id": "scan_data",
            "procedure_id": "security.pii_scan",
            "phase": "execute",
            "config": {
                "entities": inputs.get("entities", "PERSON,EMAIL,PHONE_NUMBER"),
                "data_source": inputs.get("data_source", ""),
            },
        },
        {
            "id": "anonymize",
            "procedure_id": "security.anonymize",
            "phase": "execute",
            "config": {"enabled": inputs.get("anonymize", True)},
        },
        {
            "id": "generate_report",
            "procedure_id": "compliance.audit_report",
            "phase": "finalize",
            "config": {},
        },
    ]

    return await _execute_workflow_graph("pii_compliance", procedures, inputs)


async def execute_memory_security_audit(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Memory Security Audit: PII scan, GDPR compliance, right-to-forget."""
    procedures = [
        {
            "id": "list_memories",
            "procedure_id": "memory.list",
            "phase": "preprocess",
            "config": {"skip": 0, "limit": 100},
        },
        {
            "id": "scan_pii",
            "procedure_id": "memory.pii_scan",
            "phase": "execute",
            "config": {"agent_id": inputs.get("agent_id", "default")},
        },
        {
            "id": "check_gdpr",
            "procedure_id": "memory.gdpr_compliance",
            "phase": "execute",
            "config": {
                "agent_id": inputs.get("agent_id", "default"),
                "max_retention_days": inputs.get("max_retention_days", 365),
            },
        },
    ]

    if inputs.get("hard_delete"):
        procedures.append(
            {
                "id": "execute_forget",
                "procedure_id": "memory.gdpr_forget",
                "phase": "finalize",
                "config": {
                    "agent_id": inputs.get("agent_id", "default"),
                    "hard_delete": True,
                },
            }
        )

    return await _execute_workflow_graph("memory_security_audit", procedures, inputs)


async def execute_memory_observability(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Memory Observability: Collect metrics, trace performance, health checks."""
    procedures = [
        {
            "id": "collect_metrics",
            "procedure_id": "memory.metrics",
            "phase": "execute",
            "config": {"window": inputs.get("window", "24h")},
        },
        {
            "id": "analyze_trends",
            "procedure_id": "memory.trends",
            "phase": "execute",
            "config": {},
        },
        {
            "id": "health_check",
            "procedure_id": "memory.health",
            "phase": "finalize",
            "config": {},
        },
    ]

    return await _execute_workflow_graph("memory_observability", procedures, inputs)


async def execute_memory_economics(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Memory Economics: Track embedding/storage costs, budget management."""
    procedures = [
        {
            "id": "track_costs",
            "procedure_id": "memory.costs",
            "phase": "execute",
            "config": {
                "agent_id": inputs.get("agent_id", "default"),
                "period": inputs.get("period", "monthly"),
            },
        },
        {
            "id": "budget_check",
            "procedure_id": "memory.budget",
            "phase": "finalize",
            "config": {"budget": inputs.get("budget")},
        },
    ]

    return await _execute_workflow_graph(
        "memory_economics_tracking", procedures, inputs
    )


async def execute_memory_federation_sync(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Memory Federation Sync: Sync memories across federated nodes."""
    procedures = [
        {
            "id": "discover_nodes",
            "procedure_id": "federation.discover",
            "phase": "preprocess",
            "config": {"seed_nodes": inputs.get("seed_nodes", [])},
        },
        {
            "id": "sync_memories",
            "procedure_id": "federation.sync",
            "phase": "execute",
            "config": {"max_hops": inputs.get("max_hops", 3)},
        },
        {
            "id": "resolve_conflicts",
            "procedure_id": "federation.conflicts",
            "phase": "finalize",
            "config": {"strategy": inputs.get("conflict_strategy", "latest")},
        },
    ]

    return await _execute_workflow_graph("memory_federation_sync", procedures, inputs)
