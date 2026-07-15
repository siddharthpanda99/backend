"""Thin FastAPI router for RBAC, Teams & Collaboration (UDS Module 19)."""

from fastapi import APIRouter, HTTPException
from common_lib.modules.db_studio.collaboration import (
    CollaborationService,
    OrganizationCreate, OrganizationOut,
    WorkspaceCreate, WorkspaceOut,
    TeamCreate, TeamOut, TeamMemberOut,
    RoleCreate, RoleOut,
    PermissionOut,
    ResourcePermissionGrant, ResourcePermissionOut,
    CommentCreate, CommentOut,
    ReviewCreate, ReviewUpdate, ReviewOut,
    NotificationOut,
    ActivityLogOut,
    CollaborationDashboardOut,
)

router = APIRouter(prefix="/api/v1/collaboration", tags=["Collaboration"])
svc = CollaborationService()


# ── Organizations ────────────────────────────────────────────────────

@router.post("/organizations", response_model=OrganizationOut)
def create_organization(req: OrganizationCreate):
    return svc.create_organization(req)


@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(limit: int = 50):
    return svc.list_organizations(limit)


# ── Workspaces ───────────────────────────────────────────────────────

@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(req: WorkspaceCreate):
    return svc.create_workspace(req)


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(org_id: str = None, limit: int = 50):
    return svc.list_workspaces(org_id, limit)


# ── Teams ────────────────────────────────────────────────────────────

@router.post("/teams", response_model=TeamOut)
def create_team(req: TeamCreate):
    return svc.create_team(req)


@router.get("/teams", response_model=list[TeamOut])
def list_teams(org_id: str = None, limit: int = 50):
    return svc.list_teams(org_id, limit)


@router.post("/teams/{team_id}/members", response_model=TeamMemberOut)
def add_team_member(team_id: str, user_id: str, role: str = "member"):
    return svc.add_team_member(team_id, user_id, role)


@router.get("/teams/{team_id}/members", response_model=list[TeamMemberOut])
def list_team_members(team_id: str):
    return svc.list_team_members(team_id)


# ── Roles & Permissions ──────────────────────────────────────────────

@router.post("/roles", response_model=RoleOut)
def create_role(req: RoleCreate):
    return svc.create_role(req)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(org_id: str = None, limit: int = 50):
    return svc.list_roles(org_id, limit)


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(resource_type: str = None, limit: int = 100):
    return svc.list_permissions(resource_type, limit)


# ── Resource Permissions / Sharing ───────────────────────────────────

@router.post("/permissions/grant", response_model=ResourcePermissionOut)
def grant_permission(req: ResourcePermissionGrant):
    return svc.grant_permission(req)


@router.get("/permissions/resource", response_model=list[ResourcePermissionOut])
def list_resource_permissions(resource_type: str = None, resource_id: str = None):
    return svc.list_resource_permissions(resource_type, resource_id)


# ── Comments ─────────────────────────────────────────────────────────

@router.post("/comments", response_model=CommentOut)
def create_comment(req: CommentCreate):
    return svc.create_comment(req)


@router.get("/comments", response_model=list[CommentOut])
def list_comments(resource_type: str, resource_id: str, limit: int = 100):
    return svc.list_comments(resource_type, resource_id, limit)


# ── Reviews ──────────────────────────────────────────────────────────

@router.post("/reviews", response_model=ReviewOut)
def create_review(req: ReviewCreate):
    return svc.create_review(req)


@router.get("/reviews", response_model=list[ReviewOut])
def list_reviews(resource_type: str = None, status: str = None, limit: int = 50):
    return svc.list_reviews(resource_type, status, limit)


@router.patch("/reviews/{review_id}", response_model=ReviewOut)
def update_review(review_id: str, req: ReviewUpdate):
    result = svc.update_review(review_id, req)
    if not result:
        raise HTTPException(status_code=404, detail="Review not found")
    return result


# ── Notifications ────────────────────────────────────────────────────

@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(user_id: str = None, is_read: bool = None, limit: int = 50):
    return svc.list_notifications(user_id, is_read, limit)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(notification_id: str):
    result = svc.mark_notification_read(notification_id)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


# ── Activity ─────────────────────────────────────────────────────────

@router.get("/activity", response_model=list[ActivityLogOut])
def list_activity(org_id: str = None, limit: int = 50):
    return svc.list_activity(org_id, limit)


# ── Dashboard ────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=CollaborationDashboardOut)
def get_dashboard():
    return svc.get_dashboard()
