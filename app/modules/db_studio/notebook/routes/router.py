"""Thin FastAPI router for Notebook & Interactive Workspace (UDS Module 20)."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.notebook import (
    NotebookService, NotebookOut, NotebookCreate, NotebookUpdate,
    CellOut, CellCreate, CellUpdate,
    ExecuteCellRequest, ExecuteCellOut, ExecutionHistoryOut,
    OutputOut, VersionOut,
    TemplateCreate, TemplateOut,
    PublishRequest, PublicationOut,
    NotebookDashboardOut,
)

router = APIRouter(prefix="/api/v1/notebooks", tags=["Notebook & Interactive Workspace"])
svc = NotebookService()


# ── Notebooks ──────────────────────────────────────────────────────────

@router.post("", response_model=NotebookOut)
def create_notebook(req: NotebookCreate):
    return svc.create_notebook(req)


@router.get("", response_model=List[NotebookOut])
def list_notebooks(
    owner_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    language: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 50,
):
    return svc.list_notebooks(owner_id, workspace_id, language, include_archived, limit)


@router.get("/{notebook_id}", response_model=NotebookOut)
def get_notebook(notebook_id: str):
    nb = svc.get_notebook(notebook_id)
    if not nb:
        raise HTTPException(404, "Notebook not found")
    return nb


@router.put("/{notebook_id}", response_model=NotebookOut)
def update_notebook(notebook_id: str, req: NotebookUpdate):
    nb = svc.update_notebook(notebook_id, req)
    if not nb:
        raise HTTPException(404, "Notebook not found")
    return nb


@router.delete("/{notebook_id}")
def delete_notebook(notebook_id: str):
    if not svc.delete_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")
    return {"ok": True}


# ── Cells ──────────────────────────────────────────────────────────────

@router.post("/{notebook_id}/cells", response_model=CellOut)
def create_cell(notebook_id: str, req: CellCreate):
    return svc.create_cell(notebook_id, req)


@router.get("/{notebook_id}/cells", response_model=List[CellOut])
def list_cells(notebook_id: str):
    return svc.list_cells(notebook_id)


@router.get("/cells/{cell_id}", response_model=CellOut)
def get_cell(cell_id: str):
    cell = svc.get_cell(cell_id)
    if not cell:
        raise HTTPException(404, "Cell not found")
    return cell


@router.put("/cells/{cell_id}", response_model=CellOut)
def update_cell(cell_id: str, req: CellUpdate):
    cell = svc.update_cell(cell_id, req)
    if not cell:
        raise HTTPException(404, "Cell not found")
    return cell


@router.delete("/cells/{cell_id}")
def delete_cell(cell_id: str):
    if not svc.delete_cell(cell_id):
        raise HTTPException(404, "Cell not found")
    return {"ok": True}


@router.put("/{notebook_id}/cells/reorder")
def reorder_cells(notebook_id: str, cell_ids: List[str]):
    svc.reorder_cells(notebook_id, cell_ids)
    return {"ok": True}


# ── Execution ──────────────────────────────────────────────────────────

@router.post("/{notebook_id}/cells/{cell_id}/execute", response_model=ExecuteCellOut)
def execute_cell(notebook_id: str, cell_id: str, req: Optional[ExecuteCellRequest] = None):
    return svc.execute_cell(notebook_id, cell_id, req or ExecuteCellRequest())


@router.get("/{notebook_id}/executions", response_model=List[ExecutionHistoryOut])
def list_executions(notebook_id: str, limit: int = 50):
    return svc.list_execution_history(notebook_id=notebook_id, limit=limit)


# ── Outputs ────────────────────────────────────────────────────────────

@router.get("/outputs/{output_id}", response_model=OutputOut)
def get_output(output_id: str):
    out = svc.get_output(output_id)
    if not out:
        raise HTTPException(404, "Output not found")
    return out


# ── Versions ───────────────────────────────────────────────────────────

@router.post("/{notebook_id}/versions", response_model=VersionOut)
def create_version(notebook_id: str, changelog: Optional[str] = None):
    v = svc.create_version(notebook_id, changelog)
    if not v:
        raise HTTPException(404, "Notebook not found")
    return v


@router.get("/{notebook_id}/versions", response_model=List[VersionOut])
def list_versions(notebook_id: str, limit: int = 50):
    return svc.list_versions(notebook_id, limit)


# ── Templates ──────────────────────────────────────────────────────────

@router.post("/templates", response_model=TemplateOut)
def create_template(req: TemplateCreate):
    return svc.create_template(req)


@router.get("/templates", response_model=List[TemplateOut])
def list_templates(category: Optional[str] = None, language: Optional[str] = None, limit: int = 50):
    return svc.list_templates(category, language, limit)


# ── Publishing ─────────────────────────────────────────────────────────

@router.post("/{notebook_id}/publish", response_model=PublicationOut)
def publish_notebook(notebook_id: str, req: PublishRequest):
    pub = svc.publish_notebook(notebook_id, req)
    if not pub:
        raise HTTPException(404, "Notebook not found")
    return pub


@router.get("/{notebook_id}/publications", response_model=List[PublicationOut])
def list_publications(notebook_id: str, status: Optional[str] = None, limit: int = 50):
    return svc.list_publications(notebook_id, status, limit)


# ── Dashboard ──────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=NotebookDashboardOut)
def notebook_dashboard():
    return svc.get_dashboard()
