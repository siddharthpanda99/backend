"""Export routes — generate React, HTML/Tailwind, JSON, and Figma artifacts."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.site_builder.services.export_service import export_service

router = APIRouter()


class FigmaExportRequest(BaseModel):
    figma_token: str
    figma_file_key: str


class ExportResponse(BaseModel):
    success: bool
    data: dict
    message: str


@router.post("/projects/{project_id}/export/json", response_model=ExportResponse)
def export_json(project_id: str, session: Session = Depends(get_db_session)):
    try:
        data = export_service.export_json(session, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ExportResponse(success=True, data=data, message="JSON export generated")


@router.post("/projects/{project_id}/export/react", response_model=ExportResponse)
def export_react(project_id: str, session: Session = Depends(get_db_session)):
    try:
        data = export_service.export_react(session, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ExportResponse(
        success=True,
        data=data,
        message=f"React export generated ({len(data.get('files', []))} files)",
    )


@router.post("/projects/{project_id}/export/html", response_model=ExportResponse)
def export_html(project_id: str, session: Session = Depends(get_db_session)):
    try:
        data = export_service.export_html(session, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ExportResponse(
        success=True,
        data=data,
        message=f"HTML export generated ({len(data.get('files', []))} files)",
    )


@router.post(
    "/projects/{project_id}/export/figma",
    response_model=ExportResponse,
    status_code=501,
)
def export_figma(
    project_id: str, req: FigmaExportRequest, session: Session = Depends(get_db_session)
):
    """Always 501: the Figma export has never been implemented.

    This handler used to catch the service's `ValueError` for a missing
    project, then return HTTP 200 with `success=True` and the message
    "Figma export initiated". The service never contacted Figma at all — it
    echoed back a `figma_url` built from the caller's own `figma_file_key`. A
    client that trusted the status code concluded a design file had been
    created.

    The service now returns `success=False`; this surfaces it as 501 rather
    than swallowing it.
    """
    data = export_service.export_figma(
        session,
        project_id,
        figma_token=req.figma_token,
        figma_file_key=req.figma_file_key,
    )
    if not data.get("success"):
        raise HTTPException(
            status_code=501, detail=data.get("error", "Figma export not implemented")
        )
    return ExportResponse(success=True, data=data, message="Figma export complete")
