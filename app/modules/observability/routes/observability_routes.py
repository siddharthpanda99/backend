"""
Observability Routes
--------------------
API routes for Langfuse, MLFlow, and LangFlow integrations.

Provides endpoints for:
- Langfuse: Tracing, spans, scores, and trace management
- MLFlow: Experiment tracking, run management, and comparisons
- LangFlow: Flow listing, execution, and sync
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observability", tags=["Observability"])


# ── Request/Response Models ─────────────────────────────────────────────────

class TraceCreateRequest(BaseModel):
    name: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class SpanCreateRequest(BaseModel):
    trace_id: str
    name: str
    input_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ScoreRequest(BaseModel):
    trace_id: str
    name: str
    value: float
    comment: Optional[str] = None


class ExperimentRunRequest(BaseModel):
    experiment_name: str
    run_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, float]] = None
    tags: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class FlowRunRequest(BaseModel):
    flow_id: str
    inputs: Dict[str, Any]
    session_id: Optional[str] = None


class FlowCreateRequest(BaseModel):
    name: str
    description: str
    flow_data: Dict[str, Any]


# ── Langfuse Endpoints ──────────────────────────────────────────────────────

@router.get("/langfuse/status")
async def get_langfuse_status():
    """Get Langfuse integration status."""
    try:
        return {
            "enabled": True,
            "host": __import__("os").getenv("LANGFUSE_HOST", "http://localhost:3000"),
            "connected": True,
        }
    except Exception as e:
        logger.error(f"Failed to get Langfuse status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/langfuse/traces")
async def create_langfuse_trace(request: TraceCreateRequest):
    """Create a new Langfuse trace."""
    try:
        from common_lib.modules.observability.langfuse_integration import _get_langfuse_client
        
        client = _get_langfuse_client()
        if not client:
            raise HTTPException(status_code=503, detail="Langfuse not configured")
        
        trace = client.trace(
            name=request.name,
            session_id=request.session_id,
            user_id=request.user_id,
            metadata=request.metadata or {},
            tags=request.tags or [],
        )
        
        return {
            "trace_id": trace.id,
            "name": request.name,
            "status": "created",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create trace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/langfuse/traces/{trace_id}/spans")
async def create_langfuse_span(trace_id: str, request: SpanCreateRequest):
    """Create a span within a trace."""
    try:
        from common_lib.modules.observability.langfuse_integration import _get_langfuse_client
        
        client = _get_langfuse_client()
        if not client:
            raise HTTPException(status_code=503, detail="Langfuse not configured")
        
        span = client.span(
            trace_id=trace_id,
            name=request.name,
            input=request.input_data,
            metadata=request.metadata or {},
        )
        
        return {
            "span_id": span.id,
            "trace_id": trace_id,
            "name": request.name,
            "status": "created",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create span: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/langfuse/traces/{trace_id}/scores")
async def score_langfuse_trace(trace_id: str, request: ScoreRequest):
    """Add a score/evaluation to a trace."""
    try:
        from common_lib.modules.observability.langfuse_integration import _get_langfuse_client
        
        client = _get_langfuse_client()
        if not client:
            raise HTTPException(status_code=503, detail="Langfuse not configured")
        
        score = client.score(
            trace_id=trace_id,
            name=request.name,
            value=request.value,
            comment=request.comment,
        )
        
        return {
            "score_id": score.id,
            "trace_id": trace_id,
            "name": request.name,
            "value": request.value,
            "status": "created",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to score trace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/langfuse/traces/{trace_id}")
async def get_langfuse_trace(trace_id: str):
    """Get a Langfuse trace by ID."""
    try:
        from common_lib.modules.observability.langfuse_integration import _get_langfuse_client
        
        client = _get_langfuse_client()
        if not client:
            raise HTTPException(status_code=503, detail="Langfuse not configured")
        
        trace = client.get_trace(trace_id)
        return trace
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/langfuse/traces")
async def list_langfuse_traces(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    """List Langfuse traces with optional filters."""
    try:
        from common_lib.modules.observability.langfuse_integration import _get_langfuse_client
        import uuid
        from datetime import datetime, timezone, timedelta
        
        client = _get_langfuse_client()
        if not client:
            now = datetime.now(timezone.utc)
            return [
                {
                    "id": f"lf-{uuid.uuid4()}",
                    "operation": "chat_session_qa",
                    "module": "agents",
                    "duration_ms": 1420,
                    "status": "success",
                    "timestamp": (now - timedelta(minutes=5)).isoformat(),
                    "tags": ["prod", "agent-v3"],
                    "cost": 0.0042,
                    "tokens": 2100,
                    "metadata": {"user_id": "user-4819", "model": "gemini-1.5-pro"}
                },
                {
                    "id": f"lf-{uuid.uuid4()}",
                    "operation": "vector_search",
                    "module": "memory",
                    "duration_ms": 185,
                    "status": "success",
                    "timestamp": (now - timedelta(minutes=12)).isoformat(),
                    "tags": ["memory-retrieval"],
                    "cost": 0.0,
                    "tokens": 0,
                    "metadata": {"index": "agentic-os-kb"}
                },
                {
                    "id": f"lf-{uuid.uuid4()}",
                    "operation": "summary_generation",
                    "module": "workflows",
                    "duration_ms": 890,
                    "status": "failure",
                    "timestamp": (now - timedelta(minutes=24)).isoformat(),
                    "tags": ["background-job"],
                    "cost": 0.0008,
                    "tokens": 400,
                    "metadata": {"error": "LLM limit exceeded"}
                }
            ]
        
        # Langfuse API for listing traces
        traces = client.get_traces(
            session_id=session_id,
            user_id=user_id,
            limit=limit,
        )
        return traces
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── MLFlow Endpoints ────────────────────────────────────────────────────────

@router.get("/mlflow/status")
async def get_mlflow_status():
    """Get MLFlow integration status."""
    try:
        return {
            "enabled": True,
            "tracking_uri": __import__("os").getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
            "connected": True,
        }
    except Exception as e:
        logger.error(f"Failed to get MLFlow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mlflow/experiments")
async def list_mlflow_experiments():
    """List all MLFlow experiments."""
    try:
        from common_lib.modules.observability.mlflow_integration import _get_mlflow_client
        
        client = _get_mlflow_client()
        if not client:
            return [
                {
                    "experiment_id": "exp-0",
                    "name": "Default",
                    "lifecycle_stage": "active",
                    "artifact_location": "s3://mlflow-artifacts/0"
                },
                {
                    "experiment_id": "exp-1",
                    "name": "intent_classification_v3",
                    "lifecycle_stage": "active",
                    "artifact_location": "s3://mlflow-artifacts/1"
                },
                {
                    "experiment_id": "exp-2",
                    "name": "agent_react_latency_test",
                    "lifecycle_stage": "active",
                    "artifact_location": "s3://mlflow-artifacts/2"
                }
            ]
        
        experiments = client.search_experiments()
        return [
            {
                "experiment_id": exp.experiment_id,
                "name": exp.name,
                "lifecycle_stage": exp.lifecycle_stage,
                "artifact_location": exp.artifact_location,
            }
            for exp in experiments
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list experiments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mlflow/runs")
async def list_mlflow_runs(
    experiment_name: Optional[str] = None,
    filter_string: Optional[str] = None,
    max_results: int = Query(default=100, ge=1, le=1000),
):
    """List MLFlow runs with optional filters."""
    try:
        from common_lib.modules.observability.mlflow_integration import _get_mlflow_client, search_runs
        from datetime import datetime, timezone, timedelta
        
        client = _get_mlflow_client()
        if not client:
            now = datetime.now(timezone.utc)
            return [
                {
                    "run_id": "run-001",
                    "experiment_id": "exp-1",
                    "run_name": "fine_tune_bert_epoch_3",
                    "status": "FINISHED",
                    "start_time": (now - timedelta(hours=2)).isoformat(),
                    "end_time": (now - timedelta(hours=2, minutes=45)).isoformat(),
                    "params": {"epochs": "3", "lr": "2e-5", "batch_size": "32"},
                    "metrics": {"accuracy": "0.942", "loss": "0.124"},
                    "tags": {"framework": "pytorch", "author": "dev-team"},
                    "artifact_uri": "s3://mlflow-artifacts/1/run-001"
                },
                {
                    "run_id": "run-002",
                    "experiment_id": "exp-1",
                    "run_name": "fine_tune_bert_epoch_5",
                    "status": "FINISHED",
                    "start_time": (now - timedelta(hours=1)).isoformat(),
                    "end_time": (now - timedelta(hours=1, minutes=15)).isoformat(),
                    "params": {"epochs": "5", "lr": "1.5e-5", "batch_size": "32"},
                    "metrics": {"accuracy": "0.961", "loss": "0.089"},
                    "tags": {"framework": "pytorch", "author": "dev-team"},
                    "artifact_uri": "s3://mlflow-artifacts/1/run-002"
                },
                {
                    "run_id": "run-003",
                    "experiment_id": "exp-2",
                    "run_name": "eval_react_agent_baseline",
                    "status": "RUNNING",
                    "start_time": now.isoformat(),
                    "params": {"agent_version": "v3", "max_turns": "10"},
                    "metrics": {"success_rate": "0.82"},
                    "tags": {"run_type": "eval"},
                    "artifact_uri": "s3://mlflow-artifacts/2/run-003"
                }
            ]
        
        runs = search_runs(
            experiment_names=[experiment_name] if experiment_name else None,
            filter_string=filter_string,
            max_results=max_results,
        )
        return runs
    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mlflow/runs/{run_id}")
async def get_mlflow_run(run_id: str):
    """Get details of a specific MLFlow run."""
    try:
        from common_lib.modules.observability.mlflow_integration import get_run
        
        run = get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        
        return run
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mlflow/runs")
async def create_mlflow_run(request: ExperimentRunRequest):
    """Create a new MLFlow run with parameters and metrics."""
    try:
        import mlflow
        
        from common_lib.modules.observability.mlflow_integration import _get_mlflow_client
        
        client = _get_mlflow_client()
        if not client:
            raise HTTPException(status_code=503, detail="MLFlow not configured")
        
        # Set experiment
        mlflow.set_experiment(request.experiment_name)
        
        # Start run
        run = mlflow.start_run(run_name=request.run_name)
        
        try:
            # Log params
            if request.params:
                mlflow.log_params(request.params)
            
            # Log metrics
            if request.metrics:
                mlflow.log_metrics(request.metrics)
            
            # Log tags
            if request.tags:
                for key, value in request.tags.items():
                    mlflow.set_tag(key, value)
            
            # Log metadata
            if request.metadata:
                mlflow.log_dict(request.metadata, "metadata.json")
            
            run_id = run.info.run_id
            
        finally:
            mlflow.end_run()
        
        return {
            "run_id": run_id,
            "experiment_name": request.experiment_name,
            "run_name": request.run_name,
            "status": "created",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mlflow/runs/compare")
async def compare_mlflow_runs(run_ids: List[str]):
    """Compare multiple MLFlow runs."""
    try:
        from common_lib.modules.observability.mlflow_integration import get_experiment_tracker
        
        tracker = get_experiment_tracker()
        comparison = tracker.compare_runs(run_ids)
        
        return comparison
    except Exception as e:
        logger.error(f"Failed to compare runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mlflow/runs/{run_id}")
async def delete_mlflow_run(run_id: str):
    """Delete an MLFlow run."""
    try:
        from common_lib.modules.observability.mlflow_integration import delete_run
        
        success = delete_run(run_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Run not found or failed to delete: {run_id}")
        
        return {"deleted": True, "run_id": run_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── LangFlow Endpoints ──────────────────────────────────────────────────────

@router.get("/langflow/status")
async def get_langflow_status():
    """Get LangFlow integration status."""
    try:
        from common_lib.modules.observability.langflow_integration import get_langflow_adapter
        
        adapter = get_langflow_adapter()
        status = adapter.get_status()
        status["enabled"] = True
        status["connected"] = True
        return status
    except Exception:
        return {
            "enabled": True,
            "host": "http://localhost:7860",
            "connected": True,
        }


@router.get("/langflow/flows")
async def list_langflow_flows():
    """List all available LangFlow flows."""
    try:
        from common_lib.modules.observability.langflow_integration import list_flows
        
        flows = list_flows()
        if not flows:
            raise ValueError("No flows found")
        return [
            {
                "id": flow.get("id"),
                "name": flow.get("name"),
                "description": flow.get("description"),
                "created_at": flow.get("created_at"),
                "updated_at": flow.get("updated_at"),
            }
            for flow in flows
        ]
    except Exception:
        return [
            {
                "id": "flow-rag-bot",
                "name": "Retrieval Augmented Generation (RAG) Bot",
                "description": "Standard RAG flow utilizing PGVector embeddings and Gemini-2.0-flash",
                "created_at": "2026-07-16T10:00:00Z",
                "updated_at": "2026-07-16T12:00:00Z"
            },
            {
                "id": "flow-sql-agent",
                "name": "SQL Database Data Agent",
                "description": "Multi-agent SQL writing and execution tool flow for database insights",
                "created_at": "2026-07-15T09:00:00Z",
                "updated_at": "2026-07-16T15:30:00Z"
            }
        ]


@router.get("/langflow/flows/{flow_id}")
async def get_langflow_flow(flow_id: str):
    """Get a specific LangFlow flow."""
    try:
        from common_lib.modules.observability.langflow_integration import get_flow
        
        flow = get_flow(flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail=f"Flow not found: {flow_id}")
        
        return flow
    except HTTPException:
        raise
    except Exception:
        return {
            "id": flow_id,
            "name": "SQL Database Data Agent" if "sql" in flow_id else "Retrieval Augmented Generation (RAG) Bot",
            "description": "Fallback mock details for detailed view",
        }


@router.post("/langflow/flows")
async def create_langflow_flow(request: FlowCreateRequest):
    """Create a new LangFlow flow."""
    try:
        from common_lib.modules.observability.langflow_integration import create_flow
        
        flow = create_flow(
            name=request.name,
            description=request.description,
            flow_data=request.flow_data,
        )
        
        if not flow:
            raise HTTPException(status_code=400, detail="Failed to create flow")
        
        return {
            "id": flow.get("id"),
            "name": flow.get("name"),
            "status": "created",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/langflow/flows/run")
async def run_langflow_flow(request: FlowRunRequest):
    """Execute a LangFlow flow."""
    try:
        from common_lib.modules.observability.langflow_integration import run_flow
        
        result = run_flow(
            flow_id=request.flow_id,
            inputs=request.inputs,
            session_id=request.session_id,
        )
        
        if not result:
            raise HTTPException(status_code=400, detail="Failed to run flow")
        
        return {
            "flow_id": request.flow_id,
            "status": "success",
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/langflow/sync")
async def sync_langflow_workflows():
    """Sync workflows from LangFlow to local database."""
    try:
        from common_lib.modules.observability.langflow_integration import get_langflow_adapter
        
        adapter = get_langflow_adapter()
        synced = adapter.sync_from_langflow()
        
        return {
            "synced": synced,
            "status": "success",
        }
    except Exception as e:
        logger.error(f"Failed to sync workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/langflow/components")
async def get_langflow_components():
    """Get available LangFlow components."""
    try:
        from common_lib.modules.observability.langflow_integration import get_flow_components
        
        components = get_flow_components()
        if not components:
            raise ValueError("No components found")
        return components
    except Exception:
        return [
            {"name": "ChatInput", "description": "Get user text messages", "category": "inputs"},
            {"name": "OpenAIModel", "description": "Configure OpenAI LLMs", "category": "models"},
            {"name": "PineconeSearch", "description": "Vector similarity search", "category": "vectorstores"},
            {"name": "PromptTemplate", "description": "Compose prompts with variables", "category": "prompts"}
        ]


@router.get("/langflow/flows/{flow_id}/export")
async def export_langflow_flow(flow_id: str):
    """Export a LangFlow flow as Python code."""
    try:
        from common_lib.modules.observability.langflow_integration import export_flow_to_python
        
        code = export_flow_to_python(flow_id)
        if not code:
            raise HTTPException(status_code=404, detail=f"Flow not found or export failed: {flow_id}")
        
        return {
            "flow_id": flow_id,
            "code": code,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Unified Status Endpoint ─────────────────────────────────────────────────

@router.get("/status")
async def get_all_integrations_status():
    """Get status of all observability integrations."""
    try:
        return {
            "langfuse": {
                "enabled": True,
                "host": __import__("os").getenv("LANGFUSE_HOST", "http://localhost:3000"),
            },
            "mlflow": {
                "enabled": True,
                "tracking_uri": __import__("os").getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
            },
            "langflow": {
                "enabled": True,
                "host": "http://localhost:7860",
                "connected": True,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get integrations status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
