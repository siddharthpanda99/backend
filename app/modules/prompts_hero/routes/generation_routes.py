"""Generation routes — track and manage prompt generations with full parameters."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session

router = APIRouter()


class GenerationCreateRequest(BaseModel):
    user_id: str
    prompt_text: str
    model_id: str
    negative_prompt: str | None = None
    prompt_id: str | None = None
    tool_id: str | None = None
    model_name: str | None = None
    seed: int = -1
    sampler: str | None = None
    scheduler: str | None = None
    cfg_scale: float = 7.0
    steps: int = 25
    clip_skip: int = 1
    width: int = 512
    height: int = 512
    aspect_ratio: str | None = None
    image_url: str | None = None
    generation_time_ms: int | None = None
    credits_spent: int = 1
    is_public: bool = True
    tags: list | None = None


class GenerationVisibilityRequest(BaseModel):
    is_public: bool


def _svc():
    from common_lib.modules.prompt_studio.prompts_hero.services.generation_service import (
        GenerationService,
    )

    return GenerationService()


@router.post("/generations")
def create_generation(
    body: GenerationCreateRequest, session: Session = Depends(get_session)
):
    svc = _svc()
    gen = svc.create(session, **body.model_dump())
    return {"success": True, "data": gen.model_dump()}


@router.get("/generations/{generation_id}")
def get_generation(generation_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    gen = svc.get(session, generation_id)
    if not gen:
        raise HTTPException(404, "Generation not found")
    return {"success": True, "data": gen.model_dump()}


@router.get("/generations/user/{user_id}")
def list_user_generations(
    user_id: str,
    offset: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session),
):
    svc = _svc()
    gens = svc.list_user(session, user_id, offset=offset, limit=limit)
    return {"success": True, "data": [g.model_dump() for g in gens]}


@router.delete("/generations/{generation_id}")
def delete_generation(generation_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    if not svc.delete(session, generation_id):
        raise HTTPException(404, "Generation not found")
    return {"success": True}


@router.put("/generations/{generation_id}/visibility")
def update_visibility(
    generation_id: str,
    body: GenerationVisibilityRequest,
    session: Session = Depends(get_session),
):
    svc = _svc()
    gen = svc.update_visibility(session, generation_id, is_public=body.is_public)
    if not gen:
        raise HTTPException(404, "Generation not found")
    return {"success": True, "data": gen.model_dump()}


@router.get("/generations/search")
def search_generations(
    q: str, limit: int = 20, session: Session = Depends(get_session)
):
    svc = _svc()
    results = svc.search(session, q, limit=limit)
    return {"success": True, "data": [g.model_dump() for g in results]}
