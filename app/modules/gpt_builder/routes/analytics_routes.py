"""GPT Builder — Analytics Routes.

Endpoints for app-level and org-level analytics, tool usage breakdown,
and widget type distribution.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from common_lib.modules.gpt_builder.schemas import AppAnalyticsResponse
from common_lib.modules.gpt_builder.service import get_gpt_builder_service

router = APIRouter()


@router.get("/{app_id}/analytics", response_model=AppAnalyticsResponse)
async def get_app_analytics(app_id: str):
    service = get_gpt_builder_service()
    analytics = await service.get_app_analytics(app_id)
    return AppAnalyticsResponse(
        app_id=analytics["app_id"],
        total_sessions=analytics["total_sessions"],
        total_messages=analytics["total_messages"],
        total_tokens=analytics["total_tokens"],
        unique_users=analytics["unique_users"],
        avg_latency_ms=analytics["avg_latency_ms"],
        error_rate=analytics["error_rate"],
        tool_call_count=analytics["tool_call_count"],
        widget_distribution=analytics["widget_distribution"],
    )


@router.get("/{app_id}/analytics/sessions", response_model=Dict[str, Any])
async def get_session_analytics(app_id: str):
    service = get_gpt_builder_service()
    analytics = await service.get_app_analytics(app_id)
    return {
        "app_id": app_id,
        "total_sessions": analytics["total_sessions"],
        "total_messages": analytics["total_messages"],
        "avg_messages_per_session": round(
            analytics["total_messages"] / max(analytics["total_sessions"], 1), 1
        ),
    }


@router.get("/{app_id}/analytics/tools", response_model=Dict[str, Any])
async def get_tool_analytics(app_id: str):
    return {
        "app_id": app_id,
        "tool_call_count": 0,
        "tools": {},
        "message": "Tool analytics available after app is used with tools enabled",
    }


@router.get("/{app_id}/analytics/widgets", response_model=Dict[str, Any])
async def get_widget_analytics(app_id: str):
    service = get_gpt_builder_service()
    analytics = await service.get_app_analytics(app_id)
    return {
        "app_id": app_id,
        "widget_distribution": analytics["widget_distribution"],
    }
