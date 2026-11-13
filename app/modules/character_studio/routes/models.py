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
    negative_prompt: Optional[str] = None
    workflow_version: Optional[str] = None
    params_json: Optional[Dict[str, Any]] = None
    environment_json: Optional[Dict[str, Any]] = None
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

    Matches the shape returned by `common_lib...evaluate_asset`.
    Extra keys in the backing payload are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    asset_id: UUID
    character_id: str
    reference_asset_id: Optional[UUID] = None
    reference_source: Optional[str] = None
    similarity: float
    dinov2_similarity: Optional[float] = None
    verdict: str
    method: str
    evaluation_id: UUID
    output_url: Optional[str] = None


class ExportBundleRead(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    manifest: Dict[str, Any] = Field(default_factory=dict)
    files: List[str] = Field(default_factory=list)
    output_dir: str = ""
    export_kind: str = ""


# ── Request bodies ───────────────────────────────────────────────────────


class CharacterCreateBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'character_id': 'aria_canonical_01', 'name': 'Aria Canonical', 'description': 'Front-facing canonical reference for the Aria photoshoot'}]})
    character_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""


class CharacterPatchBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class DNACreateBody(BaseModel):
    """Character DNA create body."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    version: str = Field(default="1.0.0", min_length=1)
    identity_lock_method: Optional[str] = None
    identity_lock_source: Optional[str] = None
    similarity_threshold: Optional[float] = None
    quality_threshold: Optional[float] = None
    attribute_policies: Dict[str, str] = Field(default_factory=dict)


class DNAUpdateBody(BaseModel):
    """Character DNA update body (partial)."""

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    version: Optional[str] = None
    identity_lock_method: Optional[str] = None
    identity_lock_source: Optional[str] = None
    similarity_threshold: Optional[float] = None
    quality_threshold: Optional[float] = None
    attribute_policies: Optional[Dict[str, str]] = None


class DNAUpsertBody(BaseModel):
    """Character DNA upsert body (alias for DnaUpsertBody).

    The explicit identity-lock fields and every extra DNA attribute land in
    ``attribute_policies`` (the platform's identity-lock carrier — see
    ``selector.dna_identity_lock_source``). ``similarity_threshold`` is a
    first-class DNA column.
    """

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            'name': 'Aria Canonical 1.0.0',
            'version': '1.0.0',
            'identity_lock_method': 'post_swap',
            'identity_lock_source': '/resources/generated_content/aria/canonical/0001_front.png',
            'similarity_threshold': 0.75,
            'quality_threshold': 0.6,
            'attribute_policies': {'hair_color': 'locked', 'outfit': 'variable'},
        }]},
    )

    name: str = Field(min_length=1)
    version: str = Field(default="1.0.0", min_length=1)
    identity_lock_method: Optional[str] = None
    identity_lock_source: Optional[str] = None
    similarity_threshold: Optional[float] = None
    quality_threshold: Optional[float] = None
    attribute_policies: Dict[str, str] = Field(default_factory=dict)


# Backward compatibility alias
DnaUpsertBody = DNAUpsertBody


class IdentityVersionBody(BaseModel):
    version: str = Field(min_length=1)
    face_profile_id: Optional[UUID] = None
    body_profile_id: Optional[UUID] = None


class IdentityVersionCreateBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'version': '1.0.0', 'notes': 'initial', 'attribute_policies': {'hair_color': 'locked'}, 'reference_assets': []}]})
    version: str = Field(min_length=1)
    face_profile_id: Optional[UUID] = None
    body_profile_id: Optional[UUID] = None
    attribute_policies: Dict[str, str] = Field(default_factory=dict)
    reference_assets: Dict[str, str] = Field(default_factory=dict)


class IdentityVersionRead(BaseModel):
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


class ReferenceCreateBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'asset_id_str': 'aria_front_0001', 'category': 'face', 'subcategory': 'front', 'width': 1024, 'height': 1024, 'file_size': 3145728, 'format': 'png', 'quality_score': 0.95, 'file_path': '/resources/generated_content/aria_photoshoot/canonical_candidates/zimage/aria_canonical/0001_aria_canonical_front.png'}]})
    asset_id_str: str = Field(min_length=1)
    category: str = Field(min_length=1)
    subcategory: Optional[str] = None
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    file_size: int = Field(ge=0)
    format: str = "png"
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    # An asset registered from disk must carry its path; evaluation refuses
    # assets without one.
    file_path: Optional[str] = None


class ApproveBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'approved_by': 'reviewer@example.com'}]})
    approved_by: str = Field(min_length=1)


class RejectBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'reason': 'Face drift exceeds policy threshold'}]})
    reason: Optional[str] = None


class OutfitCreateBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'outfit_name': 'Casual Denim', 'category': 'casual', 'materials': ['denim', 'cotton'], 'colors': ['#3B5BB5'], 'tags': ['day_to_day']}]})
    outfit_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    materials: List[str] = Field(default_factory=list)
    colors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class StyleProfileCreateBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'profile_name': 'editorial_photoreal', 'rendering': 'photorealistic', 'consistency_policy': 'strict', 'is_default': False}]})
    profile_name: str = Field(min_length=1)
    rendering: str = Field(min_length=1)
    consistency_policy: str = "strict"
    is_default: bool = False


class GenerationProfileCreateBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'profile_name': 'sd15_portrait', 'model_provider': 'sd15', 'checkpoint': 'dreamshaper_8', 'default_steps': 30, 'default_cfg': 7.0}]})
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
    model_config = ConfigDict(json_schema_extra={"examples": [{'intent': 'fashion_editorial', 'provider': 'sd15', 'steps': 30, 'cfg': 7.0, 'seed': 42}]})
    intent: str = Field(min_length=1)
    provider: str = Field(default="sd15", pattern="^(sd15|sdxl|faceid_sd15)$")
    style_profile: Optional[str] = None
    checkpoint: Optional[str] = None
    steps: Optional[int] = Field(default=None, ge=1)
    cfg: Optional[float] = Field(default=None, gt=0.0)
    seed: Optional[int] = None
    policy: Optional[str] = None
    prompt_override: Optional[str] = None


class VariationsBody(GenerationBody):
    model_config = ConfigDict(json_schema_extra={"examples": [{'intent': 'fashion_editorial', 'provider': 'sd15', 'steps': 30, 'cfg': 7.0, 'seed': 1234, 'count': 4}]})
    count: int = Field(default=1, ge=1, le=4)


class ReferenceSheetBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'view': 'turnaround'}]})
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



# ---------------------------------------------------------------------------
# Accessory, Pose, Expression library wire models
# ---------------------------------------------------------------------------


class AccessoryCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'name': 'Silver Hoop Earrings', 'category': 'jewellery', 'materials': ['silver'], 'colors': ['#C0C0C0'], 'compatible_outfits': ['casual', 'formal']}]})
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    materials: List[str] = Field(default_factory=list)
    colors: List[str] = Field(default_factory=list)
    compatible_outfits: List[str] = Field(default_factory=list)
    asset_id: Optional[UUID] = None


class AccessoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    accessory_id: UUID
    character_id: str
    identity_version: str
    accessory_name: str
    category: str
    asset_id: Optional[UUID] = None
    materials: List[str] = Field(default_factory=list)
    colors: List[str] = Field(default_factory=list)
    compatible_outfits: List[str] = Field(default_factory=list)
    approval_status: str = "pending"
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PoseCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'pose_name': 'Standing Neutral', 'category': 'standing', 'openpose_json': {'keypoints': []}, 'keypoint_confidence': 0.92}]})
    pose_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    front_asset_id: Optional[UUID] = None
    side_asset_id: Optional[UUID] = None
    back_asset_id: Optional[UUID] = None
    openpose_json: Optional[Dict[str, Any]] = None
    keypoint_confidence: Optional[float] = None


class PoseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pose_id: UUID
    character_id: str
    identity_version: str
    pose_name: str
    category: str
    front_asset_id: Optional[UUID] = None
    side_asset_id: Optional[UUID] = None
    back_asset_id: Optional[UUID] = None
    openpose_json: Optional[Dict[str, Any]] = None
    keypoint_confidence: Optional[float] = None
    approval_status: str = "pending"
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ExpressionCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{'expression_name': 'Happy', 'category': 'happy', 'fau': {'AU6': 0.8, 'AU12': 0.9}}]})
    expression_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    asset_id: Optional[UUID] = None
    fau: Optional[Dict[str, float]] = None


class ExpressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    expression_id: UUID
    character_id: str
    identity_version: str
    expression_name: str
    category: str
    asset_id: Optional[UUID] = None
    fau: Optional[Dict[str, float]] = None
    approval_status: str = "pending"
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: UUID
    asset_id: UUID
    character_id: str
    from_status: Optional[str] = None
    to_status: str
    action: str
    actor: str
    reason: Optional[str] = None
    score: Optional[float] = None
    created_at: datetime


__all__ = [
    "ListResponse", "ItemsResponse",
    "CharacterRead", "DNARead", "IdentityRead", "AssetRead", "OutfitRead",
    "StyleProfileRead", "GenerationProfileRead", "JobRead", "EvaluationRead",
    "EvaluateResponseContract", "ExportBundleRead",
    "CharacterCreateBody", "CharacterPatchBody",
    "DNACreateBody", "DNAUpdateBody", "DNAUpsertBody", "DnaUpsertBody",
    "IdentityVersionBody", "IdentityVersionCreateBody", "IdentityVersionRead",
    "ReferenceCreateBody", "ApproveBody", "RejectBody",
    "OutfitCreateBody", "StyleProfileCreateBody", "GenerationProfileCreateBody",
    "GenerationBody", "VariationsBody", "ReferenceSheetBody",
    "WorkflowDescriptor", "WorkflowListResponse", "DataConfigsResponse", "HealthResponse",
    "AccessoryCreate", "AccessoryRead", "PoseCreate", "PoseRead",
    "ExpressionCreate", "ExpressionRead", "AuditEventRead",
]
