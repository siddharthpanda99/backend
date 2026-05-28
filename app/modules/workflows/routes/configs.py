"""Workflow Config CRUD API routes.

Provides full REST endpoints for workflow configuration presets:
- List, get, create, update, delete configs
- Comments (threaded)
- Image gallery
- Auto-generate 10+ config variants per workflow
"""

import copy
import logging
import random
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.core.common_lib_integration import common_memory, sync_entity_to_fs
from app.modules.common.types.index import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Pydantic Models ───────────────────────────────────────────────────────


class WorkflowConfigCreate(BaseModel):
    name: str
    workflow_id: Optional[str] = None
    version: str = "1.0.0"
    description: str = ""
    category: str = "General"
    tags: List[str] = []
    status: str = "ACTIVE"
    definition: Dict[str, Any] = {}
    field_schema: Dict[str, Any] = {}
    image_gallery: List[Dict[str, Any]] = []
    metadata_json: Dict[str, Any] = {}


class WorkflowConfigUpdate(BaseModel):
    name: Optional[str] = None
    workflow_id: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    field_schema: Optional[Dict[str, Any]] = None
    image_gallery: Optional[List[Dict[str, Any]]] = None
    metadata_json: Optional[Dict[str, Any]] = None


class CommentCreate(BaseModel):
    content: str
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    parent_id: Optional[str] = None


class CommentUpdate(BaseModel):
    content: Optional[str] = None
    is_resolved: Optional[bool] = None


class ImageCreate(BaseModel):
    url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    seed: Optional[int] = None
    prompt_used: Optional[str] = None
    negative_prompt_used: Optional[str] = None
    generation_params: Dict[str, Any] = {}


# ─── Config CRUD ────────────────────────────────────────────────────────────


@router.get("/", response_model=APIResponse[List[Dict[str, Any]]])
async def list_workflow_configs(
    workflow_id: Optional[str] = Query(
        None, description="Filter by parent workflow ID"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """List all workflow configs, optionally filtered."""
    try:
        if workflow_id:
            configs = common_memory.get_workflow_configs_by_workflow_id(workflow_id)
        else:
            configs = common_memory.list_workflow_config_definitions()

        if category:
            configs = [c for c in configs if c.get("category") == category]
        if status:
            configs = [c for c in configs if c.get("status") == status]

        return APIResponse(data=configs, message="Workflow configs retrieved")
    except Exception as e:
        logger.error(f"Failed to list workflow configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-workflow/{workflow_id}", response_model=APIResponse[List[Dict[str, Any]]]
)
async def list_workflow_configs_by_workflow(workflow_id: str):
    """List all configs for a specific workflow."""
    try:
        configs = common_memory.get_workflow_configs_by_workflow_id(workflow_id)
        return APIResponse(
            data=configs,
            message=f"Found {len(configs)} configs for workflow '{workflow_id}'",
        )
    except Exception as e:
        logger.error(f"Failed to list configs for workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def get_workflow_config(config_id: str):
    """Get a single workflow config by ID."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )
        return APIResponse(data=config, message="Workflow config retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def create_workflow_config(data: WorkflowConfigCreate):
    """Create a new workflow config."""
    try:
        config_id = data.name.lower().replace(" ", "_") or str(uuid.uuid4())[:8]

        # Check for duplicate
        existing = common_memory.get_workflow_config_definition(config_id)
        if existing:
            config_id = f"{config_id}_{uuid.uuid4().hex[:6]}"

        success = common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=data.name,
            definition=data.definition,
            version=data.version,
            description=data.description,
            category=data.category,
            tags=data.tags,
            status=data.status,
            workflow_id=data.workflow_id,
            field_schema=data.field_schema,
            image_gallery=data.image_gallery,
            metadata_json=data.metadata_json,
            artifacts={
                "import_source": "api",
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to create config")

        # Sync to filesystem
        sync_entity_to_fs("workflow_config", config_id)

        config = common_memory.get_workflow_config_definition(config_id)
        return APIResponse(
            data=config, message="Workflow config created", status_code=201
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create workflow config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def update_workflow_config(config_id: str, data: WorkflowConfigUpdate):
    """Update an existing workflow config."""
    try:
        existing = common_memory.get_workflow_config_definition(config_id)
        if not existing:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        # Merge updates
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                existing[key] = value

        success = common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=existing.get("name"),
            definition=existing.get("definition", {}),
            version=existing.get("version", "1.0.0"),
            description=existing.get("description", ""),
            category=existing.get("category", "General"),
            tags=existing.get("tags", []),
            status=existing.get("status", "ACTIVE"),
            workflow_id=existing.get("workflow_id"),
            field_schema=existing.get("field_schema", {}),
            image_gallery=existing.get("image_gallery", []),
            metadata_json=existing.get("metadata_json", {}),
            artifacts=existing.get("artifacts", {}),
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update config")

        sync_entity_to_fs("workflow_config", config_id)

        config = common_memory.get_workflow_config_definition(config_id)
        return APIResponse(data=config, message="Workflow config updated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}", response_model=APIResponse[Dict[str, Any]])
async def delete_workflow_config(config_id: str):
    """Delete a workflow config."""
    try:
        existing = common_memory.get_workflow_config_definition(config_id)
        if not existing:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        success = common_memory.delete_workflow_config_definition(config_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete config")

        return APIResponse(data={"id": config_id}, message="Workflow config deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Auto-generate configs ─────────────────────────────────────────────────


# Variant profiles: each defines overrides for node-level parameters
_VARIANT_PROFILES = [
    {
        "name": "Standard Quality",
        "category": "Balanced",
        "tags": ["balanced", "standard"],
        "params": {
            "sampler": {
                "steps": 25,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "karras",
                "denoise": 1.0,
            },
            "latent": {"width": 512, "height": 512},
            "upscale": {"scale_by": 2.0, "upscale_method": "bicubic"},
        },
        "description": "Balanced quality preset — 25 steps, CFG 7.0, Euler sampler with Karras scheduler",
    },
    {
        "name": "Fast Draft",
        "category": "Speed",
        "tags": ["fast", "draft", "speed"],
        "params": {
            "sampler": {
                "steps": 10,
                "cfg": 5.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
            "latent": {"width": 512, "height": 512},
            "upscale": {"scale_by": 1.5, "upscale_method": "nearest-exact"},
        },
        "description": "Quick preview — 10 steps, CFG 5.0 for rapid iteration",
    },
    {
        "name": "High Quality",
        "category": "Quality",
        "tags": ["quality", "detailed"],
        "params": {
            "sampler": {
                "steps": 40,
                "cfg": 7.5,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "karras",
                "denoise": 1.0,
            },
            "latent": {"width": 512, "height": 512},
            "upscale": {"scale_by": 2.0, "upscale_method": "lanczos"},
        },
        "description": "High detail — 40 steps, CFG 7.5, DPM++ 2M SDE with Karras scheduler",
    },
    {
        "name": "Ultra Quality",
        "category": "Quality",
        "tags": ["quality", "ultra", "maximum"],
        "params": {
            "sampler": {
                "steps": 50,
                "cfg": 8.0,
                "sampler_name": "dpmpp_3m_sde",
                "scheduler": "exponential",
                "denoise": 1.0,
            },
            "latent": {"width": 768, "height": 768},
            "upscale": {"scale_by": 2.0, "upscale_method": "lanczos"},
        },
        "description": "Maximum quality — 50 steps, CFG 8.0, DPM++ 3M SDE with Exponential scheduler",
    },
    {
        "name": "Low CFG Creative",
        "category": "Creative",
        "tags": ["creative", "low-cfg", "experimental"],
        "params": {
            "sampler": {
                "steps": 25,
                "cfg": 3.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
            "latent": {"width": 512, "height": 512},
            "upscale": {"scale_by": 2.0, "upscale_method": "bicubic"},
        },
        "description": "Low CFG (3.0) for more creative freedom and surprise results",
    },
    {
        "name": "High CFG Sharp",
        "category": "Precision",
        "tags": ["sharp", "high-cfg", "precise"],
        "params": {
            "sampler": {
                "steps": 30,
                "cfg": 12.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
            },
            "latent": {"width": 512, "height": 512},
            "upscale": {"scale_by": 2.0, "upscale_method": "lanczos"},
        },
        "description": "High CFG (12.0) for sharp adherence to prompts with DPM++ 2M",
    },
    {
        "name": "DDIM Fast",
        "category": "Speed",
        "tags": ["fast", "ddim"],
        "params": {
            "sampler": {
                "steps": 15,
                "cfg": 6.0,
                "sampler_name": "ddim",
                "scheduler": "ddim_uniform",
                "denoise": 1.0,
            },
            "latent": {"width": 512, "height": 512},
            "upscale": {"scale_by": 1.5, "upscale_method": "bilinear"},
        },
        "description": "DDIM sampler — 15 steps, CFG 6.0 for fast deterministic generation",
    },
    {
        "name": "Portrait",
        "category": "Portrait",
        "tags": ["portrait", "vertical"],
        "params": {
            "sampler": {
                "steps": 25,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "karras",
                "denoise": 1.0,
            },
            "latent": {"width": 512, "height": 768},
            "upscale": {"scale_by": 2.0, "upscale_method": "bicubic"},
        },
        "description": "Portrait orientation — 512x768, Euler with Karras, optimized for faces",
    },
    {
        "name": "Landscape",
        "category": "Landscape",
        "tags": ["landscape", "wide"],
        "params": {
            "sampler": {
                "steps": 30,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "karras",
                "denoise": 1.0,
            },
            "latent": {"width": 768, "height": 512},
            "upscale": {"scale_by": 2.0, "upscale_method": "bicubic"},
        },
        "description": "Landscape orientation — 768x512, DPM++ 2M SDE for scenic detail",
    },
    {
        "name": "Square Ultra",
        "category": "Quality",
        "tags": ["square", "quality"],
        "params": {
            "sampler": {
                "steps": 35,
                "cfg": 7.5,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "karras",
                "denoise": 1.0,
            },
            "latent": {"width": 768, "height": 768},
            "upscale": {"scale_by": 2.0, "upscale_method": "lanczos"},
        },
        "description": "Square format — 768x768, 35 steps, DPM++ 2M SDE for balanced composition",
    },
    {
        "name": "Anime Style",
        "category": "Style",
        "tags": ["anime", "style"],
        "params": {
            "sampler": {
                "steps": 25,
                "cfg": 6.5,
                "sampler_name": "euler_ancestral",
                "scheduler": "karras",
                "denoise": 1.0,
            },
            "latent": {"width": 512, "height": 512},
            "upscale": {"scale_by": 2.0, "upscale_method": "bicubic"},
        },
        "description": "Anime-optimized — Euler Ancestral, CFG 6.5 for stylized output",
    },
    {
        "name": "Cinematic",
        "category": "Cinematic",
        "tags": ["cinematic", "film", "dramatic"],
        "params": {
            "sampler": {
                "steps": 30,
                "cfg": 8.0,
                "sampler_name": "dpmpp_2m_sde",
                "scheduler": "exponential",
                "denoise": 1.0,
            },
            "latent": {"width": 768, "height": 432},
            "upscale": {"scale_by": 2.0, "upscale_method": "lanczos"},
        },
        "description": "Cinematic widescreen — 768x432 (16:9), DPM++ 2M SDE, Exponential scheduler",
    },
]


def _detect_node_role(node_type: str) -> str:
    """Classify a node into a role group for param assignment."""
    t = node_type.lower()
    if "checkpoint" in t or "model" in t:
        return "checkpoint"
    if "clip" in t or "encode" in t or "prompt" in t:
        return "prompt"
    if "ksampler" in t or "sampler" in t:
        return "sampler"
    if "latent" in t and "upscale" not in t:
        return "latent"
    if "upscale" in t:
        return "upscale"
    if "vae" in t and "decode" in t:
        return "vae_decode"
    if "vae" in t:
        return "vae"
    if "save" in t or "image" in t:
        return "save"
    if "face" in t or "reactor" in t:
        return "face"
    return "other"


def _build_node_definition(node: Dict, profile_params: Dict, seeds: List[int]) -> Dict:
    """Build a node definition by merging base properties with profile overrides."""
    node_type = node.get("type", "")
    role = _detect_node_role(node_type)
    base_props = dict(node.get("properties", {}))

    overrides = profile_params.get(role, {})
    resolved = {}

    for key, val in base_props.items():
        if isinstance(val, str) and val.startswith("{{") and val.endswith("}}"):
            param_name = val[2:-2]
            if param_name in overrides:
                resolved[key] = overrides[param_name]
            elif param_name == "seed":
                resolved[key] = seeds[0]
            else:
                resolved[key] = val
        else:
            resolved[key] = val

    resolved.update(overrides)

    if role == "sampler":
        if "seed" not in resolved or (
            isinstance(resolved.get("seed"), str) and resolved["seed"].startswith("{{")
        ):
            resolved["seed"] = seeds.pop(0) if seeds else random.randint(0, 2**31)

    resolved = {
        k: v
        for k, v in resolved.items()
        if v is not None and (not isinstance(v, str) or v != "")
    }
    return resolved


@router.post(
    "/workflows/{workflow_id}/generate-configs",
    response_model=APIResponse[List[Dict[str, Any]]],
)
async def generate_workflow_configs(
    workflow_id: str,
    prompt_source: str = Query(
        "random", description="Source of prompts: 'random', 'prompthero', or 'database'"
    ),
    prompthero_model: str = Query(
        "sd15", description="Model slug for prompthero scraping"
    ),
):
    """Auto-generate 10+ data config variants for a workflow, organized by node.

    When prompt_source='prompthero', fetches real prompts from PromptHero and uses them.
    When prompt_source='database', uses prompts already saved in the database.
    When prompt_source='random' (default), generates synthetic placeholder prompts.
    """
    try:
        from common_lib.modules.workflows.standard.registry.workflow_registry import (
            get_workflow_registry,
        )

        registry = get_workflow_registry()
        workflow = registry.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=404, detail=f"Workflow '{workflow_id}' not found"
            )

        nodes = workflow.get("nodes", [])
        if not nodes:
            raise HTTPException(status_code=400, detail="Workflow has no nodes")

        existing_configs = common_memory.get_workflow_configs_by_workflow_id(
            workflow_id
        )
        existing_names = {c.get("name", "") for c in existing_configs}

        real_prompts = []
        if prompt_source == "prompthero":
            try:
                from common_lib.plugins.web_scraper.spiders.prompthero import (
                    PromptHeroSpider,
                )
                from common_lib.plugins.web_scraper.core.engine import ScraperCore

                fetcher = ScraperCore().get_fetcher()
                spider = PromptHeroSpider(fetcher)
                result = spider.run(
                    model=prompthero_model,
                    sort="popular",
                    limit=len(_VARIANT_PROFILES),
                )
                if result.get("success"):
                    real_prompts = [
                        p.get("prompt_text", "") for p in result.get("prompts", [])
                    ][: len(_VARIANT_PROFILES)]
                logger.info(f"Fetched {len(real_prompts)} real prompts from PromptHero")
            except Exception as e:
                logger.warning(
                    f"Failed to fetch prompthero prompts: {e}. Falling back to random."
                )
        elif prompt_source == "database":
            try:
                db_prompts = common_memory.list_prompt_definitions()
                real_prompts = [
                    p.get("system_prompt", "") or p.get("text", "")
                    for p in db_prompts
                    if p.get("system_prompt") or p.get("text")
                ][: len(_VARIANT_PROFILES)]
                logger.info(f"Using {len(real_prompts)} prompts from database")
            except Exception as e:
                logger.warning(
                    f"Failed to load DB prompts: {e}. Falling back to random."
                )

        placeholder_prompts = [
            "A majestic dragon soaring through storm clouds at sunset, volumetric lighting",
            "A serene Japanese garden with cherry blossoms, soft morning light",
            "A steampunk airship docked in Victorian London, intricate details",
            "An alien planet landscape with bioluminescent flora, twin moons",
            "A fantasy warrior in ornate armor, dramatic rim lighting",
            "A cyberpunk cityscape at night with neon reflections on wet pavement",
            "A cozy cottage in an enchanted forest, warm firelight through windows",
        ]

        created_ids = []
        seeds_pool = [42, 123, 456, 789, 1001, 2024, 77, 888, 314, 1618, 2718, 999]

        for idx, profile in enumerate(_VARIANT_PROFILES):
            config_name = f"{workflow_id}_{profile['name'].lower().replace(' ', '_')}"
            if config_name in existing_names:
                config_name = f"{config_name}_{uuid.uuid4().hex[:4]}"

            seeds = seeds_pool[idx * 3 : (idx + 1) * 3]
            if not seeds:
                seeds = [random.randint(0, 2**31)]

            definition = {}
            field_schema = {}

            prompt_text = ""
            if real_prompts and idx < len(real_prompts):
                prompt_text = real_prompts[idx]
            else:
                prompt_text = placeholder_prompts[idx % len(placeholder_prompts)]

            for node in nodes:
                node_id = node.get("id", f"node_{len(definition)}")
                node_type = node.get("type", "")
                node_def = _build_node_definition(node, profile["params"], seeds)

                role = _detect_node_role(node_type)
                if role == "prompt" and prompt_text:
                    if "text" in node_def:
                        node_def["text"] = prompt_text
                    else:
                        node_def["prompt"] = prompt_text

                definition[node_id] = node_def

                field_schema[node_id] = {}
                for key, val in node_def.items():
                    val_type = "text"
                    if isinstance(val, bool):
                        val_type = "boolean"
                    elif isinstance(val, int):
                        val_type = "number"
                    elif isinstance(val, float):
                        val_type = "number"
                    field_schema[node_id][key] = {
                        "type": val_type,
                        "label": key.replace("_", " ").title(),
                        "default": val,
                    }

            description = profile["description"]
            tags = list(profile["tags"])

            seeds_used = seeds_pool[idx * 3 : (idx + 1) * 3] or [
                random.randint(0, 2**31)
            ]

            success = common_memory.save_workflow_config_definition(
                config_id=config_name,
                name=profile["name"],
                definition=definition,
                version="1.0.0",
                description=description,
                category=profile["category"],
                tags=tags + [f"seed-{s}" for s in seeds_used],
                status="ACTIVE",
                workflow_id=workflow_id,
                field_schema=field_schema,
                image_gallery=[],
                metadata_json={
                    "author": "Auto-generator",
                    "generated": True,
                    "variant_index": idx,
                    "seeds": seeds_used,
                    "profile": profile["name"],
                    "prompt_source": prompt_source,
                    "prompt_used": prompt_text[:100] if prompt_text else "",
                },
                artifacts={
                    "import_source": "auto_generate",
                    "created_at": datetime.utcnow().isoformat(),
                },
            )

            if success:
                created_ids.append(config_name)
                sync_entity_to_fs("workflow_config", config_name)

        configs = [
            common_memory.get_workflow_config_definition(cid) for cid in created_ids
        ]
        configs = [c for c in configs if c]
        return APIResponse(
            data=configs,
            message=f"Generated {len(configs)} config variants for workflow '{workflow_id}'",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate configs for workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Seed / Bulk Generate ─────────────────────────────────────────────────


@router.post("/seed", response_model=APIResponse[Dict[str, Any]])
async def seed_all_workflow_configs(
    priority: str = Query(
        "sd15", description="Priority workflow type: 'sd15', 'audio', 'all'"
    ),
    force: bool = Query(
        False, description="Re-generate configs even if they already exist"
    ),
):
    """Seed configs for all workflows. Imports data-config YAMLs, then auto-generates for workflows without configs."""
    import os
    import yaml

    from common_lib.paths import REPO_ROOT

    results = {
        "imported_yaml": 0,
        "auto_generated": 0,
        "skipped": 0,
        "errors": 0,
        "details": [],
    }

    data_config_dir = (
        REPO_ROOT
        / "Python Libs"
        / "common_lib"
        / "src"
        / "common_lib"
        / "templates"
        / "workflows"
        / "data-config"
    )
    if data_config_dir.exists():
        for root, dirs, files in os.walk(str(data_config_dir)):
            for fname in files:
                if not fname.endswith((".yaml", ".yml")):
                    continue
                try:
                    fpath = os.path.join(root, fname)
                    with open(fpath) as f:
                        raw = yaml.safe_load(f)
                    if not raw:
                        continue
                    config_id = raw.get("id") or fname.replace(".yaml", "").replace(
                        ".yml", ""
                    )
                    existing = common_memory.get_workflow_config_definition(config_id)
                    if existing and not force:
                        results["skipped"] += 1
                        continue
                    definition = raw.get("definition", {})
                    field_schema = raw.get("field_schema", {})
                    data_cfg = raw.get("data_config", {})
                    if not definition and data_cfg:
                        definition = {
                            "prompt": data_cfg.get("prompt", ""),
                            "negative_prompt": data_cfg.get("negative_prompt", ""),
                            "steps": data_cfg.get("steps", 25),
                            "cfg": data_cfg.get("cfg_scale", 7.0),
                            "sampler": data_cfg.get("sampler", "euler"),
                            "width": data_cfg.get("width", 512),
                            "height": data_cfg.get("height", 512),
                        }
                    success = common_memory.save_workflow_config_definition(
                        config_id=config_id,
                        name=raw.get(
                            "name",
                            raw.get("metadata", {}).get("legacy_name", config_id),
                        ),
                        definition=definition,
                        field_schema=field_schema or raw.get("field_schema", {}),
                        version=raw.get("version", "1.0.0"),
                        description=raw.get("description", ""),
                        category=raw.get(
                            "category",
                            raw.get("metadata", {}).get("category", "General"),
                        ),
                        tags=raw.get("tags", []),
                        status=raw.get("status", "ACTIVE"),
                        workflow_id=raw.get("workflow_id", ""),
                        image_gallery=raw.get("image_gallery", []),
                        metadata_json=raw.get("metadata_json", raw.get("metadata", {})),
                    )
                    if success:
                        results["imported_yaml"] += 1
                        results["details"].append(f"Imported YAML config: {config_id}")
                except Exception as e:
                    logger.warning(f"Failed to import config {fname}: {e}")
                    results["errors"] += 1

    from common_lib.modules.workflows.standard.registry.workflow_registry import (
        get_workflow_registry,
    )

    registry = get_workflow_registry()
    all_workflows = registry.list_workflows()

    priority_workflows = []
    other_workflows = []

    for wf in all_workflows or []:
        wf_id = wf.get("id", "")
        wf_cats = (wf.get("category", "") or "").lower()
        wf_name = (wf.get("name", "") or "").lower()
        wf_tags = [t.lower() for t in (wf.get("tags", []) or [])]
        wf_nodes = [n.get("type", "") for n in (wf.get("nodes", []) or [])]

        is_sd15 = (
            "sd15" in wf_id.lower()
            or "sd1.5" in wf_id.lower()
            or "stage" in wf_id
            or "vision" in wf_cats
            or any("checkpoint" in n for n in wf_nodes)
        )
        is_audio = (
            "audio" in wf_cats
            or "audio" in wf_tags
            or "tts" in wf_id
            or "audio" in wf_id
        )

        if priority == "sd15" and is_sd15:
            priority_workflows.append(wf)
        elif priority == "audio" and is_audio:
            priority_workflows.append(wf)
        elif priority == "all":
            priority_workflows.append(wf)
        else:
            other_workflows.append(wf)

    ordered = priority_workflows + other_workflows

    for wf in ordered:
        wf_id = wf.get("id", "")
        try:
            existing = common_memory.get_workflow_configs_by_workflow_id(wf_id)
            if existing and not force:
                results["skipped"] += 1
                continue

            wf["nodes"] = wf.get("nodes", [])
            created = await _auto_generate_single_workflow(wf_id)
            if created:
                results["auto_generated"] += len(created)
                results["details"].append(
                    f"Generated {len(created)} configs for '{wf_id}'"
                )
        except Exception as e:
            logger.warning(f"Failed to generate configs for {wf_id}: {e}")
            results["errors"] += 1
            continue

    return APIResponse(
        data=results,
        message=f"Seeded {results['imported_yaml']} YAML + {results['auto_generated']} auto-generated configs",
    )


async def _auto_generate_single_workflow(workflow_id: str) -> List[str]:
    """Generate 12 variant configs for a single workflow. Reuse logic from generate_workflow_configs."""
    from common_lib.modules.workflows.standard.registry.workflow_registry import (
        get_workflow_registry,
    )

    registry = get_workflow_registry()
    workflow = registry.get_workflow(workflow_id)
    if not workflow:
        return []

    nodes = workflow.get("nodes", [])
    if not nodes:
        return []

    existing_configs = common_memory.get_workflow_configs_by_workflow_id(workflow_id)
    existing_names = {c.get("name", "") for c in existing_configs}

    placeholder_prompts = [
        "A majestic dragon soaring through storm clouds at sunset",
        "A serene Japanese garden with cherry blossoms",
        "A steampunk airship docked in Victorian London",
        "An alien planet landscape with bioluminescent flora",
        "A fantasy warrior in ornate armor",
        "A cyberpunk cityscape at night",
        "A cozy cottage in an enchanted forest",
        "A magical forest glade with glowing mushrooms",
        "A futuristic city with flying cars",
        "A portrait of a mysterious figure in shadow",
        "A dramatic landscape of mountains at sunrise",
        "A still life with flowers and fruits",
    ]

    created_ids = []
    seeds_pool = [42, 123, 456, 789, 1001, 2024, 77, 888, 314, 1618, 2718, 999]

    for idx, profile in enumerate(_VARIANT_PROFILES):
        config_name = f"{workflow_id}_{profile['name'].lower().replace(' ', '_')}"
        if config_name in existing_names:
            config_name = f"{config_name}_{uuid.uuid4().hex[:4]}"

        seeds = seeds_pool[idx * 3 : (idx + 1) * 3]
        if not seeds:
            seeds = [random.randint(0, 2**31)]

        definition = {}
        field_schema = {}
        prompt_text = placeholder_prompts[idx % len(placeholder_prompts)]

        for node in nodes:
            node_id = node.get("id", f"node_{len(definition)}")
            node_type = node.get("type", "")
            node_def = _build_node_definition(node, profile["params"], seeds)
            role = _detect_node_role(node_type)
            if role == "prompt" and prompt_text:
                node_def["text"] = prompt_text

            definition[node_id] = node_def
            field_schema[node_id] = {}
            for key, val in node_def.items():
                val_type = "text"
                if isinstance(val, bool):
                    val_type = "boolean"
                elif isinstance(val, int):
                    val_type = "number"
                elif isinstance(val, float):
                    val_type = "number"
                field_schema[node_id][key] = {
                    "type": val_type,
                    "label": key.replace("_", " ").title(),
                    "default": val,
                }

        success = common_memory.save_workflow_config_definition(
            config_id=config_name,
            name=profile["name"],
            definition=definition,
            version="1.0.0",
            description=profile["description"],
            category=profile["category"],
            tags=list(profile["tags"]),
            status="ACTIVE",
            workflow_id=workflow_id,
            field_schema=field_schema,
            image_gallery=[],
            metadata_json={
                "author": "Auto-generator",
                "generated": True,
                "variant_index": idx,
                "profile": profile["name"],
            },
            artifacts={
                "import_source": "auto_generate",
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        if success:
            created_ids.append(config_name)

    for cid in created_ids:
        sync_entity_to_fs("workflow_config", cid)

    return created_ids


# ─── Comments ───────────────────────────────────────────────────────────────


@router.get("/{config_id}/comments", response_model=APIResponse[List[Dict[str, Any]]])
async def list_comments(config_id: str):
    """List all comments for a config."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        comments = config.get("metadata_json", {}).get("comments", [])
        # Filter out deleted
        comments = [c for c in comments if not c.get("is_deleted", False)]
        return APIResponse(data=comments, message="Comments retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list comments for config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/comments", response_model=APIResponse[Dict[str, Any]])
async def create_comment(config_id: str, data: CommentCreate):
    """Add a comment to a config."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        comment = {
            "id": str(uuid.uuid4()),
            "config_id": config_id,
            "parent_id": data.parent_id,
            "author_id": data.author_id,
            "author_name": data.author_name or "Anonymous",
            "content": data.content,
            "reactions": {},
            "is_resolved": False,
            "is_deleted": False,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        metadata = config.get("metadata_json", {})
        comments = metadata.get("comments", [])
        comments.append(comment)
        metadata["comments"] = comments

        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=config.get("image_gallery", []),
            metadata_json=metadata,
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data=comment, message="Comment added", status_code=201)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add comment to config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{config_id}/comments/{comment_id}", response_model=APIResponse[Dict[str, Any]]
)
async def update_comment(config_id: str, comment_id: str, data: CommentUpdate):
    """Update a comment."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        metadata = config.get("metadata_json", {})
        comments = metadata.get("comments", [])
        target = None
        for c in comments:
            if c["id"] == comment_id:
                target = c
                break

        if not target:
            raise HTTPException(
                status_code=404, detail=f"Comment '{comment_id}' not found"
            )

        if data.content is not None:
            target["content"] = data.content
        if data.is_resolved is not None:
            target["is_resolved"] = data.is_resolved
        target["updated_at"] = datetime.utcnow().isoformat()

        metadata["comments"] = comments
        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=config.get("image_gallery", []),
            metadata_json=metadata,
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data=target, message="Comment updated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{config_id}/comments/{comment_id}", response_model=APIResponse[Dict[str, Any]]
)
async def delete_comment(config_id: str, comment_id: str):
    """Soft-delete a comment."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        metadata = config.get("metadata_json", {})
        comments = metadata.get("comments", [])
        for c in comments:
            if c["id"] == comment_id:
                c["is_deleted"] = True
                c["updated_at"] = datetime.utcnow().isoformat()
                break

        metadata["comments"] = comments
        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=config.get("image_gallery", []),
            metadata_json=metadata,
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data={"id": comment_id}, message="Comment deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Image Gallery ──────────────────────────────────────────────────────────


@router.get("/{config_id}/images", response_model=APIResponse[List[Dict[str, Any]]])
async def list_images(config_id: str):
    """List all images for a config."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        images = config.get("image_gallery", [])
        return APIResponse(data=images, message="Images retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list images for config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/images", response_model=APIResponse[Dict[str, Any]])
async def add_image(config_id: str, data: ImageCreate):
    """Add an image to a config's gallery."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        image = {
            "id": str(uuid.uuid4()),
            "url": data.url,
            "thumbnail_url": data.thumbnail_url,
            "width": data.width,
            "height": data.height,
            "file_size": data.file_size,
            "seed": data.seed,
            "prompt_used": data.prompt_used,
            "negative_prompt_used": data.negative_prompt_used,
            "generation_params": data.generation_params,
            "likes": 0,
            "is_featured": False,
            "created_at": datetime.utcnow().isoformat(),
        }

        gallery = config.get("image_gallery", [])
        gallery.append(image)

        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=gallery,
            metadata_json=config.get("metadata_json", {}),
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data=image, message="Image added", status_code=201)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add image to config {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{config_id}/images/{image_id}", response_model=APIResponse[Dict[str, Any]]
)
async def delete_image(config_id: str, image_id: str):
    """Remove an image from a config's gallery."""
    try:
        config = common_memory.get_workflow_config_definition(config_id)
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        gallery = config.get("image_gallery", [])
        gallery = [img for img in gallery if img.get("id") != image_id]

        common_memory.save_workflow_config_definition(
            config_id=config_id,
            name=config.get("name"),
            definition=config.get("definition", {}),
            version=config.get("version", "1.0.0"),
            description=config.get("description", ""),
            category=config.get("category", "General"),
            tags=config.get("tags", []),
            status=config.get("status", "ACTIVE"),
            workflow_id=config.get("workflow_id"),
            field_schema=config.get("field_schema", {}),
            image_gallery=gallery,
            metadata_json=config.get("metadata_json", {}),
            artifacts=config.get("artifacts", {}),
        )

        return APIResponse(data={"id": image_id}, message="Image deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Stats ──────────────────────────────────────────────────────────────────


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
async def get_config_stats():
    """Get workflow config statistics."""
    try:
        configs = common_memory.list_workflow_config_definitions()
        categories = {}
        statuses = {}
        workflow_counts = {}

        for c in configs:
            cat = c.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
            status = c.get("status", "ACTIVE")
            statuses[status] = statuses.get(status, 0) + 1
            wf_id = c.get("workflow_id")
            if wf_id:
                workflow_counts[wf_id] = workflow_counts.get(wf_id, 0) + 1

        stats = {
            "total": len(configs),
            "categories": categories,
            "statuses": statuses,
            "configs_per_workflow": workflow_counts,
        }
        return APIResponse(data=stats, message="Config statistics retrieved")
    except Exception as e:
        logger.error(f"Failed to get config stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
