"""Wire models for the Character Studio REST layer.

These mirror ``common_lib.modules.image_processing.character_studio
.schemas`` (and ``...models`` SQLModel rows) field-for-field, and are kept
local to this module so the HTTP layer imports without pulling the whole
character_studio package at decorator time. ``from_attributes=True``
everywhere, so SQLModel rows and pydantic payloads both validate.

Drift policy: when the common_lib schemas change, update these mirrors in
the same change. The HTTP wire contract is the SSOT a frontend depends on.

Two shapes exist only here:
- ``EvaluateResponseContract`` — the public evaluate endpoint response.
- ``ListResponse`` / ``ItemsResponse`` — generic list envelopes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


# ── List envelopes ───────────────────────────────────────────────────────


class ListResponse(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    total: int = 0


class ItemsResponse(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list)


# ── Response models (mirror common_lib schemas) ──────────────────────────


class CharacterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    character_id: str
    name: str
    description: Optional[str] = None
    use_cases: List[str] = Field(default_factory=list)
    intended_styles: List[str] = Field(default_factory=list)
    owner_id: Optional[str] = None
    status: str
    current_identity_version: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None


class DNARead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dna_id: UUID
    character_id: str
    name: str
    version: str = "1.0.0"
    status: str = "draft"
    apparent_age_range: Optional[str] = None
    face_shape: Optional[str] = None
    jawline: Optional[str] = None
    cheekbones: Optional[str] = None
    eye_shape: Optional[str] = None
    eye_color: Optional[str] = None
    eye_spacing: Optional[str] = None
    nose_type: Optional[str] = None
    lip_type: Optional[str] = None
    skin_tone: Optional[str] = None
    skin_texture: Optional[str] = None
    hair_color: Optional[str] = None
    hair_texture: Optional[str] = None
    hair_length: Optional[str] = None
    hair_style_policy: Optional[str] = "variable"
    body_build: Optional[str] = None
    shoulders: Optional[str] = None
    waist: Optional[str] = None
    legs: Optional[str] = None
    silhouette: Optional[str] = None
    distinctive_features: List[str] = Field(default_factory=list)
    attribute_policies: Dict[str, str] = Field(default_factory=dict)
    reference_assets: Dict[str, str] = Field(default_factory=dict)
    preferred_profiles: List[str] = Field(default_factory=list)
    lora_policy: str = "avoid_unless_explicitly_enabled"
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    similarity_threshold: Optional[float] = None
    quality_threshold: Optional[float] = None


class IdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    identity_id: UUID
    character_id: str
    version: str
    status: str = "draft"
    face_profile_id: Optional[UUID] = None
    body_profile_id: Optional[UUID] = None
    attribute_policies: Dict[str, str] = Field(default_factory=dict)
    reference_assets: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    superseded_by: Optional[UUID] = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    character_id: str
    identity_version: str
    asset_id_str: str
    category: str
    subcategory: Optional[str] = None
    view_angle: Optional[str] = None
    expression: Optional[str] = None
    pose: Optional[str] = None
    style: Optional[str] = None
    outfit_id: Optional[str] = None
    source_job_id: Optional[UUID] = None
    source_references: List[UUID] = Field(default_factory=list)
    workflow_version: Optional[str] = None
    width: int
    height: int
    format: str = "png"
    file_hash: str
    file_size: int
    file_path: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    approval_status: str
    quality_score: Optional[float] = None
    face_similarity: Optional[float] = None
    body_consistency: Optional[float] = None
    feature_consistency: Optional[float] = None
    style_consistency: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None


class OutfitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    outfit_id: UUID
    character_id: str
    identity_version: str
    outfit_name: str
    category: str
    front_asset_id: Optional[UUID] = None
    back_asset_id: Optional[UUID] = None
    left_asset_id: Optional[UUID] = None
    right_asset_id: Optional[UUID] = None
    materials: List[str] = Field(default_factory=list)
    colors: List[str] = Field(default_factory=list)
    accessories: List[str] = Field(default_factory=list)
    is_canonical: bool = False
    tags: List[str] = Field(default_factory=list)
    approval_status: str
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None


class StyleProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: UUID
    character_id: str
    profile_name: str
    rendering: str
    line_weight: Optional[str] = None
    shading: Optional[str] = None
    color_palette: Optional[str] = None
    texture: Optional[str] = None
    anatomy: Optional[str] = None
    consistency_policy: str = "strict"
    preferred_checkpoints: List[str] = Field(default_factory=list)
    compatible_conditioning: List[str] = Field(default_factory=list)
    evaluation_strategy: str = "strict"
    is_default: bool = False
    created_at: datetime
    updated_at: datetime


class GenerationProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: UUID
    character_id: str
    profile_name: str
    model_provider: str
    checkpoint: str
    style_profile_id: Optional[UUID] = None
    face_identity_conditioning: bool = True
    body_reference_conditioning: bool = False
    pose_control: bool = False
    style_reference_conditioning: bool = False
    default_steps: int = 30
    default_cfg: float = 7.0
    default_sampler: str = "euler_ancestral"
    default_scheduler: str = "karras"
    evaluation_policy: str = "strict"
    similarity_threshold: float = 0.75
    quality_threshold: float = 0.6
    created_at: datetime
    updated_at: datetime


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    character_id: str
    intent: str
    provider: str
    style_profile: Optional[str] = None
    checkpoint: Optional[str] = None
    engine: Optional[str] = None
    steps: Optional[int] = None
    cfg: Optional[float] = None
    seed: Optional[int] = None
    policy: Optional[str] = None
    prompt_override: Optional[str] = None
    count: int = 1
    status: str
    evaluation: Optional[Dict[str, Any]] = None
    generation_profile_id: Optional[UUID] = None
    output_path: Optional[str] = None
    output_paths: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: UUID
    asset_id: UUID
    character_id: str
    reference_asset_id: Optional[UUID] = None
    reference_source: Optional[str] = None
    similarity: float
    verdict: str
    method: str
    created_at: datetime


class EvaluateResponseContract(BaseModel):
    """Public evaluate-endpoint response.

    Carries everything the caller is promised; unknown keys in the backing
    payload are ignored. ``details`` is optional structured context.
    """

    model_config = ConfigDict(extra="ignore")

    asset_id: UUID
    character_id: Optional[str] = None
    similarity: float
    verdict: str
    method: Optional[str] = None
    evaluation_id: Optional[UUID] = None
    reference_asset_id: Optional[UUID] = None
    reference_source: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ExportBundleRead(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    manifest: Dict[str, Any] = Field(default_factory=dict)
    files: List[str] = Field(default_factory=list)
    output_dir: str = ""
    export_kind: str = ""


# ── Request bodies ───────────────────────────────────────────────────────


class CharacterCreateBody(BaseModel):
    character_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""


class CharacterPatchBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class DnaUpsertBody(BaseModel):
    """Character DNA upsert body.

    The explicit identity-lock fields and every extra DNA attribute land in
    ``attribute_policies`` (the platform's identity-lock carrier — see
    ``selector.dna_identity_lock_source``). ``similarity_threshold`` is a
    first-class DNA column.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    version: str = Field(default="1.0.0", min_length=1)
    identity_lock_method: Optional[str] = None
    identity_lock_source: Optional[str] = None
    similarity_threshold: Optional[float] = None
    quality_threshold: Optional[float] = None
    attribute_policies: Dict[str, str] = Field(default_factory=dict)


class IdentityVersionBody(BaseModel):
    version: str = Field(min_length=1)
    face_profile_id: Optional[UUID] = None
    body_profile_id: Optional[UUID] = None


class ReferenceCreateBody(BaseModel):
    asset_id_str: str = Field(min_length=1)
    category: str = Field(min_length=1)
    subcategory: Optional[str] = None
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    file_size: int = Field(ge=0)
    format: str = "png"
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1)


class RejectBody(BaseModel):
    reason: Optional[str] = None


class OutfitCreateBody(BaseModel):
    outfit_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    materials: List[str] = Field(default_factory=list)
    colors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class StyleProfileCreateBody(BaseModel):
    profile_name: str = Field(min_length=1)
    rendering: str = Field(min_length=1)
    consistency_policy: str = "strict"
    is_default: bool = False


class GenerationProfileCreateBody(BaseModel):
    profile_name: str = Field(min_length=1)
    model_provider: str = Field(min_length=1)
    checkpoint: str = Field(min_length=1)
    face_identity_conditioning: bool = True
    default_steps: int = Field(default=30, ge=1)
    default_cfg: float = Field(default=7.0, gt=0.0)
    evaluation_policy: str = "strict"
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    quality_threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class GenerationBody(BaseModel):
    intent: str = Field(min_length=1)
    provider: str = "sd15"
    style_profile: Optional[str] = None
    checkpoint: Optional[str] = None
    steps: Optional[int] = Field(default=None, ge=1)
    cfg: Optional[float] = Field(default=None, gt=0.0)
    seed: Optional[int] = None
    policy: Optional[str] = None
    prompt_override: Optional[str] = None


class VariationsBody(GenerationBody):
    count: int = Field(default=1, ge=1, le=4)


class ReferenceSheetBody(BaseModel):
    view: str = "all"


# ── Legacy registry stubs (kept per /workflows listing contract) ─────────


class WorkflowDescriptor(BaseModel):
    id: str
    name: str
    description: str


class WorkflowListResponse(BaseModel):
    workflows: List[WorkflowDescriptor]


class DataConfigsResponse(BaseModel):
    configs: List[str]


class HealthResponse(BaseModel):
    status: str
    module: str


__all__ = [
    "ListResponse",
    "ItemsResponse",
    "CharacterRead",
    "DNARead",
    "IdentityRead",
    "AssetRead",
    "OutfitRead",
    "StyleProfileRead",
    "GenerationProfileRead",
    "JobRead",
    "EvaluationRead",
    "EvaluateResponseContract",
    "ExportBundleRead",
    "CharacterCreateBody",
    "CharacterPatchBody",
    "DnaUpsertBody",
    "IdentityVersionBody",
    "ReferenceCreateBody",
    "ApproveBody",
    "RejectBody",
    "OutfitCreateBody",
    "StyleProfileCreateBody",
    "GenerationProfileCreateBody",
    "GenerationBody",
    "VariationsBody",
    "ReferenceSheetBody",
    "WorkflowDescriptor",
    "WorkflowListResponse",
    "DataConfigsResponse",
    "HealthResponse",
]
