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


@router.post("/projects/{project_id}/export/figma", response_model=ExportResponse)
def export_figma(
    project_id: str, req: FigmaExportRequest, session: Session = Depends(get_db_session)
):
    try:
        data = export_service.export_figma(
            session,
            project_id,
            figma_token=req.figma_token,
            figma_file_key=req.figma_file_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ExportResponse(success=True, data=data, message="Figma export initiated")
