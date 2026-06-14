"""Prompts API Routes — thin routes delegating to common_lib services."""

import logging
import uuid
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


def _import_prompt_from_url(url: str) -> dict:
    """Import a prompt from PromptHero and return adapted data."""
    from common_lib.plugins.web_scraper.spiders.prompthero import PromptHeroSpider
    from common_lib.plugins.web_scraper.core.engine import ScraperCore

    fetcher = ScraperCore().get_fetcher()
    spider = PromptHeroSpider(fetcher)
    details = spider.fetch_prompt_details(url)
    if not details.get("success"):
        raise HTTPException(
            status_code=400, detail=details.get("error", "Failed to fetch prompt")
        )
    return spider.adapt_to_prompt_record(details)


def _save_imported_prompt(prompt_id: str, request: PromptSaveRequest) -> dict:
    """Save a prompt via common_memory and sync to filesystem."""
    from app.core.common_lib_integration import common_memory, sync_entity_to_fs

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
    return saved


@router.post("/import", response_model=APIResponse[Dict[str, Any]])
async def import_prompt_from_url(request: PromptImportRequest):
    """Scrape a PromptHero URL and return adapted prompt data ready to save."""
    try:
        record = _import_prompt_from_url(request.url)
        return APIResponse(
            data=record,
            message=f"Imported '{record.get('name', '')}' — preview before saving",
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
        prompt_id = request.id or f"prompthero_{uuid.uuid4().hex[:8]}"
        saved = _save_imported_prompt(prompt_id, request)
        return APIResponse(data=saved, message=f"Prompt '{request.name}' saved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-and-save", response_model=APIResponse[Dict[str, Any]])
async def import_and_save_prompt(request: PromptImportRequest):
    """Scrape a PromptHero URL and immediately save to the database."""
    try:
        record = _import_prompt_from_url(request.url)
        save_req = PromptSaveRequest(
            id=record.get("id"),
            name=record.get("name", "Imported Prompt"),
            system_prompt=record.get("system_prompt", ""),
            description=record.get("description", ""),
            category=record.get("category", "community"),
            logical_category=record.get("logical_category", "prompts"),
            tags=record.get("tags", []),
            config=record.get("config", {}),
            metadata_json=record.get("metadata_json", {}),
        )
        prompt_id = record.get("id", f"prompthero_{uuid.uuid4().hex[:8]}")
        saved = _save_imported_prompt(prompt_id, save_req)
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
                    records.append(spider.adapt_to_prompt_record(details))
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


# --- Composable Lego Prompts & Combinatorial Generator Endpoints ---

class ComposeBlockItem(BaseModel):
    id: Optional[str] = None
    type: str  # 'block' or 'custom'
    content: str  # Raw text or block template
    active: bool = True
    weight: float = 1.0


class ComposePromptRequest(BaseModel):
    blocks: List[ComposeBlockItem]
    variables: Dict[str, str] = {}


class GeneratePromptRequest(BaseModel):
    template: str
    mode: str = "combinatorial"  # "combinatorial" or "random"
    limit: int = 100
    seed: Optional[int] = None


class DbWildcardManager:
    """Combines DB wildcards and filesystem wildcards."""
    def __init__(self, fallback_manager: Any):
        self.fallback_manager = fallback_manager

    def get_wildcard(self, name: str) -> Optional[str]:
        # Try DB first
        try:
            from common_lib.modules.image_processing.functions.text.dynamic_engine.models import WildcardRecord
            from common_lib.modules.data_storage.database.connection import get_session
            from sqlmodel import select
            import random

            with next(get_session()) as session:
                stmt = select(WildcardRecord).where(WildcardRecord.name == name)
                record = session.execute(stmt).scalar_one_or_none()
                if record and record.values:
                    # Resolve weights if present
                    weights = []
                    clean_values = []
                    has_weights = False
                    for val in record.values:
                        if "::" in val:
                            parts = val.split("::", 1)
                            try:
                                w = float(parts[0])
                                weights.append(w)
                                clean_values.append(parts[1])
                                has_weights = True
                            except ValueError:
                                weights.append(1.0)
                                clean_values.append(val)
                        else:
                            weights.append(1.0)
                            clean_values.append(val)
                    if has_weights:
                        return random.choices(clean_values, weights=weights, k=1)[0]
                    return random.choice(record.values)
        except Exception as e:
            logger.warning(f"DB Wildcard fetch failed for {name}: {e}")

        # Fallback to filesystem
        return self.fallback_manager.get_wildcard(name)

    def get_all_values(self, name: str) -> List[str]:
        # Try DB first
        try:
            from common_lib.modules.image_processing.functions.text.dynamic_engine.models import WildcardRecord
            from common_lib.modules.data_storage.database.connection import get_session
            from sqlmodel import select

            with next(get_session()) as session:
                stmt = select(WildcardRecord).where(WildcardRecord.name == name)
                record = session.execute(stmt).scalar_one_or_none()
                if record and record.values:
                    return record.values
        except Exception as e:
            logger.warning(f"DB Wildcard list fetch failed for {name}: {e}")

        # Fallback to filesystem
        return self.fallback_manager.get_all_values(name)


@router.get("/blocks", response_model=APIResponse[List[Dict[str, Any]]])
async def list_prompt_blocks():
    """List all prompt blocks in the database."""
    try:
        from app.core.common_lib_integration import common_memory
        prompts = common_memory.list_prompt_definitions()
        blocks = [
            p for p in prompts
            if p.get("logical_category") == "block"
            or p.get("category") == "block"
            or "block" in p.get("config", {}).get("tags", [])
            or "block" in p.get("tags", [])
        ]
        return APIResponse(data=blocks, message=f"Found {len(blocks)} prompt blocks")
    except Exception as e:
        logger.error(f"Failed to list prompt blocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compose", response_model=APIResponse[Dict[str, Any]])
async def compose_prompt(request: ComposePromptRequest):
    """Compile a composed prompt blueprint from block stacks and variables."""
    try:
        compiled_parts = []
        for item in request.blocks:
            if not item.active:
                continue
            content = item.content
            # Interpolate variables
            interpolated = content
            for k, v in request.variables.items():
                interpolated = interpolated.replace(f"{{{{{k}}}}}", v)
                interpolated = interpolated.replace(f"${{{k}}}", v)

            # Apply attention weights if needed
            if item.weight != 1.0:
                part = f"({interpolated.strip()}:{item.weight})"
            else:
                part = interpolated.strip()
            compiled_parts.append(part)

        compiled_prompt = "\n\n".join(compiled_parts)
        return APIResponse(
            data={
                "compiled_prompt": compiled_prompt,
                "block_count": len(compiled_parts)
            },
            message="Prompt composed successfully"
        )
    except Exception as e:
        logger.error(f"Failed to compose prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=APIResponse[List[str]])
async def generate_prompts(request: GeneratePromptRequest):
    """Expand dynamic prompt template string into variations."""
    try:
        from common_lib.modules.image_processing.functions.text.dynamic_engine.expansion import PromptEngine
        from common_lib.modules.image_processing.functions.text.dynamic_engine.wildcards import WildcardManager
        from common_lib.modules.wildcards.service import WildcardService

        fallback_mgr = WildcardManager(str(WildcardService.DEFAULT_ROOT_DIR))
        db_wildcard_mgr = DbWildcardManager(fallback_mgr)
        engine = PromptEngine(db_wildcard_mgr)

        if request.mode == "combinatorial":
            results = engine.expand_combinatorial(request.template, limit=request.limit)
        else:
            results = engine.expand_random(
                request.template,
                num_prompts=request.limit,
                seed=request.seed
            )
        return APIResponse(data=results, message=f"Generated {len(results)} prompt variations")
    except Exception as e:
        logger.error(f"Failed to generate prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

