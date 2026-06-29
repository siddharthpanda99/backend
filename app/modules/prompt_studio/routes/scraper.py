import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from common_lib.modules.prompt_studio.services.scraper_service import ScraperService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Prompt Studio"])


class ScrapeRequest(BaseModel):
    spider: str
    action: str
    params: Dict[str, Any] = {}


class ImportRequest(BaseModel):
    prompts: List[Dict[str, Any]]
    mode: str = "skip"
    dry_run: bool = False


@router.post("/scrape")
async def scrape(req: ScrapeRequest):
    try:
        result = ScraperService.scrape(req.spider, req.action, req.params)
        if not result.get("success"):
            logger.warning(
                "Scrape failed: spider=%s action=%s error=%s",
                req.spider,
                req.action,
                result.get("error"),
            )
            if req.action == "search":
                return {
                    "success": True,
                    "prompts": [],
                    "count": 0,
                    "error": result.get("error"),
                }
            raise HTTPException(
                status_code=400, detail=result.get("error", "Scrape failed")
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Scrape error: spider=%s action=%s error=%s",
            req.spider,
            req.action,
            str(e),
            exc_info=True,
        )
        if req.action == "search":
            return {"success": True, "prompts": [], "count": 0, "error": str(e)}
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/json")
async def import_json(req: ImportRequest):
    result = ScraperService.import_json(req.prompts, req.mode, req.dry_run)
    return result
