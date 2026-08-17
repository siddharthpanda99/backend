"""Reporting — AI capabilities (SSOT §13, Phases 34-35).

Submodule of the reporting router. Mounted at ``/api/v1/reporting/ai`` —
summaries, insights, chart recommendation, data cleaning, template drafting
and report generation. Inference is routed through the shared LLM proxy port;
deterministic fallbacks apply when no LLM is configured.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/ai", tags=["Reporting — AI"])


def _ai():
    from common_lib.modules.reporting.services.ai_service import AIService

    return AIService()


@router.post("/summarize", summary="AI report summary / executive summary")
def summarize(payload: Dict[str, Any] = Body(default={})):
    try:
        if payload.get("executive"):
            return _ai().executive_summary(payload.get("data"))
        return _ai().summarize(payload.get("data"), prompt=payload.get("prompt", ""))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/insights", summary="AI insights from report data")
def insights(payload: Dict[str, Any] = Body(default={})):
    try:
        return _ai().insights(payload.get("data"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recommend-chart", summary="Recommend a chart type for a data shape")
def recommend_chart(payload: Dict[str, Any] = Body(default={})):
    from common_lib.modules.reporting.core.models import DataShape

    shape = DataShape(
        fields=list(payload.get("fields") or []),
        arrays=list(payload.get("arrays") or []),
        source=payload.get("source") or {},
    )
    return _ai().recommend_chart(shape)


@router.post("/clean-data", summary="AI data cleaning / normalization")
def clean_data(payload: Dict[str, Any] = Body(default={})):
    try:
        return _ai().clean_data(payload.get("data"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/draft-template", summary="Draft a report template from a prompt")
def draft_template(payload: Dict[str, Any] = Body(default={})):
    try:
        return _ai().draft_template(
            payload.get("prompt", ""), payload.get("data") or {}
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generate-report", summary="Draft a full report from data + prompt")
def generate_report(payload: Dict[str, Any] = Body(default={})):
    try:
        return _ai().generate_report(
            payload.get("data") or {}, payload.get("prompt", "")
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
