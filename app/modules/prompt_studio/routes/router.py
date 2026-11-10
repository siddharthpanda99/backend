"""Prompt Studio API Router — Thin Transport Layer"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.prompt_studio.schemas import (
    PromptVersionCreate,
    PromptVersionRead,
    PromptPartCreate,
    PromptPartRead,
    TeamSectionCreate,
    TeamSectionRead,
    SkillCreate,
    SkillRead,
    PromptComposeRequest,
    PromptComposeResponse,
    PromptPreviewRequest,
    PromptPreviewResponse,
    PromptValidateRequest,
    PromptValidateResponse,
    PromptDiffResponse,
)
from common_lib.modules.prompt_studio.service import get_prompt_studio_service
from common_lib.modules.prompt_studio.exceptions import (
    PromptStudioError,
    PromptVersionError,
    PromptVersionNotFoundError,
    PromptPartError,
    PromptPartNotFoundError,
    SkillError,
    SkillNotFoundError,
    TemplatePlaceholderError,
)

router = APIRouter(prefix="/prompt-studio", tags=["prompt-studio"])


# Version endpoints
@router.post("/versions", response_model=PromptVersionRead, status_code=201)
def create_version(payload: PromptVersionCreate) -> PromptVersionRead:
    """Create a new prompt version snapshot."""
    try:
        svc = get_prompt_studio_service()
        pv = svc.create_version(
            base_version=payload.base_version,
            parts=payload.parts,
            team_sections=payload.team_sections,
            skills=payload.skills,
            origin=payload.origin,
        )
        return PromptVersionRead.model_validate(pv)
    except PromptVersionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/versions", response_model=list[PromptVersionRead])
def list_versions(include_deprecated: bool = Query(False)) -> list[PromptVersionRead]:
    """List all prompt versions."""
    svc = get_prompt_studio_service()
    versions = svc.list_versions(include_deprecated=include_deprecated)
    return [PromptVersionRead.model_validate(v) for v in versions]


@router.get("/versions/latest", response_model=PromptVersionRead)
def get_latest_version() -> PromptVersionRead:
    """Get the latest (non-deprecated) prompt version."""
    svc = get_prompt_studio_service()
    pv = svc.get_latest_version()
    if not pv:
        raise HTTPException(status_code=404, detail="No versions found")
    return PromptVersionRead.model_validate(pv)


@router.get("/versions/{version}", response_model=PromptVersionRead)
def get_version(version: str) -> PromptVersionRead:
    """Get a prompt version by ID."""
    svc = get_prompt_studio_service()
    pv = svc.get_version(version)
    if not pv:
        raise HTTPException(status_code=404, detail="Version not found")
    return PromptVersionRead.model_validate(pv)


@router.post("/versions/{version}/deprecate", response_model=PromptVersionRead)
def deprecate_version(version: str, reason: str) -> PromptVersionRead:
    """Deprecate a prompt version."""
    try:
        svc = get_prompt_studio_service()
        pv = svc.deprecate_version(version, reason)
        return PromptVersionRead.model_validate(pv)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/versions/history", response_model=list[dict[str, Any]])
def get_history() -> list[dict[str, Any]]:
    """Get prompt version history."""
    svc = get_prompt_studio_service()
    return svc.get_history()


@router.get("/versions/diff", response_model=dict[str, Any])
def diff_versions(
    from_version: str = Query(...),
    to_version: str = Query(...),
) -> dict[str, Any]:
    """Diff two prompt versions."""
    try:
        svc = get_prompt_studio_service()
        return svc.diff_versions(from_version, to_version)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Prompt composition endpoints
@router.post("/compose", response_model=PromptComposeResponse)
async def compose_prompt(payload: PromptComposeRequest) -> PromptComposeResponse:
    """Compose a full prompt for a role."""
    try:
        svc = get_prompt_studio_service()
        result = await svc.compose_prompt(
            role=payload.role,
            base_version=payload.base_version,
            include_skills=payload.include_skills,
            variables=payload.variables,
            policy_data=payload.policy_data,
        )
        return PromptComposeResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/preview", response_model=PromptPreviewResponse)
async def preview_prompt(payload: PromptPreviewRequest) -> PromptPreviewResponse:
    """Preview a prompt version."""
    try:
        svc = get_prompt_studio_service()
        result = await svc.preview_prompt(
            version=payload.version,
            role=payload.role,
        )
        return PromptPreviewResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/validate", response_model=PromptValidateResponse)
def validate_prompt(payload: PromptValidateRequest) -> PromptValidateResponse:
    """Validate a prompt configuration."""
    try:
        svc = get_prompt_studio_service()
        result = svc.validate_prompt_config(
            parts=payload.parts,
            team_sections=payload.team_sections,
            skills=payload.skills,
        )
        return PromptValidateResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/diff", response_model=dict[str, Any])
def diff_versions(
    from_version: str = Query(...),
    to_version: str = Query(...),
) -> dict[str, Any]:
    """Diff two prompt versions."""
    try:
        svc = get_prompt_studio_service()
        return svc.diff_versions(payload.from_version, payload.to_version)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Prompt parts endpoints
@router.get("/parts", response_model=list[PromptPartRead])
def list_parts() -> list[PromptPartRead]:
    """List all prompt part overrides."""
    svc = get_prompt_studio_service()
    parts = svc.list_parts()
    return [PromptPartRead.model_validate(p) for p in parts]


@router.post("/parts", response_model=PromptPartRead, status_code=201)
def create_part(payload: PromptPartCreate) -> PromptPartRead:
    """Create or update a prompt part override."""
    try:
        svc = get_prompt_studio_service()
        part = svc.save_part(
            key=payload.key,
            team_override=payload.team_override,
            base_version=payload.base_version,
            is_removed=payload.is_removed,
        )
        return PromptPartRead.model_validate(part)
    except PromptPartError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/parts/{key}", response_model=PromptPartRead)
def get_part(key: str) -> PromptPartRead:
    """Get a prompt part override by key."""
    svc = get_prompt_studio_service()
    part = svc.get_part(key)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return PromptPartRead.model_validate(part)


@router.delete("/parts/{key}")
def delete_part(key: str) -> dict[str, bool]:
    """Delete a prompt part override (revert to built-in)."""
    svc = get_prompt_studio_service()
    deleted = svc.delete_part(key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Part not found")
    return {"deleted": True}


# Team section endpoints
@router.get("/sections", response_model=list[TeamSectionRead])
def list_sections() -> list[TeamSectionRead]:
    """List all team sections."""
    svc = get_prompt_studio_service()
    sections = svc.list_sections()
    return [TeamSectionRead.model_validate(s) for s in sections]


@router.post("/sections", response_model=TeamSectionRead, status_code=201)
def create_section(payload: TeamSectionCreate) -> TeamSectionRead:
    """Create or update a team section."""
    try:
        svc = get_prompt_studio_service()
        section = svc.save_section(
            key=payload.key,
            title=payload.title,
            content=payload.content,
            order=payload.order,
            is_active=payload.is_active,
        )
        return TeamSectionRead.model_validate(section)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sections/{key}", response_model=TeamSectionRead)
def get_section(key: str) -> TeamSectionRead:
    """Get a team section by key."""
    svc = get_prompt_studio_service()
    section = svc.get_section(key)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return TeamSectionRead.model_validate(section)


@router.delete("/sections/{key}")
def delete_section(key: str) -> dict[str, bool]:
    """Delete a team section."""
    svc = get_prompt_studio_service()
    deleted = svc.delete_section(key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Section not found")
    return {"deleted": True}


# Skill endpoints
@router.get("/skills", response_model=list[SkillRead])
def list_skills() -> list[SkillRead]:
    """List all skills."""
    svc = get_prompt_studio_service()
    skills = svc.list_skills()
    return [SkillRead.model_validate(s) for s in skills]


@router.post("/skills", response_model=SkillRead, status_code=201)
def create_skill(payload: SkillCreate) -> SkillRead:
    """Create or update a skill."""
    try:
        svc = get_prompt_studio_service()
        skill = svc.save_skill(
            name=payload.name,
            description=payload.description,
            content=payload.content,
            version=payload.version,
            is_built_in=payload.is_built_in,
            is_active=payload.is_active,
        )
        return SkillRead.model_validate(skill)
    except SkillError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/skills/{name}", response_model=SkillRead)
def get_skill(name: str) -> SkillRead:
    """Get a skill by name."""
    svc = get_prompt_studio_service()
    skill = svc.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillRead.model_validate(skill)


@router.delete("/skills/{name}")
def delete_skill(name: str) -> dict[str, bool]:
    """Delete a skill (only team skills, not built-in)."""
    try:
        svc = get_prompt_studio_service()
        deleted = svc.delete_skill(name)
        if not deleted:
            raise HTTPException(status_code=404, detail="Skill not found")
        return {"deleted": True}
    except SkillError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Prompt operations
@router.post("/compose", response_model=PromptComposeResponse)
async def compose_prompt(payload: PromptComposeRequest) -> PromptComposeResponse:
    """Compose a full prompt for a role."""
    try:
        svc = get_prompt_studio_service()
        result = await svc.compose_prompt(
            role=payload.role,
            base_version=payload.base_version,
            include_skills=payload.include_skills,
            variables=payload.variables,
            policy_data=payload.policy_data,
        )
        return PromptComposeResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/preview", response_model=PromptPreviewResponse)
async def preview_prompt(payload: PromptPreviewRequest) -> PromptPreviewResponse:
    """Preview a prompt version."""
    try:
        svc = get_prompt_studio_service()
        result = await svc.preview_prompt(
            version=payload.version,
            role=payload.role,
        )
        return PromptPreviewResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/validate", response_model=PromptValidateResponse)
def validate_prompt(payload: PromptValidateRequest) -> PromptValidateResponse:
    """Validate a prompt configuration."""
    try:
        svc = get_prompt_studio_service()
        result = svc.validate_prompt_config(
            parts=payload.parts,
            team_sections=payload.team_sections,
            skills=payload.skills,
        )
        return PromptValidateResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/diff", response_model=dict[str, Any])
def diff_versions(
    from_version: str = Query(...),
    to_version: str = Query(...),
) -> dict[str, Any]:
    """Diff two prompt versions."""
    try:
        svc = get_prompt_studio_service()
        return svc.diff_versions(from_version, to_version)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/history")
def get_history() -> list[dict[str, Any]]:
    """Get prompt version history."""
    svc = get_prompt_studio_service()
    return svc.get_history()
