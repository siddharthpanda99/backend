"""Knowledge Hub — Scraper Management Routes.

Endpoints:
    GET    /knowledge-hub/scrapers                  — List scrapers
    POST   /knowledge-hub/scrapers                  — Create scraper
    GET    /knowledge-hub/scrapers/{id}             — Get scraper
    PUT    /knowledge-hub/scrapers/{id}             — Update scraper
    DELETE /knowledge-hub/scrapers/{id}             — Delete scraper
    POST   /knowledge-hub/scrapers/{id}/run         — Execute scraper
    GET    /knowledge-hub/scrapers/{id}/preview     — Preview (single page, no persist)
    POST   /knowledge-hub/scrapers/{id}/pause       — Pause scraper
    POST   /knowledge-hub/scrapers/{id}/resume      — Resume scraper
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_engine.knowledge_hub.models import ScraperConfigRecord
from common_lib.modules.knowledge_engine.knowledge_hub.services.scraper_service import (
    ScraperService,
    ScraperError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-hub", tags=["Knowledge Hub — Scrapers"])


# ── Pydantic Schemas ───────────────────────────────────────────────


class ScraperCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="User-given name for the scraper")
    url: str = Field(..., description="Starting URL or sitemap URL")
    scraper_type: str = Field("url", description="url, sitemap, or crawl")
    project_id: Optional[str] = None
    schedule: Optional[str] = Field(None, description="Cron expression")
    respect_robots_txt: bool = True
    max_pages: int = Field(100, ge=1, le=10000)
    rate_limit_ms: int = Field(1000, ge=100, le=60000)
    config: Dict[str, Any] = Field(default_factory=dict)


class ScraperUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    scraper_type: Optional[str] = None
    schedule: Optional[str] = None
    respect_robots_txt: Optional[bool] = None
    max_pages: Optional[int] = None
    rate_limit_ms: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/scrapers")
def list_scrapers(
    status: Optional[str] = Query(None, description="Filter by status: active, paused, archived"),
    scraper_type: Optional[str] = Query(None, description="Filter by type: url, sitemap, crawl"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List scraper configurations."""
    scrapers = ScraperService.list_scrapers(
        session, status=status, scraper_type=scraper_type, project_id=project_id
    )
    return {
        "success": True,
        "data": [_scraper_to_dict(s) for s in scrapers],
        "total": len(scrapers),
    }


@router.get("/scrapers/{scraper_id}")
def get_scraper(
    scraper_id: str = Path(..., description="Scraper ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a scraper configuration by ID."""
    record = ScraperService.get_scraper(session, scraper_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Scraper '{scraper_id}' not found")
    return {"success": True, "data": _scraper_to_dict(record)}


@router.post("/scrapers", status_code=201)
def create_scraper(
    request: ScraperCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new scraper configuration."""
    if request.scraper_type not in ("url", "sitemap", "crawl"):
        raise HTTPException(status_code=400, detail="scraper_type must be 'url', 'sitemap', or 'crawl'")
    record = ScraperService.create_scraper(session, request.model_dump())
    return {
        "success": True,
        "data": _scraper_to_dict(record),
        "message": f"Scraper '{record.name}' created",
    }


@router.put("/scrapers/{scraper_id}")
def update_scraper(
    request: ScraperUpdate,
    scraper_id: str = Path(..., description="Scraper ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update an existing scraper configuration."""
    record = ScraperService.update_scraper(session, scraper_id, request.model_dump(exclude_none=True))
    if not record:
        raise HTTPException(status_code=404, detail=f"Scraper '{scraper_id}' not found")
    return {"success": True, "data": _scraper_to_dict(record)}


@router.delete("/scrapers/{scraper_id}")
def delete_scraper(
    scraper_id: str = Path(..., description="Scraper ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a scraper configuration."""
    deleted = ScraperService.delete_scraper(session, scraper_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Scraper '{scraper_id}' not found")
    return {"success": True, "message": f"Scraper '{scraper_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Control
# ═══════════════════════════════════════════════════════════════════


@router.post("/scrapers/{scraper_id}/run")
def run_scraper(
    scraper_id: str = Path(..., description="Scraper ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Execute a scraper and persist results.

    - url: Single page fetch with robots.txt respect
    - sitemap: Discover URLs from sitemap.xml, fetch each
    - crawl: Recursive crawl with max_pages and rate limiting
    """
    try:
        result = ScraperService.run_scraper(session, scraper_id)
        if not result.get("success") and "not found" in str(result.get("message", "")):
            raise HTTPException(status_code=404, detail=result["message"])
        return {"success": True, "data": result, "message": f"Scraper run completed: {result.get('pages_fetched', 0)} pages"}
    except ScraperError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrapers/{scraper_id}/preview")
def preview_scraper(
    scraper_id: str = Path(..., description="Scraper ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Preview a scraper run (single page, no persistence).

    Fetches the configured URL, extracts text content, and shows
    a preview without saving results. Useful for testing before
    a full run.
    """
    result = ScraperService.preview_scraper(session, scraper_id)
    if not result.get("success"):
        if "not found" in str(result.get("message", "")):
            raise HTTPException(status_code=404, detail=result["message"])
        raise HTTPException(status_code=502, detail=result.get("message", "Preview failed"))
    return {"success": True, "data": result}


@router.post("/scrapers/{scraper_id}/pause")
def pause_scraper(
    scraper_id: str = Path(..., description="Scraper ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Pause a scraper. Paused scrapers won't run scheduled jobs."""
    record = ScraperService.pause_scraper(session, scraper_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Scraper '{scraper_id}' not found")
    return {
        "success": True,
        "data": _scraper_to_dict(record),
        "message": f"Scraper '{record.name}' paused",
    }


@router.post("/scrapers/{scraper_id}/resume")
def resume_scraper(
    scraper_id: str = Path(..., description="Scraper ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Resume a paused scraper."""
    record = ScraperService.resume_scraper(session, scraper_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Scraper '{scraper_id}' not found")
    return {
        "success": True,
        "data": _scraper_to_dict(record),
        "message": f"Scraper '{record.name}' resumed",
    }


# ── Serialization helper ──────────────────────────────────────


def _scraper_to_dict(record: ScraperConfigRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "url": record.url,
        "scraper_type": record.scraper_type,
        "project_id": record.project_id,
        "schedule": record.schedule,
        "respect_robots_txt": record.respect_robots_txt,
        "max_pages": record.max_pages,
        "rate_limit_ms": record.rate_limit_ms,
        "config": record.config,
        "status": record.status,
        "last_run_at": record.last_run_at.isoformat() if record.last_run_at else None,
        "last_run_result": record.last_run_result,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
