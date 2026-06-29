"""Discovery routes — public feed, hotness ranking, sharing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session

router = APIRouter()


class ShareRequest(BaseModel):
    user_id: str
    title: str | None = None
    description: str | None = None
    tags: list | None = None


def _svc():
    from common_lib.modules.prompts_hero.services.discovery_service import (
        DiscoveryService,
    )

    return DiscoveryService()


@router.get("/feed")
def get_feed(
    offset: int = 0,
    limit: int = 20,
    model: str | None = None,
    sort: str = "hotness",
    session: Session = Depends(get_session),
):
    svc = _svc()
    results = svc.get_feed(
        session, offset=offset, limit=limit, model_filter=model, sort=sort
    )
    return {
        "success": True,
        "data": [
            {
                "generation": r["generation"].model_dump(),
                "hotness_score": r["hotness_score"],
            }
            for r in results
        ],
    }


@router.get("/feed/search")
def search_feed(q: str, limit: int = 20, session: Session = Depends(get_session)):
    svc = _svc()
    results = svc.search_public(session, q, limit=limit)
    return {"success": True, "data": results}


@router.post("/generations/{generation_id}/share")
def share_generation(
    generation_id: str, body: ShareRequest, session: Session = Depends(get_session)
):
    svc = _svc()
    try:
        share = svc.share_generation(
            session,
            generation_id=generation_id,
            user_id=body.user_id,
            title=body.title,
            description=body.description,
            tags=body.tags,
        )
    except Exception:
        raise HTTPException(400, "Generation not found or cannot be shared")
    return {"success": True, "data": share.model_dump()}


@router.get("/featured")
def list_featured(limit: int = 20, session: Session = Depends(get_session)):
    svc = _svc()
    shares = svc.list_featured(session, limit=limit)
    return {"success": True, "data": [s.model_dump() for s in shares]}
