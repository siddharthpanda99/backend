import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.modules.common.types.index import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class PromptImportRequest(BaseModel):
    url: str
    model: Optional[str] = "sd15"


class PromptSaveRequest(BaseModel):
    id: Optional[str] = None
    name: str
    system_prompt: str
    description: Optional[str] = ""
    category: Optional[str] = "community"
    logical_category: Optional[str] = "prompts"
    tags: Optional[List[str]] = []
    config: Optional[Dict[str, Any]] = {}
    metadata_json: Optional[Dict[str, Any]] = {}


@router.post("/import", response_model=APIResponse[Dict[str, Any]])
async def import_prompt_from_url(request: PromptImportRequest):
    """Scrape a PromptHero URL and return adapted prompt data ready to save."""
    try:
        from common_lib.plugins.web_scraper.spiders.prompthero import PromptHeroSpider
        from common_lib.plugins.web_scraper.core.engine import ScraperCore

        fetcher = ScraperCore().get_fetcher()
        spider = PromptHeroSpider(fetcher)
        details = spider.fetch_prompt_details(request.url)
        if not details.get("success"):
            raise HTTPException(
                status_code=400, detail=details.get("error", "Failed to fetch prompt")
            )

        record = spider.adapt_to_prompt_record(details)
        return APIResponse(
            data=record,
            message=f"Imported '{details.get('title', '')}' — preview before saving",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prompt import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save", response_model=APIResponse[Dict[str, Any]])
async def save_imported_prompt(request: PromptSaveRequest):
    """Save an imported prompt to the database as a PromptRecord."""
    try:
        from app.core.common_lib_integration import common_memory, sync_entity_to_fs

        prompt_id = request.id or f"prompthero_{uuid.uuid4().hex[:8]}"
        if common_memory.get_prompt_definition(prompt_id):
            prompt_id = f"{prompt_id}_{uuid.uuid4().hex[:4]}"

        success = common_memory.save_prompt_definition(
            entity_id=prompt_id,
            system_prompt=request.system_prompt,
            config={
                "name": request.name,
                "description": request.description,
                "category": request.category,
                "logical_category": request.logical_category,
                "tags": request.tags,
                "config": request.config,
                "metadata_json": request.metadata_json,
            },
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save prompt to DB")

        sync_entity_to_fs("prompt", prompt_id)
        saved = common_memory.get_prompt_definition(prompt_id)
        return APIResponse(
            data=saved, message=f"Prompt '{request.name}' saved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-and-save", response_model=APIResponse[Dict[str, Any]])
async def import_and_save_prompt(request: PromptImportRequest):
    """Scrape a PromptHero URL and immediately save to the database."""
    try:
        from common_lib.plugins.web_scraper.spiders.prompthero import PromptHeroSpider
        from common_lib.plugins.web_scraper.core.engine import ScraperCore
        from app.core.common_lib_integration import common_memory, sync_entity_to_fs

        fetcher = ScraperCore().get_fetcher()
        spider = PromptHeroSpider(fetcher)
        details = spider.fetch_prompt_details(request.url)
        if not details.get("success"):
            raise HTTPException(
                status_code=400, detail=details.get("error", "Failed to fetch prompt")
            )

        record = spider.adapt_to_prompt_record(details)
        prompt_id = record["id"]
        if common_memory.get_prompt_definition(prompt_id):
            prompt_id = f"{prompt_id}_{uuid.uuid4().hex[:4]}"

        success = common_memory.save_prompt_definition(
            entity_id=prompt_id,
            system_prompt=record["system_prompt"],
            config={
                "name": record["name"],
                "description": record.get("description", ""),
                "category": record.get("category", "community"),
                "logical_category": record.get("logical_category", "prompts"),
                "tags": record.get("tags", []),
                "config": record.get("config", {}),
                "metadata_json": record.get("metadata_json", {}),
            },
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save prompt to DB")

        sync_entity_to_fs("prompt", prompt_id)
        saved = common_memory.get_prompt_definition(prompt_id)
        return APIResponse(
            data=saved, message=f"Prompt '{record['name']}' imported and saved"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import and save prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=APIResponse[List[Dict[str, Any]]])
async def list_imported_prompts():
    """List all prompts in the database."""
    try:
        from app.core.common_lib_integration import common_memory

        prompts = common_memory.list_prompt_definitions()
        return APIResponse(data=prompts, message=f"Found {len(prompts)} prompts")
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/import/batch", response_model=APIResponse[List[Dict[str, Any]]])
async def batch_import_prompts(
    model: str = Query("sd15", description="Model slug"),
    limit: int = Query(12, description="Number of prompts to fetch"),
):
    """Batch-fetch popular prompts from PromptHero and return adapted records."""
    try:
        from common_lib.plugins.web_scraper.spiders.prompthero import PromptHeroSpider
        from common_lib.plugins.web_scraper.core.engine import ScraperCore

        fetcher = ScraperCore().get_fetcher()
        spider = PromptHeroSpider(fetcher)
        result = spider.run(model=model, sort="popular", limit=limit)
        if not result.get("success"):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Failed to fetch prompts")
            )

        records = []
        for prompt_data in result.get("prompts", []):
            try:
                details = spider.fetch_prompt_details(prompt_data["url"])
                if details.get("success"):
                    record = spider.adapt_to_prompt_record(details)
                    records.append(record)
                else:
                    records.append(spider.adapt_to_prompt_record(prompt_data))
            except Exception as e:
                logger.warning(f"Skipping prompt {prompt_data.get('url')}: {e}")
                continue

        return APIResponse(
            data=records, message=f"Fetched {len(records)} prompts from PromptHero"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source/{source}", response_model=APIResponse[List[Dict[str, Any]]])
async def list_prompts_by_source(source: str):
    """List prompts filtered by source (e.g., 'prompthero')."""
    try:
        from app.core.common_lib_integration import common_memory

        prompts = common_memory.list_prompt_definitions()
        filtered = [
            p
            for p in prompts
            if p.get("config", {}).get("metadata_json", {}).get("source") == source
            or source in p.get("config", {}).get("tags", [])
        ]
        return APIResponse(
            data=filtered,
            message=f"Found {len(filtered)} prompts from source '{source}'",
        )
    except Exception as e:
        logger.error(f"Failed to filter prompts by source: {e}")
        raise HTTPException(status_code=500, detail=str(e))
