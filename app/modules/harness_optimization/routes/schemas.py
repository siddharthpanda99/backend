"""API schemas for Harness Optimization Service.

These are the Pydantic models for FastAPI request/response validation.
They mirror the SQLModel domain models but are separate for API versioning.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, conint, confloat


# ═══════════════════════════════════════════════════════════════════
# Base / Common
# ═══════════════════════════════════════════════════════════════════


class HarnessBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    domain: str = Field(..., min_length=1, max_length=100)
    owner_id: str = Field(..., min_length=1)
    visibility: str = Field(
        default="private", pattern="^(private|team|tenant|platform_template)$"
    )


class HarnessCreate(HarnessBase):
    tenant_id: Optional[str] = None


class HarnessUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    domain: Optional[str] = Field(None, min_length=1, max_length=100)
    visibility: Optional[str] = Field(
        None, pattern="^(private|team|tenant|platform_template)$"
    )


class HarnessRead(HarnessBase):
    id: UUID
    tenant_id: Optional[str]
    current_approved_version_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════
# Harness Versions
# ══════════════════════════════════════════════════════════════════


class HarnessVersionBase(BaseModel):
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    component_manifest_json: Dict[str, Any]
    parent_version_id: Optional[UUID] = None
    policy_bundle_id: Optional[str] = None
    policy_bundle_version: Optional[str] = None
    model_profile_id: Optional[str] = None
    pinned_model_ids: Dict[str, str] = Field(default_factory=dict)
    tool_catalog_snapshot_id: Optional[str] = None
    skill_snapshot_ids: List[str] = Field(default_factory=list)
    memory_policy_version: Optional[str] = None


class HarnessVersionCreate(HarnessVersionBase):
    harness_id: UUID
    created_by: str


class HarnessVersionRead(HarnessVersionBase):
    id: UUID
    harness_id: UUID
    status: str
    rendered_harness_hash: Optional[str]
    created_by: str
    approved_by: Optional[str]
    created_at: datetime
    approved_at: Optional[datetime]

    class Config:
        from_attributes = True


class HarnessVersionApprove(BaseModel):
    approver_id: str


# ═══════════════════════════════════════════════════════════════════
# Optimization Runs
# ═══════════════════════════════════════════════════════════════════


class BudgetSchema(BaseModel):
    max_wall_clock_seconds: conint(ge=1) = 300
    max_model_calls: conint(ge=1) = 20
    max_tool_calls: conint(ge=1) = 60
    max_cost_estimate: confloat(ge=0) = 1.5
    max_artifact_bytes: conint(ge=0) = 10_000_000
    max_subagent_depth: conint(ge=0) = 3
    max_retries: conint(ge=0) = 2


class RunCreate(BaseModel):
    tenant_id: str
    requested_by: str
    task_id: Optional[str] = None
    base_harness_version_id: UUID
    mode: str = Field(default="parallel", pattern="^(parallel|sequential)$")
    recursion_budget_k: conint(ge=1, le=3) = 1
    seed: Optional[int] = None
    executor_substrate: str = "nexus"
    model_profile_id: Optional[str] = None
    evaluation_suite_id: Optional[str] = None
    budget: BudgetSchema = Field(default_factory=BudgetSchema)
    promotion_policy: str = "never_auto_promote"
    dry_run: bool = False


class RunRead(BaseModel):
    id: UUID
    tenant_id: str
    requested_by: str
    task_id: Optional[str]
    base_harness_version_id: UUID
    status: str
    mode: str
    recursion_budget_k: int
    seed: Optional[int]
    executor_substrate: str
    model_profile_id: Optional[str]
    evaluation_suite_id: Optional[str]
    budget_json: Dict[str, Any]
    policy_decision_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    failure_code: Optional[str]
    failure_detail: Optional[str]

    class Config:
        from_attributes = True


class RunTransition(BaseModel):
    new_status: str
    reason: str = ""


# ═══════════════════════════════════════════════════════════════════
# Candidates & Executions
# ═══════════════════════════════════════════════════════════════════


class CandidatePatch(BaseModel):
    component: str
    operation: str = Field(..., pattern="^(replace_section|append|remove|modify)$")
    path: str
    content: Any


class CandidateCreate(BaseModel):
    run_id: UUID
    candidate_index: int
    scope: str = Field(
        default="general",
        pattern="^(general|domain_specific|sequential_step|composition)$",
    )
    parent_candidate_id: Optional[UUID] = None
    proposed_patch_json: Dict[str, Any]
    candidate_harness_version_id: Optional[UUID] = None
    proposer_model_id: Optional[str] = None


class CandidateRead(BaseModel):
    id: UUID
    run_id: UUID
    candidate_index: int
    scope: str
    parent_candidate_id: Optional[UUID]
    proposed_patch_json: Dict[str, Any]
    candidate_harness_version_id: Optional[UUID]
    status: str
    proposer_model_id: Optional[str]
    evaluated_at: Optional[datetime]
    adopted_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ExecutionRead(BaseModel):
    id: UUID
    run_id: UUID
    candidate_harness_id: Optional[UUID]
    execution_role: str
    task_snapshot_hash: str
    harness_hash: str
    model_id: str
    model_revision: Optional[str]
    inference_config_hash: Optional[str]
    executor_version: str
    container_digest: Optional[str]
    tool_catalog_snapshot_id: str
    status: str
    exit_code: Optional[int]
    started_at: datetime
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    input_tokens: int
    output_tokens: int
    tool_call_count: int
    estimated_cost: float
    resource_usage_json: Dict[str, Any]
    output_artifact_id: Optional[UUID]
    trace_id: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════
# Evidence & Evaluation
# ═══════════════════════════════════════════════════════════════════


class EvidenceRead(BaseModel):
    id: UUID
    run_id: UUID
    task_id: Optional[str]
    baseline_execution_id: Optional[UUID]
    candidate_execution_id: Optional[UUID]
    evidence_type: str
    observation: str
    supporting_event_refs: List[str] = Field(default_factory=list)
    supporting_artifact_refs: List[str] = Field(default_factory=list)
    confidence: confloat(ge=0, le=1)
    derivation_method: str
    safe_for_model: bool = True
    evaluator_version: str
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationRequest(BaseModel):
    run_id: UUID
    harness_version_id: UUID
    execution_id: UUID
    baseline_execution_id: Optional[UUID] = None
    candidate_execution_id: Optional[UUID] = None
    evaluator_suite_id: str


class EvaluationRead(BaseModel):
    evaluation_id: UUID
    dimension_scores: Dict[str, float]
    categorical_outcomes: Dict[str, str]
    structured_findings: List[Dict[str, Any]]
    confidence: confloat(ge=0, le=1)
    passed_gates: List[str]
    failed_gates: List[str]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════
# Lessons
# ═══════════════════════════════════════════════════════════════════


class LessonBase(BaseModel):
    statement: str = Field(..., min_length=1, max_length=5000)
    operational_recommendation: str = Field(..., min_length=1, max_length=5000)
    domain_scope: str = Field(..., min_length=1, max_length=100)
    evidence_refs: List[UUID] = Field(default_factory=list)
    source_run_id: UUID
    source_task_id: Optional[str] = None
    confidence: confloat(ge=0, le=1) = 0.0
    known_counterexamples: List[str] = Field(default_factory=list)
    applicable_component_types: List[str] = Field(default_factory=list)
    applicability_conditions: Dict[str, Any] = Field(default_factory=dict)
    expiry_days: conint(ge=1, le=365) = 90
    revalidation_policy: str = "manual"


class LessonCreate(LessonBase):
    tenant_id: str
    author_id: str = "system"


class LessonRead(LessonBase):
    id: UUID
    tenant_id: str
    source_run_id: UUID
    support_count: int
    status: str
    author_id: str
    approver_id: Optional[str]
    embedding_ref: Optional[str]
    content_hash: str
    version: int
    expiry_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LessonStatusUpdate(BaseModel):
    new_status: str = Field(..., pattern="^(candidate|approved|deprecated|rejected)$")
    approver_id: Optional[str] = None


class LessonsForHarnessQuery(BaseModel):
    component_type: Optional[str] = None
    min_confidence: confloat(ge=0, le=1) = 0.0


# ═══════════════════════════════════════════════════════════════════
# Promotions
# ═══════════════════════════════════════════════════════════════════


class PromotionCreate(BaseModel):
    harness_id: UUID
    from_version_id: UUID
    to_version_id: UUID
    target_scope: str = Field(..., pattern="^(canary|staged|full)$")
    rollout_strategy: str = Field(..., pattern="^(progressive|immediate)$")
    approver_id: str
    evaluation_package_ref: str
    rollback_version_id: Optional[UUID] = None


class PromotionRead(BaseModel):
    id: UUID
    harness_id: UUID
    from_version_id: UUID
    to_version_id: UUID
    target_scope: str
    rollout_strategy: str
    approver_id: str
    evaluation_package_ref: str
    rollback_version_id: Optional[UUID]
    status: str
    requested_at: datetime
    approved_at: Optional[datetime]
    rolled_out_at: Optional[datetime]
    rolled_back_at: Optional[datetime]

    class Config:
        from_attributes = True


class PromotionApprove(BaseModel):
    approver_id: str


class PromotionRollout(BaseModel):
    rolled_out_by: str


class RollbackRequest(BaseModel):
    harness_id: UUID
    target_version_id: UUID
    requester_id: str


# ═══════════════════════════════════════════════════════════════════
# Trace Events
# ═══════════════════════════════════════════════════════════════════


class TraceEventRead(BaseModel):
    execution_id: UUID
    sequence_number: int
    event_type: str
    tool_model_identifiers: Dict[str, str]
    payload_ref: Optional[str]
    duration_ms: Optional[int]
    status: str
    retry_count: int
    policy_decision_ref: Optional[str]
    side_effect_classification: str
    checksum: str

    class Config:
        from_attributes = True


class TraceSummaryRead(BaseModel):
    execution_id: str
    total_events: int
    event_types: List[str]
    total_duration_ms: int
    statuses: List[str]
    first_sequence: int
    last_sequence: int


# ═══════════════════════════════════════════════════════════════════
# Sandbox
# ═══════════════════════════════════════════════════════════════════


class SandboxConfigSchema(BaseModel):
    network_mode: str = Field(default="none", pattern="^(none|bridge)$")
    read_only_fs: bool = True
    cpu_limit: confloat(gt=0) = 1.0
    memory_limit_mb: conint(gt=0) = 512
    timeout_seconds: conint(gt=0) = 300
    cap_drop: str = "ALL"
    security_opt: str = "no-new-privileges:true"
    max_output_size: conint(gt=0) = 1_000_000
    userns_remap: Optional[str] = None
    seccomp_profile: Optional[str] = None
    apparmor_profile: Optional[str] = None
    rootless: bool = False
    verify_image: bool = False
    allowed_syscalls: Optional[List[int]] = None
    cap_keep: Optional[List[str]] = None
    seccomp_notify: bool = False


class SandboxRunRequest(BaseModel):
    image: str = "python:3.12-slim"
    command: Optional[str] = None
    environment: Optional[Dict[str, str]] = None
    volumes: Optional[Dict[str, Dict[str, str]]] = None
    sandbox_config: Optional[SandboxConfigSchema] = None


class SandboxRunResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class SandboxHealthCheck(BaseModel):
    status: str
    docker_version: Optional[str] = None
    containers_running: int


# ═══════════════════════════════════════════════════════════════════
# Trace Collector
# ═══════════════════════════════════════════════════════════════════


class TraceCollectorStart(BaseModel):
    tenant_id: Optional[str] = None


class TraceCollectorStatus(BaseModel):
    status: str
    tenant_id: Optional[str]


class TraceEventsQuery(BaseModel):
    from_sequence: int = 0
    tenant_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# Pagination
# ═══════════════════════════════════════════════════════════════════


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
