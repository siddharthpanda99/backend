"""Decision Engine MCP Tools.

Provides MCP tool access to decision engine operations:
- decide: Run cascaded decision engine (tiers 1-5)
- ground: Run grounding pipeline
- build_plan: Build decision graph from decisions
- approve_plan: Approve/reject/modify a plan
- compile_plan: Compile approved plan into execution contract
- get_contract: Get execution contract by ID
- register_model: Register a new decision model
- calibrate_model: Calibrate a model on a dataset
- get_thresholds: Get current threshold policy
- update_thresholds: Update threshold policy
- get_decision_provenance: Get provenance for a decision
- get_plan_provenance: Get provenance for a full plan
- list_plan_decisions: List all decision provenances for a plan
"""

from typing import Any, Annotated
from fastapi import Depends
from pydantic import BaseModel, Field

from common_lib.modules.decision_engine.services import (
    DecisionEngineService,
    DecisionRegistryService,
    ApprovalService,
)
from common_lib.modules.decision_engine.schemas import (
    DecideRequest,
    DecideResponse,
    GroundRequest,
    GroundResponse,
    PlanCreateRequest,
    PlanRead,
    PlanApproveRequest,
    CompilePlanRequest,
    ContractRead,
    DecisionModelSpecCreate,
    DecisionModelSpecRead,
    DecisionModelSpecList,
    CalibrationRequest,
    CalibrationResponse,
    ThresholdPolicyRead,
    ThresholdPolicyUpdate,
    ProvenanceRead,
    ProvenanceList,
    PlanProvenanceRead,
)


# Service instances (singletons)
_decision_service = DecisionEngineService()
_approval_service = ApprovalService()
_registry_service = DecisionRegistryService()


# Request/Response models for MCP
class IngestRequest(BaseModel):
    text: str
    context: dict[str, Any] | None = None
    user_id: str | None = None
    tenant_id: str | None = None


class IngestResponse(BaseModel):
    goal_spec: dict[str, Any]
    status: str = "success"


class GroundRequest(BaseModel):
    plan_id: str
    node_id: str | None = None
    claims: list[dict[str, Any]] | None = None
    evidence: list[dict[str, Any]] | None = None


class GroundResponse(BaseModel):
    grounding_coverage: dict[str, Any]
    status: str = "success"


class DecideRequest(BaseModel):
    state: dict[str, Any]
    decision_type: str = "ROUTING"
    options: list[dict[str, Any]] | None = None


class DecideResponse(BaseModel):
    decision: dict[str, Any]
    status: str = "success"


class PlanCreateRequest(BaseModel):
    goal: str
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    execution_policy: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)


class PlanApproveRequest(BaseModel):
    reviewer: str
    decision: str = "approved"
    comments: str = ""
    changes: list[dict[str, Any]] = Field(default_factory=list)


class CompilePlanRequest(BaseModel):
    execution_policy: dict[str, Any] | None = None


class ContractRead(BaseModel):
    plan_id: str
    plan_version: int
    allowed_tools: list[str]
    allowed_agents: list[str]
    allowed_domains: list[str]
    denied_tools: list[str]
    denied_agents: list[str]
    max_cost: float
    max_steps: int
    max_duration_seconds: int
    requires_human_review: bool
    required_evidence_coverage: float
    critical_claim_coverage: float
    output_schema: str
    adaptation_policy: str
    max_adaptations: int
    allowed_adaptation_types: list[str]


class DecisionModelSpecCreate(BaseModel):
    id: str
    type: str
    framework: str
    input_schema: str
    output_schema: str
    calibration: dict[str, Any]
    thresholds: dict[str, Any]
    version: int
    artifact_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionModelSpecRead(BaseModel):
    id: str
    type: str
    framework: str
    input_schema: str
    output_schema: str
    calibration: dict[str, Any]
    thresholds: dict[str, Any]
    version: int
    artifact_path: str
    metadata: dict[str, Any]


class DecisionModelSpecList(BaseModel):
    items: list[DecisionModelSpecRead]


class CalibrationRequest(BaseModel):
    dataset: str
    method: str = "temperature"
    parameters: dict[str, Any] = Field(default_factory=dict)


class CalibrationResponse(BaseModel):
    calibration_spec: dict[str, Any]
    status: str = "success"


class ThresholdPolicyRead(BaseModel):
    global_autonomous_min: float
    global_review_min: float
    global_review_max: float
    global_abstain_max: float
    per_decision_type: dict[str, dict[str, float]]
    per_model: dict[str, dict[str, float]]


class ThresholdPolicyUpdate(BaseModel):
    global_autonomous_min: float | None = None
    global_review_min: float | None = None
    global_review_max: float | None = None
    global_abstain_max: float | None = None
    per_decision_type: dict[str, dict[str, float]] | None = None
    per_model: dict[str, dict[str, float]] | None = None


class ProvenanceRead(BaseModel):
    decision_id: str
    model_id: str
    model_version: str
    model_type: str
    calibration_version: str
    inputs: list[str]
    output: str | None = None
    confidence: float
    threshold_applied: float
    status: str
    risk_overall: float
    action_category: str
    reasoning: str
    resolved_at: str | None = None


class ProvenanceList(BaseModel):
    items: list[ProvenanceRead]


class PlanProvenanceRead(BaseModel):
    plan_id: str
    plan_version: int
    goal_spec_id: str
    decisions: list[ProvenanceRead]
    models_used: dict[str, str]
    calibrations_used: list[str]
    evidence_ids: list[str]
    memory_ids: list[str]
    policy_version: str


async def ingest_intent(request: IngestRequest) -> IngestResponse:
    """Parse user request into structured goal specification."""
    try:
        result = _decision_service.ingest_intent(request)
        return IngestResponse(goal_spec=result, status="success")
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Ingestion failed: {e}")


async def ground_claims(request: GroundRequest) -> GroundResponse:
    """Run grounding pipeline: extract claims, retrieve evidence, verify, compute coverage."""
    try:
        from common_lib.modules.decision_engine.services import DecisionEngineService

        service = DecisionEngineService()
        result = service.ground_claims(request)
        return GroundResponse(grounding_coverage=result, status="success")
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Grounding failed: {e}")


async def decide(request: DecideRequest) -> DecideResponse:
    """Run cascaded decision engine (tiers 1-5) and return decision."""
    try:
        from common_lib.modules.decision_engine.services import DecisionEngineService

        service = DecisionEngineService()
        result = service.route_decision(request)
        return DecideResponse(decision=result, status="success")
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Decision failed: {e}")


async def build_plan(request: PlanCreateRequest) -> dict:
    """Build decision plan from decisions and goal."""
    try:
        from common_lib.modules.decision_engine.services import DecisionEngineService

        service = DecisionEngineService()
        plan = service.build_plan(request)
        return plan
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Plan build failed: {e}")


async def approve_plan(plan_id: str, request: PlanApproveRequest) -> dict:
    """Approve, reject, or modify a plan."""
    try:
        plan = _approval_service.approve(plan_id, request)
        if not plan:
            raise ValueError("Plan not found")
        return plan
    except Exception as e:
        raise Exception(f"Approval failed: {e}")


async def compile_plan(plan_id: str, request: CompilePlanRequest) -> ContractRead:
    """Compile approved plan into execution contract."""
    try:
        contract = _decision_service.compile_plan(plan_id, request)
        return ContractRead.model_validate(contract)
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Compilation failed: {e}")


async def register_model(request: DecisionModelSpecCreate) -> dict:
    """Register a new decision model."""
    try:
        model = _registry_service.register_model(request)
        return model
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Register model failed: {e}")


async def calibrate_model(
    model_id: str, request: CalibrationRequest
) -> CalibrationResponse:
    """Calibrate a model on a dataset."""
    try:
        result = _registry_service.calibrate_model(model_id, request)
        return CalibrationResponse(calibration_spec=result, status="success")
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Calibration failed: {e}")


async def get_thresholds() -> dict:
    """Get current threshold policy."""
    try:
        policy = _registry_service.get_thresholds()
        return policy
    except Exception as e:
        raise Exception(f"Get thresholds failed: {e}")


async def update_thresholds(request: dict) -> dict:
    """Update threshold policy."""
    try:
        policy = _registry_service.update_thresholds(request)
        return policy
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Update thresholds failed: {e}")


async def get_decision_provenance(decision_id: str) -> dict:
    """Get provenance for a single decision."""
    try:
        prov = _registry_service.get_decision_provenance(decision_id)
        if not prov:
            raise ValueError("Provenance not found")
        return prov
    except Exception as e:
        raise Exception(f"Get provenance failed: {e}")


async def get_plan_provenance(plan_id: str) -> dict:
    """Get provenance for a full plan."""
    try:
        prov = _registry_service.get_plan_provenance(plan_id)
        if not prov:
            raise ValueError("Plan provenance not found")
        return prov
    except Exception as e:
        raise Exception(f"Get plan provenance failed: {e}")


async def list_plan_decisions(plan_id: str) -> dict:
    """List all decision provenances for a plan."""
    try:
        provs = _registry_service.list_plan_decisions(plan_id)
        return {
            "items": [
                {
                    "decision_id": p.get("decision_id", ""),
                    "model_id": p.get("model_id", ""),
                }
                for p in provs
            ]
        }
    except Exception as e:
        raise Exception(f"List decisions failed: {e}")


def register_decision_engine_tools(mcp) -> int:
    """Register all decision engine tools with the MCP server."""
    tools = [
        (
            "ingest_intent",
            ingest_intent,
            "Parse user request into structured goal specification",
        ),
        (
            "ground_claims",
            ground_claims,
            "Run grounding pipeline: extract claims, retrieve evidence, verify, compute coverage",
        ),
        (
            "decide",
            decide,
            "Run cascaded decision engine (tiers 1-5) and return decision",
        ),
        ("build_plan", build_plan, "Build decision plan from decisions and goal"),
        ("approve_plan", approve_plan, "Approve, reject, or modify a plan"),
        ("compile_plan", compile_plan, "Compile approved plan into execution contract"),
        ("register_model", register_model, "Register a new decision model"),
        ("calibrate_model", calibrate_model, "Calibrate a model on a dataset"),
        ("get_thresholds", get_thresholds, "Get current threshold policy"),
        ("update_thresholds", update_thresholds, "Update threshold policy"),
        (
            "get_decision_provenance",
            get_decision_provenance,
            "Get provenance for a single decision",
        ),
        ("get_plan_provenance", get_plan_provenance, "Get provenance for a full plan"),
        (
            "list_plan_decisions",
            list_plan_decisions,
            "List all decision provenances for a plan",
        ),
    ]

    count = 0
    for name, func, description in tools:
        try:
            mcp.tool(name=name, description=description)(func)
            count += 1
        except Exception as e:
            print(f"Failed to register {name}: {e}")

    return count
