"""Skill Bridge routes — thin wrappers around skill_bridge_service.

Endpoints:
    POST /scan          — trigger local skill scan
    POST /import        — import a skill to workspace
    GET  /              — list workspace skills
    GET  /{skill_id}    — get skill detail
    DELETE /{skill_id}  — archive skill
    GET  /agent/{agent_id} — get skills for agent
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.services.skill_bridge_service import skill_bridge_service

router = APIRouter()


class SkillImportRequest(BaseModel):
    name: str
    source_path: str
    skill_content: str
    description: str = ""
    frontmatter: Optional[str] = None
    applicable_agents: Optional[str] = None
    dependencies: Optional[str] = None
    imported_by: Optional[str] = None


class SkillScanResponse(BaseModel):
    success: bool
    data: list
    message: str


class SkillResponse(BaseModel):
    success: bool
    data: dict | list
    message: str


def _skill_to_dict(skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "source_path": skill.source_path,
        "skill_content": skill.skill_content,
        "frontmatter": skill.frontmatter,
        "applicable_agents": skill.applicable_agents,
        "dependencies": skill.dependencies,
        "status": skill.status,
        "imported_by": skill.imported_by,
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
    }


@router.post("/scan", response_model=SkillScanResponse)
def scan_local_skills(session: Session = Depends(get_db_session)):
    discovered = skill_bridge_service.scan_local_skills(session)
    return SkillScanResponse(
        success=True,
        data=discovered,
        message=f"Discovered {len(discovered)} skills",
    )


@router.post("/import", response_model=SkillResponse)
def import_skill(req: SkillImportRequest, session: Session = Depends(get_db_session)):
    skill = skill_bridge_service.import_to_workspace(
        session=session,
        name=req.name,
        source_path=req.source_path,
        skill_content=req.skill_content,
        description=req.description,
        frontmatter=req.frontmatter,
        applicable_agents=req.applicable_agents,
        dependencies=req.dependencies,
        imported_by=req.imported_by,
    )
    return SkillResponse(
        success=True,
        data=_skill_to_dict(skill),
        message="Skill imported successfully",
    )


@router.get("/", response_model=SkillResponse)
def list_skills(
    status: Optional[str] = None,
    session: Session = Depends(get_db_session),
):
    skills = skill_bridge_service.list_workspace_skills(session, status=status)
    return SkillResponse(
        success=True,
        data=[_skill_to_dict(s) for s in skills],
        message=f"Found {len(skills)} skills",
    )


@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill(skill_id: str, session: Session = Depends(get_db_session)):
    skill = skill_bridge_service.get_skill(session, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillResponse(
        success=True,
        data=_skill_to_dict(skill),
        message="Skill retrieved",
    )


@router.delete("/{skill_id}", response_model=SkillResponse)
def archive_skill(skill_id: str, session: Session = Depends(get_db_session)):
    skill = skill_bridge_service.archive_skill(session, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillResponse(
        success=True,
        data=_skill_to_dict(skill),
        message="Skill archived",
    )


@router.get("/agent/{agent_id}", response_model=SkillResponse)
def get_skills_for_agent(agent_id: str, session: Session = Depends(get_db_session)):
    skills = skill_bridge_service.get_skills_for_agent(session, agent_id)
    return SkillResponse(
        success=True,
        data=[_skill_to_dict(s) for s in skills],
        message=f"Found {len(skills)} skills for agent",
    )
