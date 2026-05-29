from __future__ import annotations
import json
import time
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from common_lib.modules.proxy_routing import (
    get_proxy_service,
    get_router,
    get_rate_limiter,
    ChatCompletionRequest,
    ChatCompletionResponse,
    FallbackEntry,
    FallbackUpdateItem,
    FallbackTokenUsage,
    ProxyModelCatalog,
)
from common_lib.modules.keys_management.service import KeyManagementService
from common_lib.modules.data_storage.database.connection import get_engine
from sqlmodel import Session, text

logger = logging.getLogger(__name__)

router = APIRouter()
proxy_service = get_proxy_service()
keys_service = KeyManagementService()


class ErrorResponse(BaseModel):
    error: Dict[str, Any]


@router.get("/models")
async def list_proxy_models() -> Dict:
    catalog = proxy_service.get_model_catalog()
    models_list = [
        {
            "id": "auto",
            "object": "model",
            "created": 0,
            "owned_by": "antigravity",
            "name": "Auto (router picks the best available model)",
            "context_window": None,
        }
    ]
    for m in catalog:
        models_list.append(
            {
                "id": m.model_id,
                "object": "model",
                "created": 0,
                "owned_by": m.platform,
                "name": m.display_name,
                "context_window": m.context_window,
            }
        )
    return {"object": "list", "data": models_list}


@router.post("/chat/completions")
async def chat_completion(request: ChatCompletionRequest, req: Request) -> Any:
    auth = req.headers.get("authorization", "").replace("Bearer ", "")
    try:
        unified = keys_service.get_unified_api_key()
        if auth != unified:
            raise HTTPException(status_code=401, detail="Invalid API key")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if request.stream:
        return await _stream_completion(request, auth)
    try:
        result = await proxy_service.chat_completion(request, unified, auth)
        headers = {}
        if result._routed_via:
            headers["X-Routed-Via"] = (
                f"{result._routed_via['platform']}/{result._routed_via['model']}"
            )
        return JSONResponse(content=result.dict(exclude_none=True), headers=headers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=502, detail=f"Provider error: {str(e)}")


async def _stream_completion(
    request: ChatCompletionRequest, auth_key: str
) -> StreamingResponse:
    async def event_stream():
        try:
            async for chunk in proxy_service.stream_chat_completion(
                request, "", auth_key
            ):
                yield f"data: {chunk.json(exclude_none=True)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': {'message': str(e)}})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/fallback", response_model=List[FallbackEntry])
async def get_fallback_chain() -> List[FallbackEntry]:
    return proxy_service.get_fallback_chain()


@router.put("/fallback")
async def update_fallback_chain(items: List[FallbackUpdateItem]) -> Dict:
    proxy_service.update_fallback_chain(items)
    return {"success": True}


@router.post("/fallback/sort/{preset}")
async def sort_fallback(preset: str) -> Dict:
    try:
        proxy_service.sort_fallback_by_preset(preset)
        return {"success": True, "preset": preset}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fallback/token-usage", response_model=FallbackTokenUsage)
async def get_fallback_token_usage() -> FallbackTokenUsage:
    return proxy_service.get_token_usage()


def _get_local_llm_models() -> List[ProxyModelCatalog]:
    try:
        engine = get_engine()
        with Session(engine) as session:
            rows = session.exec(
                text("""
                    SELECT id, name, provider, parameters, repo_id, file_path, is_local
                    FROM ai_models
                    WHERE is_local = true AND status = 'completed'
                      AND provider IN ('vllm', 'huggingface')
                      AND (modality = 'text' OR modality = 'multimodal')
                    ORDER BY id
                """)
            ).all()
            results = []
            for i, r in enumerate(rows):
                params = r.parameters or ""
                results.append(
                    ProxyModelCatalog(
                        id=10000 + i,
                        platform="local",
                        model_id=r.id,
                        display_name=f"{r.name} ({r.provider})",
                        intelligence_rank=50,
                        speed_rank=50,
                        size_label=params,
                        rpm_limit=60,
                        rpd_limit=1000,
                        context_window=32768,
                        enabled=True,
                        key_count=1,
                    )
                )
            return results
    except Exception as e:
        logger.warning(f"Failed to fetch local models: {e}")
        return []


@router.get("/catalog", response_model=List[ProxyModelCatalog])
async def get_model_catalog() -> List[ProxyModelCatalog]:
    api_models = proxy_service.get_model_catalog()
    local_models = _get_local_llm_models()
    return api_models + local_models


@router.get("/rate-limits")
async def get_all_rate_limits() -> List[Dict]:
    rate_limiter = get_rate_limiter()
    states = rate_limiter.get_all_rate_limit_states()
    catalog = proxy_service.get_model_catalog()
    catalog_map = {}
    for m in catalog:
        catalog_map[f"{m.platform}:{m.model_id}"] = m
    result = []
    seen = set()
    for s in states:
        combo = f"{s['platform']}:{s['model_id']}:{s['key_id']}"
        if combo in seen:
            continue
        seen.add(combo)
        cm = catalog_map.get(f"{s['platform']}:{s['model_id']}")
        entry = {
            "modelDbId": cm.model_db_id if cm else s["key_id"],
            "platform": s["platform"],
            "modelId": s["model_id"],
            "displayName": cm.display_name if cm else s["model_id"],
            "rpmLimit": cm.rpm_limit if cm else None,
            "rpdLimit": cm.rpd_limit if cm else None,
            "rpmUsed": s["rpm_used"],
            "rpdUsed": s["rpd_used"],
            "remainingRpm": (cm.rpm_limit - s["rpm_used"])
            if cm and cm.rpm_limit is not None
            else 9999,
            "remainingRpd": (cm.rpd_limit - s["rpd_used"])
            if cm and cm.rpd_limit is not None
            else 9999,
            "cooldownUntil": s["cooldown_until"],
        }
        result.append(entry)
    return result


@router.get("/rate-limits/{platform}/{model_id}/{key_id}")
async def get_rate_limits(platform: str, model_id: str, key_id: int) -> Dict:
    rate_limiter = get_rate_limiter()
    limits = {"rpm": None, "rpd": None, "tpm": None, "tpd": None}
    return rate_limiter.get_rate_limit_status(platform, model_id, key_id, limits)
