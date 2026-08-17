"""Reporting — UFP Forms bridge (SSOT §12, Phase 31).

Submodule of the reporting router. Mounted at ``/api/v1/reporting`` with the
``/forms/*`` endpoints — link a form to a template (GenerationBinding),
handle submissions that fire report generation, list bindings.
"""

from __future__ import annotations

from typing import Any, Dict

import base64

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(tags=["Reporting — Forms"])


def _bridge():
    from common_lib.modules.reporting.services.forms_bridge import FormsBridge

    return FormsBridge()


@router.post("/forms/link", summary="Link a UFP form to a report template")
def link_form(payload: Dict[str, Any] = Body(...)):
    try:
        return _bridge().link_template(
            form_id=payload.get("form_id", ""),
            template_id=payload.get("template_id", ""),
            field_map=payload.get("field_map"),
            output_format=payload.get("format", "pdf"),
            output_formats=payload.get("formats"),
            options=payload.get("options"),
            data_path=payload.get("data_path", "data"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/forms/{form_id}/templates", summary="Templates linked to a form")
def templates_for_form(form_id: str):
    return {"templates": _bridge().templates_for_form(form_id)}


@router.get("/forms/bindings", summary="List GenerationBindings")
def list_bindings(form_id: str = ""):
    return {"bindings": _bridge().list_bindings(form_id=form_id)}


@router.post(
    "/forms/{form_id}/submit", summary="Handle a form submission → generate report"
)
def handle_submission(form_id: str, payload: Dict[str, Any] = Body(default={})):
    try:
        result = _bridge().handle_submission(
            form_id=form_id,
            submission_id=payload.get("submission_id", ""),
            data=payload.get("data"),
            variables=payload.get("variables"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Base64-encode any generation output content before returning to the client.
    if result.get("ok"):
        for item in result.get("results", []):
            generation = item.get("generation") or {}
            for output in generation.get("outputs") or []:
                content = output.get("content")
                if isinstance(content, (bytes, bytearray)):
                    output["content"] = base64.b64encode(bytes(content)).decode()
                    output["encoding"] = "base64"
    return result
