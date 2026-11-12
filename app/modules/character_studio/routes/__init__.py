"""Character Studio REST API.

Thin FastAPI routers delegating to the ``common_lib`` operations layer
(G1 — transport here, logic there). Mounted by ``app/core/routers.py`` at
``/api/v1/character-studio`` (registry prefix ``/character-studio``; this
router adds no prefix of its own).

Feature gating: the registry mounts the module behind
``CHARACTER_IDENTITY_ENABLED``; every handler additionally calls
``is_enabled("character_studio")`` (namespace flag, defaults ON) and answers
404 while disabled.

Errors from ``character_studio.exceptions.CharacterStudioError`` are mapped
to HTTP statuses: ``NOT_FOUND`` → 404, ``CONFLICT`` → 409, otherwise 400.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_lib.modules.common.feature_flags import is_enabled

from app.modules.character_studio import flags as _flags  # noqa: F401 — registers the flag
from app.modules.character_studio.routes.models import (
    ApproveBody,
    AssetRead,
    CharacterCreateBody,
    CharacterPatchBody,
    CharacterRead,
    DataConfigsResponse,
    DnaUpsertBody,
    DNARead,
    EvaluateResponseContract,
    EvaluationRead,
    ExportBundleRead,
    GenerationBody,
    GenerationProfileCreateBody,
    GenerationProfileRead,
    HealthResponse,
    IdentityRead,
    IdentityVersionBody,
    ItemsResponse,
    JobRead,
    ListResponse,
    OutfitCreateBody,
    OutfitRead,
    ReferenceCreateBody,
    ReferenceSheetBody,
    RejectBody,
    StyleProfileCreateBody,
    StyleProfileRead,
    VariationsBody,
    WorkflowDescriptor,
    WorkflowListResponse,
)

router = APIRouter(tags=["Character Studio"])


def _guard() -> None:
    """Per-handler check of the ``character_studio`` namespace flag."""
    if not is_enabled("character_studio"):
        raise HTTPException(status_code=404, detail="Character Studio is disabled")


def _http_error(exc: Exception) -> HTTPException:
    """Map a character_studio error onto HTTP.

    The ops layer raises ``CharacterStudioError`` (code: NOT_FOUND /
    CONFLICT / INVALID). We do NOT import it at module import time (the
    common_lib package is intentionally lazy here), so classification is
    duck-typed on ``code``/``message``:

    - NOT_FOUND → 404
    - CONFLICT  → 409
    - anything else carrying a code/message → 400
    - unknown exception → 500 with a plain message
    """
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None) or str(exc)
    if code == "NOT_FOUND":
        return HTTPException(status_code=404, detail=message)
    if code == "CONFLICT":
        return HTTPException(status_code=409, detail=message)
    if code == "INVALID":
        return HTTPException(status_code=400, detail=message)
    if isinstance(exc, HTTPException):
        return exc
    if code:
        return HTTPException(status_code=400, detail=message)
    return HTTPException(status_code=500, detail=f"character_studio error: {message}")


def _ops():
    """Lazily resolve the common_lib operations surface."""
    try:
        from common_lib.modules.image_processing.character_studio import (
            operations,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "character_studio operations layer unavailable: "
                f"{exc.__class__.__name__}: {exc}"
            ),
        ) from exc
    return operations


def _call(fn_name: str, *args: Any, **kwargs: Any) -> Any:
    ops = _ops()
    fn = getattr(ops, fn_name, None)
    if fn is None:
        raise HTTPException(
            status_code=503,
            detail=f"character_studio operations.{fn_name} not implemented yet",
        )
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        raise _http_error(exc) from exc


def _non_none(**kwargs: Any) -> Dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


# ═══════════════════════════════════════════════════════════════════════════
# Characters
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/characters", response_model=ListResponse[CharacterRead])
async def list_characters() -> ListResponse[CharacterRead]:
    """List all Character Studio characters."""
    _guard()
    items, total = _call("list_characters")
    return ListResponse[CharacterRead](items=list(items), total=total)


@router.post("/characters", response_model=CharacterRead, status_code=201)
async def create_character(body: CharacterCreateBody) -> CharacterRead:
    """Create a new character entry."""
    _guard()
    return _call(
        "create_character",
        character_id=body.character_id,
        name=body.name,
        description=body.description,
    )


@router.get("/characters/{character_id}", response_model=CharacterRead)
async def get_character(character_id: str) -> CharacterRead:
    """Get a character by ID."""
    _guard()
    return _call("get_character", character_id)


@router.patch("/characters/{character_id}", response_model=CharacterRead)
async def patch_character(character_id: str, body: CharacterPatchBody) -> CharacterRead:
    """Update a character (name/description/status)."""
    _guard()
    updates = _non_none(
        name=body.name, description=body.description, status=body.status
    )
    if not updates:
        return _call("get_character", character_id)
    return _call("update_character", character_id, **updates)


# ═══════════════════════════════════════════════════════════════════════════
# Character DNA
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/characters/{character_id}/dna", response_model=DNARead)
async def get_dna(character_id: str) -> DNARead:
    """Get the (latest) DNA record for a character."""
    _guard()
    return _call("get_dna", character_id)


@router.put("/characters/{character_id}/dna", response_model=DNARead)
async def upsert_dna(character_id: str, body: DnaUpsertBody) -> DNARead:
    """Create or replace the character DNA.

    Unknown top-level attributes are folded into ``attribute_policies`` along
    with the identity-lock scalars; ``similarity_threshold`` is persisted on
    the DNA record itself.
    """
    _guard()
    policies: Dict[str, str] = {}
    for key, value in (body.attribute_policies or {}).items():
        if value is not None:
            policies[str(key)] = str(value)
    extras = body.model_extra or {}
    for key, value in extras.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            policies[str(key)] = ",".join(str(item) for item in value)
        else:
            policies[str(key)] = str(value)

    kwargs: Dict[str, Any] = {
        "name": body.name,
        "version": body.version,
    }
    if body.identity_lock_method:
        kwargs["identity_lock_method"] = body.identity_lock_method
    if body.identity_lock_source:
        kwargs["identity_lock_source"] = body.identity_lock_source
    if body.similarity_threshold is not None:
        kwargs["similarity_threshold"] = body.similarity_threshold
    if body.quality_threshold is not None:
        kwargs["quality_threshold"] = body.quality_threshold
    if policies:
        kwargs["attribute_policies"] = policies
    return _call("upsert_dna", character_id, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# Identity versions
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/characters/{character_id}/versions", response_model=IdentityRead)
async def create_identity_version(
    character_id: str, body: IdentityVersionBody
) -> IdentityRead:
    """Create an identity version for a character."""
    _guard()
    return _call(
        "create_identity_version",
        character_id,
        version=body.version,
        face_profile_id=body.face_profile_id,
        body_profile_id=body.body_profile_id,
    )


# ═══════════════════════════════════════════════════════════════════════════
# References
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/characters/{character_id}/references",
    response_model=ListResponse[AssetRead],
)
async def list_references(
    character_id: str,
    category: Optional[str] = None,
    approved_only: bool = True,
) -> ListResponse[AssetRead]:
    """List reference assets for a character."""
    _guard()
    items, total = _call(
        "list_references",
        character_id,
        category=category,
        approved_only=approved_only,
    )
    return ListResponse[AssetRead](items=list(items), total=total)


@router.post("/characters/{character_id}/references", response_model=AssetRead)
async def add_reference(character_id: str, body: ReferenceCreateBody) -> AssetRead:
    """Register a reference asset (typically one produced by generation)."""
    _guard()
    return _call(
        "add_reference",
        character_id,
        asset_id_str=body.asset_id_str,
        category=body.category,
        subcategory=body.subcategory,
        width=body.width,
        height=body.height,
        file_size=body.file_size,
        format=body.format,
        quality_score=body.quality_score,
    )


@router.post("/references/{asset_id}/approve", response_model=AssetRead)
async def approve_reference(asset_id: UUID, body: ApproveBody) -> AssetRead:
    """Approve a reference asset."""
    _guard()
    return _call("approve_reference", asset_id, approved_by=body.approved_by)


@router.post("/references/{asset_id}/archive", response_model=AssetRead)
async def archive_reference(asset_id: UUID) -> AssetRead:
    """Archive a reference asset."""
    _guard()
    return _call("archive_reference", asset_id)


# ═══════════════════════════════════════════════════════════════════════════
# Outfits
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/characters/{character_id}/outfits",
    response_model=ItemsResponse[OutfitRead],
)
async def list_outfits(character_id: str) -> ItemsResponse[OutfitRead]:
    """List outfits for a character."""
    _guard()
    items = list(_call("list_outfits", character_id))
    return ItemsResponse[OutfitRead](items=items)


@router.post("/characters/{character_id}/outfits", response_model=OutfitRead)
async def add_outfit(character_id: str, body: OutfitCreateBody) -> OutfitRead:
    """Add an outfit for a character."""
    _guard()
    return _call(
        "add_outfit",
        character_id,
        outfit_name=body.outfit_name,
        category=body.category,
        materials=body.materials,
        colors=body.colors,
        tags=body.tags,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Style profiles
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/characters/{character_id}/style-profiles",
    response_model=ItemsResponse[StyleProfileRead],
)
async def list_style_profiles(
    character_id: str,
) -> ItemsResponse[StyleProfileRead]:
    """List style profiles for a character."""
    _guard()
    items = list(_call("list_style_profiles", character_id))
    return ItemsResponse[StyleProfileRead](items=items)


@router.post(
    "/characters/{character_id}/style-profiles",
    response_model=StyleProfileRead,
)
async def create_style_profile(
    character_id: str, body: StyleProfileCreateBody
) -> StyleProfileRead:
    """Create a style profile for a character."""
    _guard()
    return _call(
        "create_style_profile",
        character_id,
        profile_name=body.profile_name,
        rendering=body.rendering,
        consistency_policy=body.consistency_policy,
        is_default=body.is_default,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Generation profiles
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/characters/{character_id}/generation-profiles",
    response_model=ItemsResponse[GenerationProfileRead],
)
async def list_generation_profiles(
    character_id: str,
) -> ItemsResponse[GenerationProfileRead]:
    """List generation profiles for a character."""
    _guard()
    items = list(_call("list_generation_profiles", character_id))
    return ItemsResponse[GenerationProfileRead](items=items)


@router.post(
    "/characters/{character_id}/generation-profiles",
    response_model=GenerationProfileRead,
)
async def create_generation_profile(
    character_id: str, body: GenerationProfileCreateBody
) -> GenerationProfileRead:
    """Create a generation profile for a character."""
    _guard()
    return _call(
        "create_generation_profile",
        character_id,
        profile_name=body.profile_name,
        model_provider=body.model_provider,
        checkpoint=body.checkpoint,
        face_identity_conditioning=body.face_identity_conditioning,
        default_steps=body.default_steps,
        default_cfg=body.default_cfg,
        evaluation_policy=body.evaluation_policy,
        similarity_threshold=body.similarity_threshold,
        quality_threshold=body.quality_threshold,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Generation jobs
# ═══════════════════════════════════════════════════════════════════════════


def _job_kwargs(
    body: GenerationBody, count: int = 1, intent: Optional[str] = None
) -> Dict[str, Any]:
    # operations.create_generation_job requires ALL request kwargs (they carry
    # no defaults on purpose) — pass them explicitly, None included.
    return {
        "intent": intent or body.intent,
        "provider": body.provider,
        "style_profile": body.style_profile,
        "checkpoint": body.checkpoint,
        "engine": None,
        "steps": body.steps,
        "cfg": body.cfg,
        "seed": body.seed,
        "policy": body.policy,
        "prompt_override": body.prompt_override,
        "count": count,
    }


@router.post(
    "/characters/{character_id}/generate",
    response_model=JobRead,
    status_code=202,
)
async def generate(character_id: str, body: GenerationBody) -> JobRead:
    """Queue a generation job for a character."""
    _guard()
    return _call("create_generation_job", character_id, **_job_kwargs(body))


@router.post(
    "/characters/{character_id}/edit",
    response_model=JobRead,
    status_code=202,
)
async def edit(character_id: str, body: GenerationBody) -> JobRead:
    """Queue an edit job for a character."""
    _guard()
    return _call("create_generation_job", character_id, **_job_kwargs(body))


@router.post(
    "/characters/{character_id}/variations",
    response_model=JobRead,
    status_code=202,
)
async def variations(character_id: str, body: VariationsBody) -> JobRead:
    """Queue a variations job for a character (1–4 images)."""
    _guard()
    return _call(
        "create_generation_job",
        character_id,
        **_job_kwargs(body, count=body.count),
    )


@router.post(
    "/characters/{character_id}/reference-sheets",
    response_model=JobRead,
    status_code=202,
)
async def reference_sheets(character_id: str, body: ReferenceSheetBody) -> JobRead:
    """Queue a reference-sheet job for a character."""
    _guard()
    intent = "reference_sheet" if body.view == "all" else f"reference_sheet:{body.view}"
    return _call(
        "create_generation_job",
        character_id,
        **_job_kwargs(GenerationBody(intent=intent), count=1, intent=intent),
    )


@router.get("/generation-jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: UUID) -> JobRead:
    """Get a generation job."""
    _guard()
    return _call("get_job", job_id)


@router.post("/generation-jobs/{job_id}/cancel", response_model=JobRead)
async def cancel_job(job_id: UUID) -> JobRead:
    """Cancel a queued/running generation job."""
    _guard()
    return _call("cancel_job", job_id)


# ═══════════════════════════════════════════════════════════════════════════
# Evaluation
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/assets/{asset_id}/evaluate",
    response_model=EvaluateResponseContract,
)
async def evaluate_asset(asset_id: UUID) -> EvaluateResponseContract:
    """Evaluate an asset against the character identity lock."""
    _guard()
    result = _call("evaluate_asset", asset_id)
    return EvaluateResponseContract.model_validate(result)


@router.get(
    "/assets/{asset_id}/evaluations",
    response_model=ItemsResponse[EvaluationRead],
)
async def list_evaluations(asset_id: UUID) -> ItemsResponse[EvaluationRead]:
    """List identity-consistency evaluations for an asset."""
    _guard()
    items = list(_call("list_evaluations", asset_id))
    return ItemsResponse[EvaluationRead](items=items)


@router.post("/assets/{asset_id}/approve", response_model=AssetRead)
async def approve_asset(asset_id: UUID, body: ApproveBody) -> AssetRead:
    """Approve an asset."""
    _guard()
    return _call("approve_asset", asset_id, approved_by=body.approved_by)


@router.post("/assets/{asset_id}/reject", response_model=AssetRead)
async def reject_asset(asset_id: UUID, body: RejectBody) -> AssetRead:
    """Reject an asset."""
    _guard()
    return _call("reject_asset", asset_id, reason=body.reason)


# ═══════════════════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/characters/{character_id}/export/rpg",
    response_model=ExportBundleRead,
)
async def export_rpg(character_id: str) -> ExportBundleRead:
    """Export a character bundle for RPG use."""
    _guard()
    return ExportBundleRead.model_validate(_call("export_rpg", character_id))


@router.post(
    "/characters/{character_id}/export/social",
    response_model=ExportBundleRead,
)
async def export_social(character_id: str) -> ExportBundleRead:
    """Export a character bundle for social use."""
    _guard()
    return ExportBundleRead.model_validate(_call("export_social", character_id))


@router.post(
    "/characters/{character_id}/export/comic",
    response_model=ExportBundleRead,
)
async def export_comic(character_id: str) -> ExportBundleRead:
    """Export a character bundle for comic use."""
    _guard()
    return ExportBundleRead.model_validate(_call("export_comic", character_id))


# ═══════════════════════════════════════════════════════════════════════════
# Legacy registry stubs (kept)
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_character_studio_workflows() -> WorkflowListResponse:
    """List all Character Studio workflows."""
    _guard()
    workflows = [
        WorkflowDescriptor(
            id="character_studio_character_creation",
            name="Character Creation",
            description="Create initial character candidates from text prompts",
        ),
        WorkflowDescriptor(
            id="character_studio_character_generation",
            name="Character Generation",
            description="Generate new images of an established character with identity preservation",
        ),
        WorkflowDescriptor(
            id="character_studio_character_edit",
            name="Character Edit",
            description="Edit existing character images (outfit, background, etc.)",
        ),
        WorkflowDescriptor(
            id="character_studio_reference_sheet",
            name="Reference Sheet",
            description="Generate reference sheets: turnarounds, expressions, details",
        ),
        WorkflowDescriptor(
            id="character_studio_consistency_evaluation",
            name="Consistency Evaluation",
            description="Evaluate visual consistency using InsightFace comparison",
        ),
        WorkflowDescriptor(
            id="character_studio_style_profile_generation",
            name="Style Profile Generation",
            description="Generate style profiles from reference images",
        ),
        WorkflowDescriptor(
            id="character_studio_upscale_enhance",
            name="Upscale & Enhance",
            description="Upscale and enhance character images for final output",
        ),
    ]
    return WorkflowListResponse(workflows=workflows)


@router.get("/data-configs", response_model=DataConfigsResponse)
async def list_character_studio_data_configs() -> DataConfigsResponse:
    """List all Character Studio data configurations."""
    _guard()
    return DataConfigsResponse(
        configs=[
            "character_creation",
            "character_generation",
            "character_edit",
            "reference_sheet",
            "consistency_evaluation",
            "style_profile_generation",
            "upscale_enhance",
        ],
    )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check for Character Studio."""
    _guard()
    return HealthResponse(status="healthy", module="character_studio")
