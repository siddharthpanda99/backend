"""Thin FastAPI router for Workspace, Projects & Environment Management (UDS Module 24)."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.workspace_environment import (
    WorkspaceEnvironmentService,
    WorkspaceCreate, WorkspaceUpdate, WorkspaceOut,
    ProjectCreate, ProjectUpdate, ProjectOut,
    FolderCreate, FolderOut,
    EnvironmentCreate, EnvironmentUpdate, EnvironmentOut,
    VariableCreate, VariableUpdate, VariableOut,
    ConnectionProfileCreate, ConnectionProfileOut,
    SyncHistoryOut,
    PromotionCreate, PromotionUpdate, PromotionOut,
    WorkspaceDashboardOut,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspace, Projects & Environment Management"])
svc = WorkspaceEnvironmentService()


# ── Workspaces ─────────────────────────────────────────────────────────

@router.post("", response_model=WorkspaceOut)
def create_workspace(req: WorkspaceCreate):
    return svc.create_workspace(req)


@router.get("", response_model=List[WorkspaceOut])
def list_workspaces(
    workspace_type: Optional[str] = None,
    owner_id: Optional[str] = None,
    include_archived: bool = False,
    limit: int = 50,
):
    return svc.list_workspaces(workspace_type, owner_id, include_archived, limit)


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str):
    w = svc.get_workspace(workspace_id)
    if not w:
        raise HTTPException(404, "Workspace not found")
    return w


@router.put("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(workspace_id: str, req: WorkspaceUpdate):
    w = svc.update_workspace(workspace_id, req)
    if not w:
        raise HTTPException(404, "Workspace not found")
    return w


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: str):
    if not svc.delete_workspace(workspace_id):
        raise HTTPException(404, "Workspace not found")
    return {"ok": True}


# ── Projects ───────────────────────────────────────────────────────────

@router.post("/projects", response_model=ProjectOut)
def create_project(req: ProjectCreate):
    return svc.create_project(req)


@router.get("/projects", response_model=List[ProjectOut])
def list_projects(
    workspace_id: Optional[str] = None,
    folder_id: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    limit: int = 50,
):
    return svc.list_projects(workspace_id, folder_id, is_favorite, limit)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str):
    p = svc.get_project(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, req: ProjectUpdate):
    p = svc.update_project(project_id, req)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    if not svc.delete_project(project_id):
        raise HTTPException(404, "Project not found")
    return {"ok": True}


# ── Folders ────────────────────────────────────────────────────────────

@router.post("/folders", response_model=FolderOut)
def create_folder(req: FolderCreate):
    return svc.create_folder(req)


@router.get("/folders", response_model=List[FolderOut])
def list_folders(workspace_id: str, parent_folder_id: Optional[str] = None, limit: int = 100):
    return svc.list_folders(workspace_id, parent_folder_id, limit)


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: str):
    if not svc.delete_folder(folder_id):
        raise HTTPException(404, "Folder not found")
    return {"ok": True}


# ── Environments ───────────────────────────────────────────────────────

@router.post("/environments", response_model=EnvironmentOut)
def create_environment(req: EnvironmentCreate):
    return svc.create_environment(req)


@router.get("/environments", response_model=List[EnvironmentOut])
def list_environments(workspace_id: str, limit: int = 50):
    return svc.list_environments(workspace_id, limit)


@router.put("/environments/{env_id}", response_model=EnvironmentOut)
def update_environment(env_id: str, req: EnvironmentUpdate):
    e = svc.update_environment(env_id, req)
    if not e:
        raise HTTPException(404, "Environment not found")
    return e


@router.delete("/environments/{env_id}")
def delete_environment(env_id: str):
    if not svc.delete_environment(env_id):
        raise HTTPException(404, "Environment not found")
    return {"ok": True}


# ── Variables ──────────────────────────────────────────────────────────

@router.post("/variables", response_model=VariableOut)
def create_variable(req: VariableCreate):
    return svc.create_variable(req)


@router.get("/variables", response_model=List[VariableOut])
def list_variables(workspace_id: str, environment_id: Optional[str] = None, limit: int = 100):
    return svc.list_variables(workspace_id, environment_id, limit)


@router.put("/variables/{var_id}", response_model=VariableOut)
def update_variable(var_id: str, req: VariableUpdate):
    v = svc.update_variable(var_id, req)
    if not v:
        raise HTTPException(404, "Variable not found")
    return v


@router.delete("/variables/{var_id}")
def delete_variable(var_id: str):
    if not svc.delete_variable(var_id):
        raise HTTPException(404, "Variable not found")
    return {"ok": True}


# ── Connection Profiles ────────────────────────────────────────────────

@router.post("/connection-profiles", response_model=ConnectionProfileOut)
def create_connection_profile(req: ConnectionProfileCreate):
    return svc.create_connection_profile(req)


@router.get("/connection-profiles", response_model=List[ConnectionProfileOut])
def list_connection_profiles(
    workspace_id: str,
    environment_id: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_connection_profiles(workspace_id, environment_id, limit)


# ── Sync History ───────────────────────────────────────────────────────

@router.get("/sync-history", response_model=List[SyncHistoryOut])
def list_sync_history(
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_sync_history(workspace_id, status, limit)


# ── Promotions ─────────────────────────────────────────────────────────

@router.post("/promotions", response_model=PromotionOut)
def create_promotion(req: PromotionCreate):
    return svc.create_promotion(req)


@router.get("/promotions", response_model=List[PromotionOut])
def list_promotions(
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_promotions(workspace_id, status, limit)


@router.put("/promotions/{promotion_id}", response_model=PromotionOut)
def update_promotion(promotion_id: str, req: PromotionUpdate):
    p = svc.update_promotion(promotion_id, req)
    if not p:
        raise HTTPException(404, "Promotion not found")
    return p


# ── Dashboard ──────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=WorkspaceDashboardOut)
def workspace_dashboard():
    return svc.get_dashboard()
