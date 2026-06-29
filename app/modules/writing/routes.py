"""
writing/routes.py — API routes for the Writing Studio module.

Thin wrappers only — all logic imported from common_lib.
Endpoints:
    Projects:   POST/GET /projects, GET/PUT/DELETE /projects/{id}, GET /projects/{id}/stats
    Bible:      POST /projects/{id}/bible/entries, GET /projects/{id}/bible/entries,
                GET/PUT/DELETE /projects/{id}/bible/entries/{eid},
                GET /projects/{id}/bible/search, GET /projects/{id}/bible/context
    Tools:      POST /tools (create custom tool), POST /tools/list, POST /tools/generate, POST /tools/generate-content, POST /tools/save
    Instances:  POST /instances, GET /instances, GET/PUT/DELETE /instances/{id}
    Pipeline:   POST /projects/{id}/pipeline/execute, GET /state, GET /history, POST /reset, PUT /config, GET /prompt
    Skills:     POST /projects/{id}/skills/{write,describe,rewrite,brainstorm}
    Drafts:     POST/GET /projects/{id}/drafts, GET/PUT/DELETE /drafts/{id},
                GET /drafts/{id}/versions, GET /drafts/{id}/versions/{vid}, POST /drafts/{id}/restore/{vid}
    History:    GET /projects/{id}/history, POST /history/{id}/favorite, GET /projects/{id}/history/stats
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from common_lib.modules.external_platform.writing_studio.bible import (
    BibleEntry,
    BibleSection,
)
from common_lib.modules.external_platform.writing_studio.database import (
    get_session_direct,
)
from common_lib.modules.external_platform.writing_studio.project_service import (
    WritingProjectService,
)
from common_lib.modules.external_platform.writing_studio.service import BibleService
from common_lib.modules.external_platform.writing_studio.tool_builder import (
    ToolBuilderService,
    ToolDefinition,
    ToolInstance,
    WritingToolType,
    get_tool_builder_service,
)
from common_lib.modules.external_platform.writing_studio.tool_instance_service import (
    ToolInstanceService,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────


def _get_session():
    return get_session_direct()


def _get_project_service() -> WritingProjectService:
    return WritingProjectService(_get_session())


def _get_bible_service() -> BibleService:
    session = _get_session()
    return BibleService(session=session)


def _get_instance_service() -> ToolInstanceService:
    return ToolInstanceService(_get_session())


def _get_tool_service() -> ToolBuilderService:
    return get_tool_builder_service()


def _to_tool_list_item(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "id": tool.id,
        "name": tool.name,
        "tool_type": tool.tool_type.value,
        "description": tool.description,
        "icon": tool.icon or tool.tool_type.icon,
        "field_count": tool.field_count,
        "fields": [f.to_form_field_schema() for f in tool.fields],
        "tags": tool.tags,
        "version": tool.version,
        "is_builtin": tool.id.startswith("builtin_"),
        "generator_id": tool.generator_id,
    }


# ─── Request / Response Schemas ───────────────────────────────────


class ProjectCreateRequest(BaseModel):
    name: str
    project_type: str = "fiction"
    genre: str = ""
    description: str = ""
    target_audience: str = ""
    language: str = "en"
    word_count_target: int = 0


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    project_type: Optional[str] = None
    genre: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    language: Optional[str] = None
    word_count_target: Optional[int] = None
    status: Optional[str] = None


class BibleEntryCreateRequest(BaseModel):
    entry_id: str
    section: str
    title: str = ""
    content: str = ""
    tags: list[str] = []
    importance: float = 0.5
    entry_type: str = "base"
    metadata_json: dict[str, Any] = {}


class BibleEntryUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: Optional[float] = None
    metadata_json: Optional[dict[str, Any]] = None


class ToolListRequest(BaseModel):
    category: Optional[str] = None


class ToolFieldSchema(BaseModel):
    """A single field in a custom tool definition (mirrors FieldDefinition)."""

    id: str
    type: str
    label: str = ""
    placeholder: str = ""
    help_text: str = ""
    default_value: Any = None
    required: bool = False
    options: Optional[List[Dict[str, str]]] = None
    validation: Dict[str, Any] = {}
    order: int = 0


class ToolCreateRequest(BaseModel):
    """Request to create (or update) a custom writing tool definition."""

    tool_id: Optional[str] = None  # omit for new tools; provide to update
    name: str
    tool_type: str = "custom"
    description: str = ""
    icon: str = ""
    tags: List[str] = []
    fields: List[ToolFieldSchema] = []


class ToolGenerateRequest(BaseModel):
    description: str


class ContentGenerateRequest(BaseModel):
    """Request schema for LLM auto-generation of content."""

    tool_id: str
    count: int = 5
    parameters: Optional[Dict[str, Any]] = None
    project_id: Optional[str] = None
    save_as_instances: bool = False


class ToolSaveRequest(BaseModel):
    tool_id: str
    project_id: str
    values: Dict[str, Any]
    tags: Optional[list[str]] = None


class InstanceCreateRequest(BaseModel):
    tool_id: str
    name: str
    project_id: Optional[str] = None
    values: Dict[str, Any] = {}
    tags: list[str] = []


class InstanceUpdateRequest(BaseModel):
    name: Optional[str] = None
    values: Optional[Dict[str, Any]] = None
    tags: Optional[list[str]] = None


# ═══════════════════════════════════════════════════════════════════
# PROJECT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════


@router.post("/projects")
async def create_project(request: ProjectCreateRequest):
    """Create a new writing project."""
    try:
        svc = _get_project_service()
        project = svc.create(
            name=request.name,
            project_type=request.project_type,
            genre=request.genre,
            description=request.description,
            target_audience=request.target_audience,
            language=request.language,
            word_count_target=request.word_count_target,
        )
        return {"success": True, "project": _project_to_dict(project)}
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def list_projects(
    status: Optional[str] = Query("active"),
    project_type: Optional[str] = None,
    genre: Optional[str] = None,
    limit: int = Query(100),
    offset: int = Query(0),
):
    """List writing projects."""
    try:
        svc = _get_project_service()
        projects = svc.list(
            status=status,
            project_type=project_type,
            genre=genre,
            limit=limit,
            offset=offset,
        )
        return {
            "success": True,
            "projects": [_project_to_dict(p) for p in projects],
            "total": len(projects),
        }
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a writing project by ID."""
    try:
        svc = _get_project_service()
        project = svc.get(project_id)
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_id}' not found"
            )
        return {"success": True, "project": _project_to_dict(project)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}")
async def update_project(project_id: str, request: ProjectUpdateRequest):
    """Update a writing project."""
    try:
        svc = _get_project_service()
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        project = svc.update(project_id, **updates)
        if not project:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_id}' not found"
            )
        return {"success": True, "project": _project_to_dict(project)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Soft-delete a writing project."""
    try:
        svc = _get_project_service()
        result = svc.delete(project_id)
        if not result:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_id}' not found"
            )
        return {"success": True, "message": f"Project '{project_id}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/stats")
async def get_project_stats(project_id: str):
    """Get project statistics."""
    try:
        svc = _get_project_service()
        stats = svc.get_stats(project_id)
        if not stats:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_id}' not found"
            )
        return {"success": True, "stats": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# BIBLE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════


@router.post("/projects/{project_id}/bible/entries")
async def add_bible_entry(project_id: str, request: BibleEntryCreateRequest):
    """Add a Bible entry to a project."""
    try:
        svc = _get_bible_service()
        section = BibleSection(request.section)
        entry = BibleEntry(
            id=request.entry_id,
            section=section,
            title=request.title,
            content=request.content,
            tags=request.tags,
            importance=request.importance,
            metadata=request.metadata_json,
        )
        result = svc.add_entry(project_id, entry)
        return {"success": True, "entry_id": result.id}
    except Exception as e:
        logger.error(f"Failed to add Bible entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/bible/entries")
async def list_bible_entries(
    project_id: str,
    section: Optional[str] = None,
    limit: int = Query(100),
    offset: int = Query(0),
):
    """List Bible entries for a project."""
    try:
        svc = _get_bible_service()
        if section:
            sec = BibleSection(section)
            entries = svc.list_section(project_id, sec, limit=limit, offset=offset)
        else:
            bible = svc.get_or_create_bible(project_id)
            entries = list(bible.entries.values())[offset : offset + limit]
        return {
            "success": True,
            "entries": [_entry_to_dict(e) for e in entries],
            "total": len(entries),
        }
    except Exception as e:
        logger.error(f"Failed to list Bible entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/bible/entries/{entry_id}")
async def get_bible_entry(project_id: str, entry_id: str):
    """Get a single Bible entry."""
    try:
        svc = _get_bible_service()
        entry = svc.get_entry(project_id, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found")
        return {"success": True, "entry": _entry_to_dict(entry)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Bible entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/bible/entries/{entry_id}")
async def update_bible_entry(
    project_id: str, entry_id: str, request: BibleEntryUpdateRequest
):
    """Update a Bible entry."""
    try:
        svc = _get_bible_service()
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        entry = svc.update_entry(project_id, entry_id, updates)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found")
        return {"success": True, "entry": _entry_to_dict(entry)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update Bible entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/bible/entries/{entry_id}")
async def delete_bible_entry(project_id: str, entry_id: str):
    """Delete a Bible entry."""
    try:
        svc = _get_bible_service()
        result = svc.delete_entry(project_id, entry_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found")
        return {"success": True, "message": f"Entry '{entry_id}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete Bible entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/bible/search")
async def search_bible(project_id: str, q: str = Query(...)):
    """Search Bible entries by title, content, and tags."""
    try:
        svc = _get_bible_service()
        entries = svc.search(project_id, q)
        return {
            "success": True,
            "entries": [_entry_to_dict(e) for e in entries],
            "total": len(entries),
        }
    except Exception as e:
        logger.error(f"Failed to search Bible: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/bible/context")
async def get_bible_context(
    project_id: str,
    sections: Optional[str] = Query(None, description="Comma-separated section names"),
    max_chars: int = Query(4000),
):
    """Get formatted Bible context for LLM injection."""
    try:
        svc = _get_bible_service()
        section_list = None
        if sections:
            section_list = [BibleSection(s.strip()) for s in sections.split(",")]
        context = svc.get_context(
            project_id, sections=section_list, max_chars=max_chars
        )
        return {"success": True, "context": context, "char_count": len(context)}
    except Exception as e:
        logger.error(f"Failed to get Bible context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# TOOL ENDPOINTS (existing, kept thin)
# ═══════════════════════════════════════════════════════════════════


# ─── Create / Update Custom Tool Definition ────────────────────


@router.post("/tools")
async def create_custom_tool(request: ToolCreateRequest):
    """Create (or update) a custom writing tool definition.

    Accepts a field schema from the form builder and registers it with
    ToolBuilderService so it shows up in the tool library immediately.
    """
    try:
        from common_lib.modules.external_platform.writing_studio.tool_builder import (
            FieldDefinition,
            ToolDefinition,
            WritingToolType,
        )
        import uuid

        svc = _get_tool_service()

        # Resolve tool type
        try:
            tool_type = WritingToolType(request.tool_type)
        except ValueError:
            tool_type = WritingToolType.CUSTOM

        # Build field definitions from the request schema
        fields = [
            FieldDefinition(
                id=f.id,
                type=f.type,
                label=f.label,
                placeholder=f.placeholder,
                help_text=f.help_text,
                default_value=f.default_value,
                required=f.required,
                options=f.options,
                validation=f.validation,
            )
            for f in sorted(request.fields, key=lambda x: x.order)
        ]

        tool_id = request.tool_id or f"custom_{uuid.uuid4().hex[:12]}"

        tool = ToolDefinition(
            id=tool_id,
            name=request.name,
            tool_type=tool_type,
            description=request.description,
            icon=request.icon or tool_type.icon,
            fields=fields,
            tags=request.tags,
        )

        svc.register_tool(tool)

        return {
            "success": True,
            "tool": _to_tool_list_item(tool),
            "message": f"Saved '{tool.name}' with {tool.field_count} fields",
        }
    except Exception as e:
        logger.error(f"Failed to create custom tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/list")
async def list_tools(request: ToolListRequest):
    """List all available writing tool definitions."""
    try:
        svc = _get_tool_service()
        tools = svc.list_tools(category=request.category)
        items = [_to_tool_list_item(t) for t in tools]
        return {"success": True, "tools": items, "total": len(items)}
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generators")
async def list_generators(
    category: Optional[str] = Query(None),
    include_unpublished: bool = Query(False),
):
    """List all generator definitions from DB for LLM auto-generation.

    Returns generators with their field schemas, usable for auto-generating
    N entities via the /tools/generate-content endpoint.
    """
    try:
        from common_lib.modules.external_platform.writing_studio.generator_engine import (
            GeneratorEngine,
        )

        session = _get_session()
        engine = GeneratorEngine(session=session)
        generators = engine.list_generators(
            category=category,
            include_unpublished=include_unpublished,
        )
        items = []
        for gen in generators:
            items.append(
                {
                    "id": gen.id,
                    "name": gen.name,
                    "entity_type": gen.entity_type,
                    "description": gen.description,
                    "icon": gen.icon,
                    "category": gen.category,
                    "parameters": [p.to_form_field_schema() for p in gen.parameters],
                    "output_fields": [
                        {
                            "id": f.id,
                            "label": f.label,
                            "type": f.type,
                            "description": f.description,
                        }
                        for f in gen.output_fields
                    ],
                    "tags": gen.tags,
                    "is_builtin": gen.source == "builtin",
                    "execution_count": 0,
                }
            )
        return {"success": True, "generators": items, "total": len(items)}
    except Exception as e:
        logger.error(f"Failed to list generators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/generate")
async def generate_tool(request: ToolGenerateRequest):
    """Generate a tool definition from a natural language description."""
    try:
        svc = _get_tool_service()
        tool = await svc.generate_tool_from_description(description=request.description)
        if not tool:
            return {
                "success": False,
                "message": "Could not generate a tool from that description.",
            }
        form_schema = svc.render_tool_as_form(tool.id)
        return {
            "success": True,
            "tool": _to_tool_list_item(tool),
            "form_schema": form_schema,
            "message": f"Generated '{tool.name}' with {tool.field_count} fields",
        }
    except Exception as e:
        logger.error(f"Failed to generate tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/generate-content")
async def generate_content(request: ContentGenerateRequest):
    """Generate N content items using a tool's generator via LLM.

    Reads the tool's field schema and uses GeneratorEngine to produce
    N structured items matching the schema.
    """
    try:
        from common_lib.modules.external_platform.writing_studio.generator_engine import (
            GeneratorEngine,
        )

        session = _get_session()
        engine = GeneratorEngine(session=session)

        # Build params for the generator
        params = {
            "count": request.count,
            **(request.parameters or {}),
        }

        result = await engine.execute(
            gen_id=request.tool_id,
            params=params,
            save=True,
        )

        items = result.items if result.success else []
        saved_instances = []

        # Optionally save each generated item as a tool instance
        if request.save_as_instances and items:
            inst_svc = _get_instance_service()
            for i, item in enumerate(items):
                inst = inst_svc.create(
                    tool_id=request.tool_id,
                    project_id=request.project_id or "",
                    name=f"{item.get('title', item.get('name', f'Generated {i + 1}'))}",
                    values=item,
                    tags=["auto-generated"],
                )
                saved_instances.append(_instance_to_dict(inst))

        return {
            "success": result.success,
            "items": items,
            "count": len(items),
            "generator_name": result.generator_name,
            "entity_type": result.entity_type,
            "execution_time_ms": result.execution_time_ms,
            "saved_instances": saved_instances,
        }
    except Exception as e:
        logger.error(f"Failed to generate content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/save")
async def save_tool_instance(request: ToolSaveRequest):
    """Save a filled tool instance (via ToolBuilderService)."""
    try:
        svc = _get_tool_service()
        tool = svc.get_tool(request.tool_id)
        if not tool:
            return {"success": False, "message": f"Tool '{request.tool_id}' not found."}
        instance = svc.create_instance(
            tool_id=request.tool_id,
            project_id=request.project_id,
            values=request.values,
        )
        if not instance:
            return {"success": False, "message": "Failed to create instance."}
        return {
            "success": True,
            "instance_id": instance.id,
            "message": f"Saved '{tool.name}' instance",
        }
    except Exception as e:
        logger.error(f"Failed to save tool instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# TOOL INSTANCE ENDPOINTS (DB-backed)
# ═══════════════════════════════════════════════════════════════════


@router.post("/instances")
async def create_instance(request: InstanceCreateRequest):
    """Create a new tool instance (DB-backed)."""
    try:
        svc = _get_instance_service()
        instance = svc.create(
            tool_id=request.tool_id,
            project_id=request.project_id,
            name=request.name,
            values=request.values,
            tags=request.tags,
        )
        return {"success": True, "instance": _instance_to_dict(instance)}
    except Exception as e:
        logger.error(f"Failed to create instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances")
async def list_instances(
    project_id: Optional[str] = Query(None),
    tool_id: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
):
    """List tool instances, optionally filtered by project and/or tool type."""
    try:
        svc = _get_instance_service()
        if project_id:
            instances = svc.list_by_project(
                project_id, tool_id=tool_id, limit=limit, offset=offset
            )
        else:
            instances = svc.list_all(tool_id=tool_id, limit=limit, offset=offset)
        return {
            "success": True,
            "instances": [_instance_to_dict(i) for i in instances],
            "total": len(instances),
        }
    except Exception as e:
        logger.error(f"Failed to list instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str):
    """Get a tool instance by ID."""
    try:
        svc = _get_instance_service()
        instance = svc.get(instance_id)
        if not instance:
            raise HTTPException(
                status_code=404, detail=f"Instance '{instance_id}' not found"
            )
        return {"success": True, "instance": _instance_to_dict(instance)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/instances/{instance_id}")
async def update_instance(instance_id: str, request: InstanceUpdateRequest):
    """Update a tool instance."""
    try:
        svc = _get_instance_service()
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        instance = svc.update(instance_id, **updates)
        if not instance:
            raise HTTPException(
                status_code=404, detail=f"Instance '{instance_id}' not found"
            )
        return {"success": True, "instance": _instance_to_dict(instance)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str):
    """Delete a tool instance."""
    try:
        svc = _get_instance_service()
        result = svc.delete(instance_id)
        if not result:
            raise HTTPException(
                status_code=404, detail=f"Instance '{instance_id}' not found"
            )
        return {"success": True, "message": f"Instance '{instance_id}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete instance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Serialization helpers ────────────────────────────────────────


def _project_to_dict(project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "project_type": project.project_type,
        "genre": project.genre,
        "target_audience": project.target_audience,
        "language": project.language,
        "word_count_target": project.word_count_target,
        "status": project.status,
        "metadata_json": project.metadata_json,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


def _entry_to_dict(entry) -> dict[str, Any]:
    if hasattr(entry, "model_dump"):
        d = entry.model_dump()
    elif hasattr(entry, "dict"):
        d = entry.dict()
    else:
        d = {
            "id": entry.id,
            "section": entry.section.value
            if hasattr(entry.section, "value")
            else entry.section,
            "title": entry.title,
            "content": entry.content,
            "tags": entry.tags,
            "importance": entry.importance,
            "metadata": entry.metadata,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }

    if "section" in d and hasattr(d["section"], "value"):
        d["section"] = d["section"].value
    return d


def _instance_to_dict(instance) -> dict[str, Any]:
    return {
        "id": instance.id,
        "tool_id": instance.tool_id,
        "project_id": instance.project_id,
        "name": instance.name,
        "values": instance.values,
        "tags": instance.tags,
        "created_at": instance.created_at.isoformat() if instance.created_at else None,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
    }


# ═══════════════════════════════════════════════════════════════════
# PIPELINE ENDPOINTS (DB-backed, LLM-wired)
# ═══════════════════════════════════════════════════════════════════


def _get_pipeline_service():
    from common_lib.modules.external_platform.writing_studio.pipeline_service import (
        PipelineService,
    )

    return PipelineService(session=_get_session())


class PipelineExecuteRequest(BaseModel):
    stage: str
    input_data: Dict[str, Any] = {}


class PipelineConfigRequest(BaseModel):
    config: Dict[str, Any] = {}


@router.post("/projects/{project_id}/pipeline/execute")
async def execute_pipeline_stage(project_id: str, request: PipelineExecuteRequest):
    """Execute a pipeline stage (braindump, synopsis, outline, bible, beats, prose)."""
    try:
        svc = _get_pipeline_service()
        result = svc.execute_stage(project_id, request.stage, request.input_data)
        return result
    except Exception as e:
        logger.error(f"Failed to execute pipeline stage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pipeline/state")
async def get_pipeline_state(project_id: str):
    """Get the current pipeline state for a project."""
    try:
        svc = _get_pipeline_service()
        state = svc.get_state(project_id)
        if state is None:
            return {
                "success": True,
                "state": None,
                "message": "No pipeline state found",
            }
        return {"success": True, "state": state}
    except Exception as e:
        logger.error(f"Failed to get pipeline state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pipeline/history")
async def get_pipeline_history(project_id: str):
    """Get pipeline execution history for a project."""
    try:
        svc = _get_pipeline_service()
        history = svc.get_history(project_id)
        return {"success": True, "history": history, "total": len(history)}
    except Exception as e:
        logger.error(f"Failed to get pipeline history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/pipeline/reset")
async def reset_pipeline(project_id: str):
    """Reset the pipeline for a project to initial state."""
    try:
        svc = _get_pipeline_service()
        result = svc.reset(project_id)
        return {
            "success": result,
            "message": "Pipeline reset" if result else "No pipeline to reset",
        }
    except Exception as e:
        logger.error(f"Failed to reset pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/pipeline/config")
async def update_pipeline_config(project_id: str, request: PipelineConfigRequest):
    """Update the pipeline configuration (word_count_target, chapters, etc.)."""
    try:
        svc = _get_pipeline_service()
        config = svc.update_config(project_id, request.config)
        return {"success": True, "config": config}
    except Exception as e:
        logger.error(f"Failed to update pipeline config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pipeline/prompt")
async def build_pipeline_prompt(project_id: str, stage: Optional[str] = Query(None)):
    """Build a combined prompt for the current or specified stage."""
    try:
        svc = _get_pipeline_service()
        prompt = svc.build_prompt(project_id, stage)
        return {"success": True, "prompt": prompt}
    except Exception as e:
        logger.error(f"Failed to build pipeline prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# SKILLS ENDPOINTS (LLM-wired creative writing skills)
# ═══════════════════════════════════════════════════════════════════


def _get_skills_service():
    from common_lib.modules.external_platform.writing_studio.skills_service import (
        SkillsService,
    )

    return SkillsService(session=_get_session())


class SkillWriteRequest(BaseModel):
    mode: str = "auto"
    preceding_text: str = ""
    steering_instruction: str = ""
    tone: str = ""
    word_count_target: int = 0
    character_focus: str = ""
    genre_hints: List[str] = []


class SkillDescribeRequest(BaseModel):
    text: str
    mode: str = "all_senses"
    intensity: float = 0.5
    character_pov: str = ""
    setting: str = ""


class SkillRewriteRequest(BaseModel):
    text: str
    preset: str = "rephrase"
    custom_instruction: str = ""
    preserve_voice: bool = True
    character_focus: str = ""
    style_guide: str = ""


class SkillBrainstormRequest(BaseModel):
    seed_text: str
    category: str = "plot_points"
    count: int = 10
    custom_instruction: str = ""
    inspiration_ids: List[str] = []


@router.post("/projects/{project_id}/skills/write")
async def skill_write(project_id: str, request: SkillWriteRequest):
    """Execute the Write skill — AI-powered prose continuation."""
    try:
        svc = _get_skills_service()
        result = await svc.write(
            project_id=project_id,
            mode=request.mode,
            preceding_text=request.preceding_text,
            steering_instruction=request.steering_instruction,
            tone=request.tone,
            word_count_target=request.word_count_target,
            character_focus=request.character_focus,
            genre_hints=request.genre_hints,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to execute write skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/skills/describe")
async def skill_describe(project_id: str, request: SkillDescribeRequest):
    """Execute the Describe skill — AI-powered sensory description expansion."""
    try:
        svc = _get_skills_service()
        result = await svc.describe(
            text=request.text,
            mode=request.mode,
            intensity=request.intensity,
            character_pov=request.character_pov,
            setting=request.setting,
            project_id=project_id,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to execute describe skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/skills/rewrite")
async def skill_rewrite(project_id: str, request: SkillRewriteRequest):
    """Execute the Rewrite skill — AI-powered text revision."""
    try:
        svc = _get_skills_service()
        result = await svc.rewrite(
            text=request.text,
            preset=request.preset,
            custom_instruction=request.custom_instruction,
            preserve_voice=request.preserve_voice,
            character_focus=request.character_focus,
            style_guide=request.style_guide,
            project_id=project_id,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to execute rewrite skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/skills/brainstorm")
async def skill_brainstorm(project_id: str, request: SkillBrainstormRequest):
    """Execute the Brainstorm skill — AI-powered ideation."""
    try:
        svc = _get_skills_service()
        result = await svc.brainstorm(
            seed_text=request.seed_text,
            category=request.category,
            count=request.count,
            custom_instruction=request.custom_instruction,
            inspiration_ids=request.inspiration_ids,
            project_id=project_id,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to execute brainstorm skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# DRAFT ENDPOINTS (versioned draft content)
# ═══════════════════════════════════════════════════════════════════


def _get_draft_service():
    from common_lib.modules.external_platform.writing_studio.draft_service import (
        DraftService,
    )

    return DraftService(session=_get_session())


class DraftCreateRequest(BaseModel):
    title: str
    content: str = ""
    entry_id: Optional[str] = None
    status: str = "draft"
    metadata_json: Optional[Dict[str, Any]] = None


class DraftUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    entry_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    change_summary: str = ""


def _draft_to_dict(draft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "project_id": draft.project_id,
        "entry_id": draft.entry_id,
        "title": draft.title,
        "content": draft.content,
        "word_count": draft.word_count,
        "status": draft.status,
        "version_number": draft.version_number,
        "metadata_json": draft.metadata_json,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


def _draft_version_to_dict(v) -> dict[str, Any]:
    return {
        "id": v.id,
        "draft_id": v.draft_id,
        "version_number": v.version_number,
        "content": v.content,
        "word_count": v.word_count,
        "change_summary": v.change_summary,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.post("/projects/{project_id}/drafts")
async def create_draft(project_id: str, request: DraftCreateRequest):
    """Create a new draft (version 1)."""
    try:
        svc = _get_draft_service()
        draft = svc.create(
            project_id=project_id,
            title=request.title,
            content=request.content,
            entry_id=request.entry_id,
            status=request.status,
            metadata_json=request.metadata_json,
        )
        return {"success": True, "draft": _draft_to_dict(draft)}
    except Exception as e:
        logger.error(f"Failed to create draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/drafts")
async def list_drafts(
    project_id: str,
    status: Optional[str] = Query(None),
    entry_id: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
):
    """List drafts for a project."""
    try:
        svc = _get_draft_service()
        drafts = svc.list_by_project(
            project_id, status=status, entry_id=entry_id, limit=limit, offset=offset
        )
        return {
            "success": True,
            "drafts": [_draft_to_dict(d) for d in drafts],
            "total": len(drafts),
        }
    except Exception as e:
        logger.error(f"Failed to list drafts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str):
    """Get a draft by ID."""
    try:
        svc = _get_draft_service()
        draft = svc.get(draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft '{draft_id}' not found")
        return {"success": True, "draft": _draft_to_dict(draft)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, request: DraftUpdateRequest):
    """Update a draft (auto-versions on content change)."""
    try:
        svc = _get_draft_service()
        draft = svc.update(
            draft_id,
            title=request.title,
            content=request.content,
            status=request.status,
            entry_id=request.entry_id,
            metadata_json=request.metadata_json,
            change_summary=request.change_summary,
        )
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft '{draft_id}' not found")
        return {"success": True, "draft": _draft_to_dict(draft)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str):
    """Delete a draft and all its version history."""
    try:
        svc = _get_draft_service()
        result = svc.delete(draft_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Draft '{draft_id}' not found")
        return {"success": True, "message": f"Draft '{draft_id}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts/{draft_id}/versions")
async def list_draft_versions(draft_id: str):
    """List all version snapshots for a draft."""
    try:
        svc = _get_draft_service()
        versions = svc.get_versions(draft_id)
        return {
            "success": True,
            "versions": [_draft_version_to_dict(v) for v in versions],
            "total": len(versions),
        }
    except Exception as e:
        logger.error(f"Failed to list draft versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drafts/{draft_id}/versions/{version_number}")
async def get_draft_version(draft_id: str, version_number: int):
    """Get a specific version snapshot."""
    try:
        svc = _get_draft_service()
        version = svc.get_version(draft_id, version_number)
        if not version:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version_number} not found for draft '{draft_id}'",
            )
        return {"success": True, "version": _draft_version_to_dict(version)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get draft version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts/{draft_id}/restore/{version_number}")
async def restore_draft_version(draft_id: str, version_number: int):
    """Restore a draft to a specific version."""
    try:
        svc = _get_draft_service()
        draft = svc.restore_version(draft_id, version_number)
        if not draft:
            raise HTTPException(
                status_code=404,
                detail=f"Draft '{draft_id}' or version {version_number} not found",
            )
        return {"success": True, "draft": _draft_to_dict(draft)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore draft version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# GENERATION HISTORY ENDPOINTS (LLM call audit trail)
# ═══════════════════════════════════════════════════════════════════


def _get_history_service():
    from common_lib.modules.external_platform.writing_studio.generation_history_service import (
        GenerationHistoryService,
    )

    return GenerationHistoryService(session=_get_session())


def _history_to_dict(entry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "project_id": entry.project_id,
        "source": entry.source,
        "input_text": entry.input_text,
        "output_text": entry.output_text,
        "model_used": entry.model_used,
        "params_json": entry.params_json,
        "execution_time_ms": entry.execution_time_ms,
        "is_favorited": entry.is_favorited,
        "metadata_json": entry.metadata_json,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.get("/projects/{project_id}/history")
async def list_generation_history(
    project_id: str,
    source: Optional[str] = Query(None),
    favorited_only: bool = Query(False),
    limit: int = Query(100),
    offset: int = Query(0),
):
    """List generation history for a project."""
    try:
        svc = _get_history_service()
        entries = svc.list_by_project(
            project_id,
            source=source,
            favorited_only=favorited_only,
            limit=limit,
            offset=offset,
        )
        return {
            "success": True,
            "history": [_history_to_dict(e) for e in entries],
            "total": len(entries),
        }
    except Exception as e:
        logger.error(f"Failed to list generation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/history/search")
async def search_generation_history(
    project_id: str,
    q: str = Query(...),
    limit: int = Query(50),
):
    """Search generation history by input/output text."""
    try:
        svc = _get_history_service()
        entries = svc.search(project_id, q, limit=limit)
        return {
            "success": True,
            "history": [_history_to_dict(e) for e in entries],
            "total": len(entries),
        }
    except Exception as e:
        logger.error(f"Failed to search generation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/{history_id}/favorite")
async def toggle_favorite(history_id: str):
    """Toggle the favorite status of a history entry."""
    try:
        svc = _get_history_service()
        entry = svc.toggle_favorite(history_id)
        if not entry:
            raise HTTPException(
                status_code=404, detail=f"History entry '{history_id}' not found"
            )
        return {"success": True, "entry": _history_to_dict(entry)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle favorite: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/history/stats")
async def get_generation_stats(project_id: str):
    """Get generation statistics for a project."""
    try:
        svc = _get_history_service()
        stats = svc.get_stats(project_id)
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Failed to get generation stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{history_id}")
async def delete_history_entry(history_id: str):
    """Delete a history entry."""
    try:
        svc = _get_history_service()
        result = svc.delete(history_id)
        if not result:
            raise HTTPException(
                status_code=404, detail=f"History entry '{history_id}' not found"
            )
        return {"success": True, "message": f"History entry '{history_id}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete history entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# EXPORT ENDPOINTS (multi-format project export)
# ═══════════════════════════════════════════════════════════════════


from fastapi.responses import Response


def _get_export_service():
    from common_lib.modules.external_platform.writing_studio.export_service import (
        ExportService,
    )

    return ExportService(session=_get_session())


@router.get("/projects/{project_id}/export/{fmt}")
async def export_project(project_id: str, fmt: str):
    """Export a project to the specified format.

    Supported formats: markdown, json, docx, epub, latex, screenplay
    Returns the export content with appropriate Content-Type header.
    """
    try:
        from common_lib.modules.external_platform.writing_studio.export_service import (
            EXPORT_FORMATS,
        )

        if fmt not in EXPORT_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{fmt}'. Choose from: {EXPORT_FORMATS}",
            )
        svc = _get_export_service()
        result = svc.export(project_id, fmt)
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_id}' not found"
            )
        return Response(
            content=result["content"],
            media_type=result["mime_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{result["filename"]}"'
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/export")
async def export_project_json(project_id: str):
    """Export a project as JSON (default format, returns structured data)."""
    try:
        svc = _get_export_service()
        result = svc.export(project_id, "json")
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Project '{project_id}' not found"
            )
        return {"success": True, "data": json.loads(result["content"])}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
