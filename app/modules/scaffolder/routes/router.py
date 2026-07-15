from fastapi import APIRouter, HTTPException

from common_lib.modules.scaffolder.service import ScaffolderService
from common_lib.modules.scaffolder.template_service import ScaffoldTemplateService

router = APIRouter()
_service = ScaffolderService()
_template_svc = ScaffoldTemplateService()


@router.get("/schemas")
async def list_schemas():
    return _service.get_config_schemas()


@router.get("/schemas/{generator}")
async def get_schema(generator: str):
    schema = _service.get_generator_config(generator)
    if not schema:
        raise HTTPException(
            status_code=404, detail=f"Generator '{generator}' not found"
        )
    return schema


@router.get("/presets")
async def list_presets():
    return _service.list_presets()


@router.get("/presets/{generator}")
async def get_generator_presets(generator: str):
    presets = _service.get_generator_presets(generator)
    if not presets:
        raise HTTPException(
            status_code=404, detail=f"Generator '{generator}' not found"
        )
    return presets


@router.post("/dry-run")
async def dry_run(body: dict):
    generator = body.get("generator")
    name = body.get("name")
    options = body.get("options", {})
    if not generator or not name:
        raise HTTPException(status_code=400, detail="generator and name are required")
    return _service.dry_run(generator, name, options)


@router.post("/generate")
async def generate(body: dict):
    generator = body.get("generator")
    name = body.get("name")
    options = body.get("options", {})
    preset = body.get("preset")
    if not generator or not name:
        raise HTTPException(status_code=400, detail="generator and name are required")
    if preset:
        all_presets = _service.get_generator_presets(generator)
        match = next((p for p in all_presets if p["name"] == preset), None)
        if match:
            merged = {**match["defaults"], **options}
            options = merged
    _service.use_workspace()
    files = _service.generate(generator, name, options)
    return {"files": [str(f) for f in files]} if files else {"files": []}


@router.get("/workspace/{collection}")
async def list_entities(collection: str):
    _service.use_workspace()
    return _service.list_workspace_entities(collection)


@router.delete("/workspace/{collection}/{name}")
async def delete_entity(collection: str, name: str):
    _service.use_workspace()
    _service.workspace.remove_entity(collection, name)
    return {"status": "deleted"}


@router.get("/templates")
async def list_templates(generator_type: str | None = None):
    return _template_svc.list_templates(generator_type)


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    tpl = _template_svc.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.post("/templates")
async def create_template(body: dict):
    return _template_svc.create_template(body)


@router.put("/templates/{template_id}")
async def update_template(template_id: str, body: dict):
    tpl = _template_svc.update_template(template_id, body)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    ok = _template_svc.delete_template(template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted"}
