"""RIP ETL Routes — FastAPI endpoints for ETL Builder."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.rip.rip_etl.service import get_etl_service
from common_lib.modules.rip.rip_etl.engine import PipelineEngine
from common_lib.modules.rip.rip_etl.variants import list_variants, get_variant
from common_lib.modules.rip.rip_etl.comparison import get_comparison_engine
from common_lib.modules.rip.rip_etl.presets import list_presets, get_preset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/etl", tags=["rip-etl"])


# ── Schemas ───────────────────────────────────────────────────────


class CreateInstanceBody(BaseModel):
    name: str
    description: str = ""
    pipeline_id: str = ""
    tags: list[str] = Field(default_factory=list)


class ExecutePipelineBody(BaseModel):
    content: str
    source_type: str = "text"
    pipeline_id: str = ""


class CompareBody(BaseModel):
    content: str
    source_type: str = "text"
    variant_ids: list[str] = Field(default_factory=list)


# ── Instance CRUD ─────────────────────────────────────────────────


@router.get("/instances")
async def list_instances():
    svc = get_etl_service()
    return {"items": svc.list_instances(), "total": len(svc.list_instances())}


@router.post("/instances")
async def create_instance(body: CreateInstanceBody):
    svc = get_etl_service()
    pipeline_config = None
    if body.pipeline_id:
        preset = get_preset(body.pipeline_id)
        if preset:
            from common_lib.modules.rip.rip_etl.schemas import (
                PipelineConfig,
                PipelineStepConfig,
            )

            pipeline_config = PipelineConfig(
                id=preset["id"],
                name=preset["name"],
                description=preset["description"],
                steps=[PipelineStepConfig(**s) for s in preset["steps"]],
                is_preset=True,
                preset_name=preset["preset_name"],
            )
    inst = svc.create_instance(
        name=body.name,
        description=body.description,
        pipeline_config=pipeline_config,
        tags=body.tags,
    )
    return inst


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str):
    svc = get_etl_service()
    inst = svc.get_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Instance not found")
    return inst


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    svc = get_etl_service()
    svc.delete_instance(instance_id)
    return {"deleted": True}


# ── Pipeline CRUD ─────────────────────────────────────────────────


@router.get("/pipelines")
async def list_pipelines():
    svc = get_etl_service()
    return {"items": svc.list_pipelines(), "total": len(svc.list_pipelines())}


@router.get("/presets")
async def get_presets():
    return {"items": list_presets(), "total": len(list_presets())}


@router.get("/presets/{preset_name}")
async def get_preset_detail(preset_name: str):
    p = get_preset(preset_name)
    if not p:
        raise HTTPException(404, "Preset not found")
    return p


# ── Variants ──────────────────────────────────────────────────────


@router.get("/variants")
async def get_variants():
    variants = list_variants()
    return {"items": variants, "total": len(variants)}


@router.get("/variants/{variant_id}")
async def get_variant_detail(variant_id: str):
    v = get_variant(variant_id)
    if not v:
        raise HTTPException(404, "Variant not found")
    return v


# ── Execute ───────────────────────────────────────────────────────


@router.post("/execute")
async def execute_pipeline(body: ExecutePipelineBody, instance_id: str = ""):
    svc = get_etl_service()
    if not instance_id:
        inst = svc.create_instance(
            name="auto-exec", description="Auto-created for execution"
        )
        instance_id = inst["id"]

    pipeline_config = {"steps": []}
    if body.pipeline_id:
        preset = get_preset(body.pipeline_id)
        if preset:
            pipeline_config = {"steps": preset["steps"]}

    import uuid

    run_id = f"run_{uuid.uuid4().hex[:12]}"

    engine = PipelineEngine(service=svc)
    from common_lib.modules.rip.rip_etl.steps import register_all_steps

    register_all_steps(engine)

    run = await engine.execute(
        run_id=run_id,
        instance_id=instance_id,
        pipeline_config=pipeline_config,
        content=body.content,
        source_type=body.source_type,
    )
    return run


@router.post("/execute/variant/{variant_id}")
async def execute_variant(variant_id: str, body: ExecutePipelineBody):
    v = get_variant(variant_id)
    if not v:
        raise HTTPException(404, "Variant not found")

    svc = get_etl_service()
    inst = svc.create_instance(
        name=f"variant-{variant_id}",
        description=f"Auto-created for variant {variant_id}",
    )

    import uuid

    run_id = f"run_{uuid.uuid4().hex[:12]}"

    engine = PipelineEngine(service=svc)
    from common_lib.modules.rip.rip_etl.steps import register_all_steps

    register_all_steps(engine)

    run = await engine.execute(
        run_id=run_id,
        instance_id=inst["id"],
        pipeline_config={"steps": v["steps"]},
        content=body.content,
        source_type=body.source_type,
    )
    return run


# ── Compare ───────────────────────────────────────────────────────


@router.post("/compare")
async def compare_variants(body: CompareBody):
    comp = get_comparison_engine()
    result = await comp.compare(
        content=body.content,
        variant_ids=body.variant_ids or None,
        source_type=body.source_type,
    )
    return result
