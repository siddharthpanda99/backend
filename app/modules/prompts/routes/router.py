"""Prompts API Routes — thin routes delegating to common_lib services."""

import logging
import uuid
import re
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.modules.common.types.index import APIResponse
from common_lib.modules.prompts.services.prompt_import_service import (
    PromptImportService,
)
from common_lib.modules.image_processing.functions.text.dynamic_engine.services.wildcard_resolver import (
    DbWildcardManager,
)

logger = logging.getLogger(__name__)
router = APIRouter()
_svc = PromptImportService()


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
    try:
        record = _svc.import_from_url(request.url)
        return APIResponse(
            data=record,
            message=f"Imported '{record.get('name', '')}' — preview before saving",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Prompt import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save", response_model=APIResponse[Dict[str, Any]])
async def save_imported_prompt(request: PromptSaveRequest):
    try:
        saved = _svc.save_prompt(
            None,
            {
                "id": request.id or f"prompthero_{uuid.uuid4().hex[:8]}",
                "name": request.name,
                "system_prompt": request.system_prompt,
                "description": request.description,
                "category": request.category,
                "logical_category": request.logical_category,
                "tags": request.tags,
                "config": request.config,
                "metadata_json": request.metadata_json,
            },
        )
        return APIResponse(data=saved, message=f"Prompt '{request.name}' saved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-and-save", response_model=APIResponse[Dict[str, Any]])
async def import_and_save_prompt(request: PromptImportRequest):
    try:
        record = _svc.import_from_url(request.url)
        saved = _svc.save_prompt(None, record)
        return APIResponse(
            data=saved, message=f"Prompt '{record.get('name', '')}' imported and saved"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import and save prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=APIResponse[List[Dict[str, Any]]])
async def list_imported_prompts():
    try:
        prompts = _svc.list_prompts(None)
        return APIResponse(data=prompts, message=f"Found {len(prompts)} prompts")
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/import/batch", response_model=APIResponse[List[Dict[str, Any]]])
async def batch_import_prompts(
    model: str = Query("sd15", description="Model slug"),
    limit: int = Query(12, description="Number of prompts to fetch"),
):
    try:
        records = _svc.batch_import(model=model, limit=limit)
        return APIResponse(
            data=records, message=f"Fetched {len(records)} prompts from PromptHero"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Batch import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source/{source}", response_model=APIResponse[List[Dict[str, Any]]])
async def list_prompts_by_source(source: str):
    try:
        prompts = _svc.list_prompts(None)
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
    name: Optional[str] = None
    type: str
    content: str
    active: bool = True
    weight: float = 1.0


class VariableDeclarationItem(BaseModel):
    key: str
    type: str = "text"
    label: Optional[str] = None
    value: str = ""
    defaultValue: Optional[Any] = None


class ComposePromptRequest(BaseModel):
    blocks: List[ComposeBlockItem]
    variables: Dict[str, str] = {}
    variable_definitions: Optional[Dict[str, VariableDeclarationItem]] = None


class GeneratePromptRequest(BaseModel):
    template: str
    mode: str = "combinatorial"
    limit: int = 100
    seed: Optional[int] = None


@router.get("/blocks", response_model=APIResponse[List[Dict[str, Any]]])
async def list_prompt_blocks():
    try:
        from app.core.common_lib_integration import common_memory

        prompts = common_memory.list_prompt_definitions()
        blocks = [
            p
            for p in prompts
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
    try:
        compiled_parts = []
        segments = []
        block_entries = []
        variable_map: Dict[str, Dict[str, Any]] = {}

        # Build variable map from explicit definitions + value overrides
        if request.variable_definitions:
            for key, decl in request.variable_definitions.items():
                variable_map[key] = {
                    "key": decl.key,
                    "type": decl.type,
                    "label": decl.label,
                    "value": request.variables.get(key, decl.value),
                    "defaultValue": decl.defaultValue,
                }
        else:
            for k, v in request.variables.items():
                variable_map[k] = {"key": k, "type": "text", "value": v}

        for item in request.blocks:
            if not item.active:
                continue
            content = item.content
            interpolated = content

            # Build segments for structured output
            seg_re = re.compile(r"\{\{([^}]+)\}\}|\$\{([^}]+)\}")
            last_idx = 0
            block_segments = []

            for m in seg_re.finditer(content):
                key = (
                    (m.group(1) or m.group(2))
                    .strip()
                    .split(":")[0]
                    .split("|")[0]
                    .strip()
                )
                val = request.variables.get(key, "")

                if m.start() > last_idx:
                    block_segments.append(
                        {"type": "text", "value": content[last_idx : m.start()]}
                    )
                block_segments.append(
                    {
                        "type": "variable",
                        "value": val or f"[{key}]",
                        "key": key,
                        "declaredType": variable_map.get(key, {}).get("type"),
                    }
                )
                last_idx = m.end()

            if last_idx < len(content):
                block_segments.append({"type": "text", "value": content[last_idx:]})

            # Interpolate for flat output
            for k, v in request.variables.items():
                interpolated = interpolated.replace(f"{{{{{k}}}}}", v)
                interpolated = interpolated.replace(f"${{{k}}}", v)

            if item.weight != 1.0:
                part = f"({interpolated.strip()}:{item.weight})"
            else:
                part = interpolated.strip()

            compiled_parts.append(part)
            segments.extend(block_segments)

            block_entries.append(
                {
                    "id": item.id,
                    "name": item.name or item.id or item.type,
                    "content": item.content,
                    "active": item.active,
                    "weight": item.weight,
                }
            )

        compiled_prompt = "\n\n".join(compiled_parts)

        return APIResponse(
            data={
                "compiled_prompt": compiled_prompt,
                "block_count": len(compiled_parts),
                "structured": {
                    "blocks": block_entries,
                    "variables": variable_map,
                    "segments": segments,
                    "resolved_text": compiled_prompt,
                    "metadata": {
                        "compiled_at": datetime.utcnow().isoformat(),
                        "version": 1,
                    },
                },
            },
            message="Prompt composed successfully",
        )
    except Exception as e:
        logger.error(f"Failed to compose prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=APIResponse[List[str]])
async def generate_prompts(request: GeneratePromptRequest):
    try:
        from common_lib.modules.image_processing.functions.text.dynamic_engine.expansion import (
            PromptEngine,
        )
        from common_lib.modules.image_processing.functions.text.dynamic_engine.wildcards import (
            WildcardManager,
        )
        from common_lib.modules.wildcards.service import WildcardService

        fallback_mgr = WildcardManager(str(WildcardService.DEFAULT_ROOT_DIR))
        db_wildcard_mgr = DbWildcardManager(fallback_mgr)
        engine = PromptEngine(db_wildcard_mgr)

        if request.mode == "combinatorial":
            results = engine.expand_combinatorial(request.template, limit=request.limit)
        else:
            results = engine.expand_random(
                request.template, num_prompts=request.limit, seed=request.seed
            )
        return APIResponse(
            data=results, message=f"Generated {len(results)} prompt variations"
        )
    except Exception as e:
        logger.error(f"Failed to generate prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
