"""Skills Gateway API Routes — REST endpoints for npx skills CLI."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.skills_gateway.service import (
    get_skills_gateway_service,
    SkillsGatewayError,
    SkillNotFoundError,
    SkillInstallError,
    SkillExecutionError,
    SkillTimeoutError,
)
from common_lib.modules.skills_gateway.schemas import (
    SkillSearchResponse,
    SkillInstallRequest,
    SkillInstallResponse,
    SkillExecuteRequest,
    SkillExecuteResponse,
    SkillListResponse,
    SkillUninstallResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["Skills Gateway"])


def _get_service():
    """Get the skills gateway service."""
    return get_skills_gateway_service()


@router.get("/search", response_model=SkillSearchResponse)
async def search_skills(
    q: str = Query(..., description="Search query", min_length=1),
    owner: Optional[str] = Query(None, description="Filter by GitHub owner"),
) -> SkillSearchResponse:
    """Search skills.sh registry for skills matching query.

    Wraps: `npx skills find <query> [--owner <owner>]`
    """
    service = _get_service()
    try:
        return service.search(q, owner)
    except SkillsGatewayError as exc:
        raise HTTPException(status_code=400, detail=exc.message)


@router.post("/install", response_model=SkillInstallResponse)
async def install_skill(request: SkillInstallRequest) -> SkillInstallResponse:
    """Install a skill to the local project (node_modules/).

    Wraps: `npx skills add <skill> [-g]`
    """
    service = _get_service()
    try:
        return service.install(request)
    except SkillsGatewayError as exc:
        raise HTTPException(status_code=400, detail=exc.message)


@router.post("/execute", response_model=SkillExecuteResponse)
async def execute_skill(request: SkillExecuteRequest) -> SkillExecuteResponse:
    """Execute a skill with JSON input.

    Wraps: `npx skills run <skill>` with JSON input via stdin.
    Auto-installs if missing (install_if_missing=true).
    """
    service = _get_service()
    try:
        return service.execute(request)
    except SkillTimeoutError as exc:
        raise HTTPException(status_code=408, detail=exc.message)
    except SkillsGatewayError as exc:
        raise HTTPException(status_code=400, detail=exc.message)


@router.get("/list", response_model=SkillListResponse)
async def list_skills() -> SkillListResponse:
    """List locally installed skills.

    Wraps: `npx skills list`
    """
    service = _get_service()
    try:
        return service.list_installed()
    except SkillsGatewayError as exc:
        raise HTTPException(status_code=400, detail=exc.message)


@router.delete("/{skill}", response_model=SkillUninstallResponse)
async def uninstall_skill(skill: str) -> SkillUninstallResponse:
    """Uninstall a skill from the local project.

    Wraps: `npx skills remove <skill>`
    """
    service = _get_service()
    try:
        return service.uninstall(skill)
    except SkillsGatewayError as exc:
        raise HTTPException(status_code=400, detail=exc.message)


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    service = _get_service()
    try:
        # Quick check - try to run npx skills --version
        import subprocess

        result = subprocess.run(
            ["npx", "skills", "--version"],
            cwd=service._project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "status": "healthy" if result.returncode == 0 else "degraded",
            "skills_cli_version": result.stdout.strip()
            if result.returncode == 0
            else None,
            "error": result.stderr.strip() if result.returncode != 0 else None,
            "feature_enabled": True,
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
            "feature_enabled": True,
        }
