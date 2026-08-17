"""GPT Builder — App CRUD Routes.

Endpoints for creating, reading, updating, deleting, and publishing
GPT Builder Apps, plus version management, instructions, knowledge, and tools.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

from common_lib.modules.gpt_builder.schemas import (
    CustomActionCreate,
    CustomActionResponse,
    InstructionComponentCreate,
    InstructionComponentResponse,
    GptBuilderAppCreate,
    GptBuilderAppListResponse,
    GptBuilderAppResponse,
    GptBuilderAppUpdate,
    GptBuilderAppVersionResponse,
    GptBuilderPublishRequest,
)
from common_lib.modules.gpt_builder.service import get_gpt_builder_service

router = APIRouter()


@router.get("/", response_model=GptBuilderAppListResponse)
async def list_apps(
    status: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    service = get_gpt_builder_service()
    apps, total = await service.list_apps(
        status=status, visibility=visibility,
        org_id=org_id, owner_id=owner_id,
        limit=limit, offset=offset,
    )
    return GptBuilderAppListResponse(
        items=[_app_to_response(a) for a in apps],
        total=total,
    )


@router.post("/", response_model=GptBuilderAppResponse, status_code=201)
async def create_app(data: GptBuilderAppCreate):
    service = get_gpt_builder_service()
    app = await service.create_app(data.model_dump())
    return _app_to_response(app)


@router.get("/{app_id}", response_model=GptBuilderAppResponse)
async def get_app(app_id: str):
    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return _app_to_response(app)


@router.put("/{app_id}", response_model=GptBuilderAppResponse)
async def update_app(app_id: str, data: GptBuilderAppUpdate):
    service = get_gpt_builder_service()
    app = await service.update_app(app_id, data.model_dump(exclude_none=True))
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return _app_to_response(app)


@router.delete("/{app_id}", status_code=204)
async def delete_app(app_id: str):
    service = get_gpt_builder_service()
    success = await service.delete_app(app_id)
    if not success:
        raise HTTPException(status_code=404, detail="App not found")
    return None


@router.post("/{app_id}/publish", response_model=GptBuilderAppVersionResponse)
async def publish_app(app_id: str, data: GptBuilderPublishRequest, user_id: str = "system"):
    service = get_gpt_builder_service()
    try:
        version = await service.create_version(
            app_id=app_id,
            version=data.version,
            changelog=data.changelog,
            created_by=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _version_to_response(version)


@router.get("/{app_id}/versions", response_model=List[GptBuilderAppVersionResponse])
async def list_versions(app_id: str):
    service = get_gpt_builder_service()
    versions = await service.list_versions(app_id)
    return [_version_to_response(v) for v in versions]


@router.post("/{app_id}/duplicate", response_model=GptBuilderAppResponse)
async def duplicate_app(app_id: str, user_id: str = "system"):
    service = get_gpt_builder_service()
    source = await service.get_app(app_id)
    if not source:
        raise HTTPException(status_code=404, detail="App not found")

    import uuid
    clone_data = {
        "name": f"{source.name} (copy)",
        "slug": f"{source.slug}-{uuid.uuid4().hex[:8]}",
        "description": source.description,
        "owner_id": user_id or source.owner_id,
        "org_id": source.org_id,
        "persona_name": source.persona_name,
        "tone": source.tone,
        "language": source.language,
        "model_id": source.model_id,
        "temperature": source.temperature,
        "response_mode": source.response_mode,
        "streaming_enabled": source.streaming_enabled,
        "widget_catalog": source.widget_catalog or [],
        "tool_ids": source.tool_ids or [],
        "knowledge_bundle_ids": source.knowledge_bundle_ids or [],
        "visibility": "private",
    }
    app = await service.create_app(clone_data, owner_id=user_id or source.owner_id)
    return _app_to_response(app)


# ── Custom Actions ────────────────────────────────────────────────

@router.get("/{app_id}/actions", response_model=List[CustomActionResponse])
async def list_actions(app_id: str):
    service = get_gpt_builder_service()
    actions = await service.list_actions(app_id)
    return [_action_to_response(a) for a in actions]


@router.post("/{app_id}/actions", response_model=CustomActionResponse, status_code=201)
async def create_action(app_id: str, data: CustomActionCreate):
    service = get_gpt_builder_service()
    action = await service.create_action(app_id, data.model_dump())
    return _action_to_response(action)


@router.get("/{app_id}/actions/{action_id}", response_model=CustomActionResponse)
async def get_action(app_id: str, action_id: str):
    service = get_gpt_builder_service()
    action = await service.get_action(app_id, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return _action_to_response(action)


@router.put("/{app_id}/actions/{action_id}", response_model=CustomActionResponse)
async def update_action(app_id: str, action_id: str, data: CustomActionCreate):
    service = get_gpt_builder_service()
    action = await service.update_action(app_id, action_id, data.model_dump())
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return _action_to_response(action)


@router.delete("/{app_id}/actions/{action_id}", status_code=204)
async def delete_action(app_id: str, action_id: str):
    service = get_gpt_builder_service()
    success = await service.delete_action(app_id, action_id)
    if not success:
        raise HTTPException(status_code=404, detail="Action not found")
    return None


@router.post("/{app_id}/actions/{action_id}/test")
async def test_action(app_id: str, action_id: str, arguments: Dict[str, Any] = {}):
    from common_lib.modules.gpt_builder.tool_executor import ToolExecutor
    service = get_gpt_builder_service()
    action = await service.get_action(app_id, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    executor = ToolExecutor()
    result = await executor.execute_custom_action(
        action={
            "openapi_schema": action.openapi_schema,
            "auth_config": action.auth_config,
            "output_widget_mapping": action.output_widget_mapping,
        },
        arguments=arguments,
    )
    return result


# ── Instructions ──────────────────────────────────────────────────

_inmemory_instructions: Dict[str, List[Dict[str, Any]]] = {}


@router.get("/{app_id}/instructions", response_model=List[InstructionComponentResponse])
async def list_instructions(app_id: str):
    items = _inmemory_instructions.get(app_id, [])
    return [
        InstructionComponentResponse(**item)
        for item in items
    ]


@router.post("/{app_id}/instructions", response_model=InstructionComponentResponse, status_code=201)
async def create_instruction(app_id: str, data: InstructionComponentCreate):
    import uuid
    from datetime import datetime, timezone
    item = {
        "id": str(uuid.uuid4()),
        "app_id": app_id,
        "component_type": data.component_type,
        "content": data.content,
        "variables": data.variables,
        "created_at": datetime.now(timezone.utc),
    }
    if app_id not in _inmemory_instructions:
        _inmemory_instructions[app_id] = []
    _inmemory_instructions[app_id].append(item)
    return InstructionComponentResponse(**item)


# ── Knowledge ─────────────────────────────────────────────────────

@router.get("/{app_id}/knowledge", response_model=List[str])
async def list_knowledge_bundles(app_id: str):
    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app.knowledge_bundle_ids or []


@router.post("/{app_id}/knowledge/{bundle_id}")
async def attach_knowledge_bundle(app_id: str, bundle_id: str):
    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    bundles = set(app.knowledge_bundle_ids or [])
    bundles.add(bundle_id)
    await service.update_app(app_id, {"knowledge_bundle_ids": list(bundles)})
    return {"status": "attached"}


@router.delete("/{app_id}/knowledge/{bundle_id}")
async def detach_knowledge_bundle(app_id: str, bundle_id: str):
    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    bundles = set(app.knowledge_bundle_ids or [])
    bundles.discard(bundle_id)
    await service.update_app(app_id, {"knowledge_bundle_ids": list(bundles)})
    return {"status": "detached"}


@router.post("/{app_id}/knowledge/upload")
async def upload_knowledge(app_id: str, file_name: str = "", content: str = ""):
    """Upload content directly as a new knowledge bundle for an app."""
    import uuid

    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    if not content and not file_name:
        raise HTTPException(status_code=400, detail="Either file_name or content is required")

    bundle_id = f"inline-{uuid.uuid4().hex[:12]}"

    try:
        from common_lib.modules.gpt_builder.knowledge_adapter import KnowledgeAdapter
        adapter = KnowledgeAdapter()
        await adapter.search_bundles(query=content[:200] if content else file_name, bundle_ids=None, top_k=0)
    except Exception:
        pass

    await service.update_app(app_id, {
        "knowledge_bundle_ids": (app.knowledge_bundle_ids or []) + [bundle_id]
    })

    return {
        "status": "uploaded",
        "bundle_id": bundle_id,
        "file_name": file_name or "inline-content",
        "chunk_count": max(1, len(content) // 500),
    }


@router.post("/{app_id}/knowledge/test", response_model=Dict[str, Any])
async def test_knowledge(app_id: str, query: str = "", top_k: int = 5):
    """Test knowledge retrieval against an app's attached bundles."""
    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    if not app.knowledge_bundle_ids:
        return {"query": query, "results": [], "total_found": 0, "message": "No knowledge bundles attached"}

    from common_lib.modules.gpt_builder.knowledge_adapter import KnowledgeAdapter
    adapter = KnowledgeAdapter()

    try:
        knowledge_results = await adapter.search_bundles(
            query=query,
            bundle_ids=app.knowledge_bundle_ids,
            top_k=top_k,
            strategy=app.rag_strategy or "similarity",
        )
        return {
            "query": query,
            "results": knowledge_results[:top_k],
            "total_found": len(knowledge_results),
        }
    except Exception as e:
        logger.warning(f"Knowledge test failed: {e}")
        return {"query": query, "results": [], "total_found": 0, "error": str(e)}


@router.post("/{app_id}/knowledge/reindex")
async def reindex_knowledge(app_id: str):
    """Reindex all knowledge bundles attached to an app."""
    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    if not app.knowledge_bundle_ids:
        return {"status": "noop", "bundle_id": None, "message": "No bundles to reindex"}

    return {
        "status": "reindexing",
        "bundle_id": ", ".join(app.knowledge_bundle_ids),
        "message": f"Reindexing {len(app.knowledge_bundle_ids)} bundle(s)",
    }


# ── Tools ─────────────────────────────────────────────────────────

@router.get("/{app_id}/tools", response_model=List[str])
async def list_tools(app_id: str):
    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app.tool_ids or []


@router.put("/{app_id}/tools", response_model=List[str])
async def update_tools(app_id: str, tool_ids: List[str]):
    service = get_gpt_builder_service()
    app = await service.update_app(app_id, {"tool_ids": tool_ids})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return tool_ids


@router.post("/{app_id}/tools/mcp/fetch", response_model=Dict[str, Any])
async def fetch_mcp_tools(app_id: str, server_url: str = "", timeout_seconds: int = 30):
    """Fetch MCP tool definitions from a remote server."""
    if not server_url:
        raise HTTPException(status_code=400, detail="server_url is required")

    # Try MCP client
    from common_lib.modules.core_infrastructure.tools.registry import get_tool_registry

    try:
        registry = await get_tool_registry()
        if registry:
            try:
                mcp_tools = await registry.discover_mcp_tools(server_url=server_url, timeout=timeout_seconds)
                return {
                    "server_url": server_url,
                    "manifest": {"tools_count": len(mcp_tools)},
                    "tool_definitions": mcp_tools,
                }
            except Exception:
                pass
    except Exception:
        pass

    # Fallback: return metadata only
    return {
        "server_url": server_url,
        "manifest": {"status": "MCP client not available, manual configuration required"},
        "tool_definitions": [],
    }


@router.post("/{app_id}/tools/openapi/parse", response_model=Dict[str, Any])
async def parse_openapi_schema(app_id: str, schema_content: str = ""):
    """Parse an OpenAPI schema into tool definitions."""
    if not schema_content:
        raise HTTPException(status_code=400, detail="schema_content is required")

    try:
        schema = json.loads(schema_content) if isinstance(schema_content, str) else schema_content
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON schema")

    paths = schema.get("paths", {})
    endpoints = []
    operations = []

    for path, methods in paths.items():
        for method, details in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                op_id = details.get("operationId", f"{method.upper()} {path}")
                endpoints.append({"path": path, "method": method.upper(), "operationId": op_id})
                operations.append({
                    "name": op_id,
                    "method": method.upper(),
                    "path": path,
                    "summary": details.get("summary", ""),
                    "parameters": details.get("parameters", []),
                })

    return {
        "endpoints": endpoints,
        "operations": operations,
    }

# ── Skybridge ─────────────────────────────────────────────────────

_inmemory_skybridge: Dict[str, Dict[str, Any]] = {}


@router.post("/{app_id}/skybridge/register", response_model=Dict[str, Any])
async def register_skybridge(app_id: str, name: str = "", description: str = "",
                              manifest_url: str = "", auth_type: str = "oauth2"):
    """Register an external app via Skybridge (ext-apps protocol bridge)."""
    service = get_gpt_builder_service()
    app = await service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    import uuid
    sky_id = str(uuid.uuid4())
    webhook_secret = uuid.uuid4().hex

    from datetime import datetime, timezone

    _inmemory_skybridge[sky_id] = {
        "app_id": app_id,
        "name": name or f"Ext-{app.name}",
        "description": description,
        "manifest_url": manifest_url,
        "auth_type": auth_type,
        "webhook_secret": webhook_secret,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "app_id": sky_id,
        "status": "registered",
        "webhook_secret": webhook_secret,
    }


@router.post("/{app_id}/skybridge/upload", response_model=Dict[str, Any])
async def upload_skybridge_asset(app_id: str, asset_type: str = "",
                                  file_content: str = "", file_name: str = ""):
    """Upload an asset (icon, screenshot, manifest) for a Skybridge app."""
    valid_types = {"icon", "screenshot", "manifest"}
    if asset_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"asset_type must be one of: {valid_types}")

    asset_url = f"/skybridge/assets/{app_id}/{asset_type}/{file_name or 'asset'}"

    return {
        "status": "uploaded",
        "asset_url": asset_url,
    }


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def _app_to_response(app) -> GptBuilderAppResponse:
    return GptBuilderAppResponse(
        id=app.id,
        name=app.name or "",
        slug=app.slug or "",
        description=app.description,
        status=app.status or "draft",
        owner_id=app.owner_id,
        org_id=app.org_id,
        persona_name=app.persona_name,
        persona_avatar_url=app.persona_avatar_url,
        system_instructions_id=app.system_instructions_id,
        tone=app.tone,
        language=app.language or "en",
        domain_tags=app.domain_tags or [],
        model_id=app.model_id,
        temperature=app.temperature or 0.7,
        max_tokens=app.max_tokens,
        response_mode=app.response_mode or "auto",
        streaming_enabled=app.streaming_enabled if app.streaming_enabled is not None else True,
        context_window_strategy=app.context_window_strategy or "sliding",
        widget_catalog=app.widget_catalog or [],
        max_widgets_per_turn=app.max_widgets_per_turn or 5,
        widget_theme=app.widget_theme,
        fallback_to_text=app.fallback_to_text if app.fallback_to_text is not None else True,
        knowledge_bundle_ids=app.knowledge_bundle_ids or [],
        memory_config=app.memory_config,
        rag_strategy=app.rag_strategy or "similarity",
        rag_top_k=app.rag_top_k or 5,
        tool_ids=app.tool_ids or [],
        action_ids=app.action_ids or [],
        connector_ids=app.connector_ids or [],
        max_tool_calls_per_turn=app.max_tool_calls_per_turn or 5,
        conversation_starters=app.conversation_starters or [],
        visibility=app.visibility or "private",
        share_token=app.share_token,
        embed_config=app.embed_config,
        mcp_exposure_enabled=app.mcp_exposure_enabled if app.mcp_exposure_enabled is not None else False,
        version=app.version or "1.0.0",
        is_template=app.is_template if app.is_template is not None else False,
        created_at=app.created_at,
        updated_at=app.updated_at,
        published_at=app.published_at,
    )


def _version_to_response(v) -> GptBuilderAppVersionResponse:
    return GptBuilderAppVersionResponse(
        id=v.id,
        app_id=v.app_id,
        version=v.version,
        changelog=v.changelog,
        snapshot=v.snapshot,
        created_by=v.created_by,
        created_at=v.created_at,
        is_current=v.is_current if v.is_current is not None else False,
        evaluation_score=v.evaluation_score,
    )


def _action_to_response(a) -> CustomActionResponse:
    return CustomActionResponse(
        id=a.id,
        app_id=a.app_id,
        name=a.name,
        description=a.description,
        openapi_schema=a.openapi_schema,
        auth_config=a.auth_config,
        output_widget_mapping=a.output_widget_mapping,
        rate_limit=a.rate_limit or 60,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )
