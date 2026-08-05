"""PM Import/Export Routes — Thin API layer.

Registered at: /api/v1/jira/import-export/
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission

def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)
from common_lib.modules.project_management.import_export.service import ImportExportService
from common_lib.modules.project_management.schemas import (
    CsvImportRequest, CsvValidateResult,
    JsonExportRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/export/json")
def export_json(
    data: JsonExportRequest,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.execute", "*", "import_export"),
):
    """Export project data as JSON."""
    svc = ImportExportService(session)
    try:
        if data.include_all_project_data:
            result = svc.export_project_to_json(
                project_id=data.project_id,
                include_all=True,
            )
        else:
            result = svc.export_issues_to_json(
                project_id=data.project_id,
                status_id=data.status_id,
                sprint_id=data.sprint_id,
                include_comments=data.include_comments,
                include_activity=data.include_activity,
            )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/export/json/issues")
def export_issues_json(
    data: JsonExportRequest,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.execute", "*", "import_export"),
):
    """Export issues as JSON (lightweight, no full project data)."""
    svc = ImportExportService(session)
    try:
        result = svc.export_issues_to_json(
            project_id=data.project_id,
            status_id=data.status_id,
            sprint_id=data.sprint_id,
            include_comments=data.include_comments,
            include_activity=data.include_activity,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/import/csv")
def import_csv(
    data: CsvImportRequest,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.execute", "*", "import_export"),
):
    """Import issues from CSV content."""
    svc = ImportExportService(session)
    try:
        result = svc.import_issues_from_csv(
            project_id=data.project_id,
            csv_content=data.csv_content,
            column_mapping=data.column_mapping,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/csv/validate")
def validate_csv(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.read", "*", "import_export"),
):
    """Validate CSV columns before import."""
    svc = ImportExportService(session)
    csv_content = data.get("csv_content", "")
    column_mapping = data.get("column_mapping")
    result = svc.validate_csv_columns(
        csv_content=csv_content,
        column_mapping=column_mapping,
    )
    return result


@router.get("/reports/project/{project_id}")
def get_project_report(
    project_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.read", "*", "import_export"),
):
    """Generate HTML project report (print-to-PDF)."""
    svc = ImportExportService(session)
    try:
        html = svc.generate_project_report_html(project_id)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, media_type="text/html")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/sprint/{sprint_id}")
def get_sprint_report(
    sprint_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.read", "*", "import_export"),
):
    """Generate HTML sprint report (print-to-PDF)."""
    svc = ImportExportService(session)
    try:
        html = svc.generate_sprint_report_html(sprint_id)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, media_type="text/html")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/issue/{issue_id}")
def get_issue_report(
    issue_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.read", "*", "import_export"),
):
    """Generate HTML issue report (print-to-PDF)."""
    svc = ImportExportService(session)
    try:
        html = svc.generate_issue_report_html(issue_id)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, media_type="text/html")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/backup/export/{workspace_id}")
def export_workspace_backup(
    workspace_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.execute", "*", "import_export"),
):
    """Export a complete workspace backup as JSON."""
    svc = ImportExportService(session)
    try:
        return svc.export_workspace_backup(workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/backup/import")
def import_workspace_backup(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("import_export.execute", "*", "import_export"),
):
    """Import a workspace from a backup JSON dict."""
    svc = ImportExportService(session)
    try:
        return svc.import_workspace_backup(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
