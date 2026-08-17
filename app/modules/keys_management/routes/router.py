import logging
import json
import secrets
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.modules.common.types.index import APIResponse
from common_lib.modules.secrets_manager.keys_management.models import Settings, Model
from common_lib.modules.secrets_manager.keys_management import (
    KeyManagementService,
    ApiKeyCreate,
    ApiKeyUpdate,
    ApiKeyResponse,
    KeyCheckResult,
    UsageStats,
    ProviderUsageSummary,
    UsageTimelinePoint,
    PlatformHealthSummary,
    ErrorRecord,
    ErrorDistribution,
    AnalyticsSummary,
    ModelUsageSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_svc = KeyManagementService()


@router.get("/", response_model=APIResponse)
async def list_keys():
    try:
        keys = _svc.list_keys()
        return APIResponse(
            data=[k.model_dump() for k in keys], message="Keys retrieved"
        )
    except Exception as e:
        logger.error(f"Failed to list keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=APIResponse)
async def create_key(payload: ApiKeyCreate):
    try:
        key = _svc.create_key(payload)
        return APIResponse(data=key.model_dump(), message="Key created")
    except Exception as e:
        logger.error(f"Failed to create key: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{key_id}", response_model=APIResponse)
async def delete_key(key_id: int):
    try:
        success = _svc.delete_key(key_id)
        if not success:
            raise HTTPException(status_code=404, detail="Key not found")
        return APIResponse(data={"success": True}, message="Key deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete key {key_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{key_id}", response_model=APIResponse)
async def toggle_key(key_id: int, payload: Dict[str, Any]):
    try:
        enabled = payload.get("enabled")
        if enabled is None:
            raise HTTPException(status_code=400, detail="enabled field required")
        success = _svc.toggle_key(key_id, enabled)
        if not success:
            raise HTTPException(status_code=404, detail="Key not found")
        return APIResponse(data={"enabled": enabled}, message="Key toggled")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle key {key_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{key_id}", response_model=APIResponse)
async def update_key(key_id: int, payload: ApiKeyUpdate):
    try:
        result = _svc.update_key(key_id, payload)
        if not result:
            raise HTTPException(status_code=404, detail="Key not found")
        return APIResponse(data=result.model_dump(), message="Key updated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update key {key_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/platform/{platform}", response_model=APIResponse)
async def toggle_platform(platform: str, payload: Dict[str, Any]):
    try:
        enabled = payload.get("enabled")
        if enabled is None:
            raise HTTPException(status_code=400, detail="enabled field required")
        updated = _svc.toggle_platform(platform, enabled)
        return APIResponse(
            data={"platform": platform, "enabled": enabled, "updatedKeys": updated},
            message="Platform toggled",
        )
    except Exception as e:
        logger.error(f"Failed to toggle platform {platform}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hub", response_model=APIResponse)
async def get_hub():
    try:
        platforms = _svc.get_platform_health()
        keys = _svc.list_keys()
        return APIResponse(
            data={
                "platforms": [p.model_dump() for p in platforms],
                "keys": [
                    {
                        "id": k.id,
                        "platform": k.provider,
                        "status": k.status,
                        "enabled": k.enabled,
                        "createdAt": k.created_at,
                        "lastCheckedAt": k.last_checked_at,
                        "masked_key": k.masked_key,
                        "label": k.label,
                    }
                    for k in keys
                ],
            },
            message="Keys Hub retrieved",
        )
    except Exception as e:
        logger.error(f"Failed to get Keys Hub: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=APIResponse)
async def get_health():
    try:
        platforms = _svc.get_platform_health()
        keys = _svc.list_keys()
        return APIResponse(
            data={
                "platforms": [p.model_dump() for p in platforms],
                "keys": [
                    {
                        "id": k.id,
                        "platform": k.provider,
                        "status": k.status,
                        "enabled": k.enabled,
                        "createdAt": k.created_at,
                        "lastCheckedAt": k.last_checked_at,
                        "masked_key": k.masked_key,
                        "label": k.label,
                    }
                    for k in keys
                ],
            },
            message="Health retrieved",
        )
    except Exception as e:
        logger.error(f"Failed to get health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/health/check/{key_id}", response_model=APIResponse)
async def check_key(key_id: int):
    try:
        result = _svc.check_key(key_id)
        if not result:
            raise HTTPException(status_code=404, detail="Key not found")
        return APIResponse(data=result.model_dump(), message="Key checked")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check key {key_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/health/check-all", response_model=APIResponse)
async def check_all_keys():
    try:
        results = _svc.check_all_keys()
        return APIResponse(
            data={
                "checked": len(results),
                "results": [r.model_dump() for r in results],
            },
            message="All keys checked",
        )
    except Exception as e:
        logger.error(f"Failed to check all keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/summary", response_model=APIResponse)
async def get_analytics_summary(
    range: str = Query("168", description="Hours to look back"),
):
    try:
        summary = _svc.get_analytics_summary(period_hours=int(range))
        return APIResponse(data=summary.model_dump(), message="Analytics summary")
    except Exception as e:
        logger.error(f"Failed to get analytics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/by-platform", response_model=APIResponse)
async def get_analytics_by_platform(
    range: str = Query("168", description="Hours to look back"),
):
    try:
        stats = _svc.get_provider_usage(period_hours=int(range))
        return APIResponse(
            data=[s.model_dump() for s in stats], message="Platform usage"
        )
    except Exception as e:
        logger.error(f"Failed to get by-platform analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/timeline", response_model=APIResponse)
async def get_analytics_timeline(
    range: str = Query("168", description="Hours to look back"),
    interval: str = Query("day", description="hour or day"),
):
    try:
        bucket = "hour" if interval == "hour" else "day"
        timeline = _svc.get_usage_timeline(period_hours=int(range), bucket=bucket)
        return APIResponse(
            data=[
                {
                    "timestamp": t.timestamp,
                    "requests": t.requests,
                    "successCount": t.requests - t.errors,
                    "failureCount": t.errors,
                }
                for t in timeline
            ],
            message="Timeline",
        )
    except Exception as e:
        logger.error(f"Failed to get timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/by-model", response_model=APIResponse)
async def get_analytics_by_model(
    range: str = Query("168", description="Hours to look back"),
):
    try:
        models = _svc.get_model_usage(period_hours=int(range))
        return APIResponse(data=[m.model_dump() for m in models], message="Model usage")
    except Exception as e:
        logger.error(f"Failed to get by-model analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/error-distribution", response_model=APIResponse)
async def get_error_distribution(
    range: str = Query("168", description="Hours to look back"),
):
    try:
        dist = _svc.get_error_distribution(period_hours=int(range))
        return APIResponse(data=dist.model_dump(), message="Error distribution")
    except Exception as e:
        logger.error(f"Failed to get error distribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/errors", response_model=APIResponse)
async def get_recent_errors(
    range: str = Query("168", description="Hours to look back"),
):
    try:
        errors = _svc.get_errors(period_hours=int(range))
        return APIResponse(
            data=[e.model_dump() for e in errors], message="Recent errors"
        )
    except Exception as e:
        logger.error(f"Failed to get errors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/api-key", response_model=APIResponse)
async def get_unified_api_key():
    try:
        api_key = _svc.get_unified_api_key()
        return APIResponse(
            data={"apiKey": api_key}, message="Unified API key retrieved"
        )
    except Exception as e:
        logger.error(f"Failed to get unified API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/api-key/regenerate", response_model=APIResponse)
async def regenerate_unified_api_key():
    try:
        new_key = _svc.regenerate_unified_api_key()
        return APIResponse(
            data={"apiKey": new_key}, message="Unified API key regenerated"
        )
    except Exception as e:
        logger.error(f"Failed to regenerate unified API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unified", response_model=APIResponse)
async def get_unified_keys():
    try:
        with _svc._session() as db:
            settings_rows = db.exec(
                select(Settings).where(Settings.key_name.like("unified_key:%"))
            ).all()
            keys = []
            for row in settings_rows:
                try:
                    keys.append(json.loads(row.value))
                except Exception:
                    pass
            return APIResponse(data=keys, message="Unified keys retrieved")
    except Exception as e:
        logger.error(f"Failed to retrieve unified keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unified", response_model=APIResponse)
async def create_unified_key(payload: Dict[str, Any]):
    try:
        name = payload.get("name", "Unnamed Unified Key")
        providers = payload.get("providers", [])
        models = payload.get("models", [])
        rpm = payload.get("rpm", 60)
        tpd = payload.get("tpd", 10000)
        guardrails = payload.get("guardrails", False)
        key_id = "sk-un-" + secrets.token_hex(20)
        unified_key_data = {
            "id": key_id,
            "name": name,
            "providers": providers,
            "models": models,
            "rpm": rpm,
            "tpd": tpd,
            "guardrails": guardrails,
            "created_at": datetime.utcnow().isoformat(),
            "status": "healthy",
        }
        with _svc._session() as db:
            setting_row = Settings(
                key_name=f"unified_key:{key_id}", value=json.dumps(unified_key_data)
            )
            db.add(setting_row)
            db.commit()
        return APIResponse(
            data=unified_key_data, message="Unified key created successfully"
        )
    except Exception as e:
        logger.error(f"Failed to create unified key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/unified/{key_id}", response_model=APIResponse)
async def update_unified_key(key_id: str, payload: Dict[str, Any]):
    try:
        with _svc._session() as db:
            setting_row = db.exec(
                select(Settings).where(Settings.key_name == f"unified_key:{key_id}")
            ).first()
            if not setting_row:
                raise HTTPException(status_code=404, detail="Unified key not found")
            existing = json.loads(setting_row.value)
            existing["name"] = payload.get("name", existing["name"])
            existing["providers"] = payload.get("providers", existing["providers"])
            existing["models"] = payload.get("models", existing["models"])
            existing["rpm"] = payload.get("rpm", existing["rpm"])
            existing["tpd"] = payload.get("tpd", existing["tpd"])
            existing["guardrails"] = payload.get("guardrails", existing["guardrails"])
            setting_row.value = json.dumps(existing)
            db.add(setting_row)
            db.commit()
        return APIResponse(data=existing, message="Unified key updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update unified key {key_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unified/{key_id}", response_model=APIResponse)
async def delete_unified_key(key_id: str):
    try:
        with _svc._session() as db:
            setting_row = db.exec(
                select(Settings).where(Settings.key_name == f"unified_key:{key_id}")
            ).first()
            if not setting_row:
                raise HTTPException(status_code=404, detail="Unified key not found")
            db.delete(setting_row)
            db.commit()
        return APIResponse(
            data={"success": True}, message="Unified key deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete unified key {key_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
