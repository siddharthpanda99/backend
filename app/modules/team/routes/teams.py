from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.team.schemas import (
    TeamRead,
    TeamCreate,
    TeamUpdate,
    TeamMemberRead,
    TeamMemberUpdate,
    TeamInviteRead,
    TeamInviteCreate,
    WorkspaceUpdate,
)
from common_lib.modules.team.service import (
    team_service,
    team_member_service,
    team_invite_service,
    workspace_service,
)
from common_lib.modules.auth.authorization import PlatformIdentity, log_crud_mutation
from app.modules.auth.dependencies import (
    get_current_identity,
    require_permission,
    require_tenant,
)

router = APIRouter()


# ─── Teams ───────────────────────────────────────────────────


@router.get("/", response_model=List[TeamRead])
def list_teams(
    session: Session = Depends(get_session),
    identity: PlatformIdentity = Depends(get_current_identity),
):
    teams = team_service.list_teams_for_user(session, int(identity.subject_id))
    result = []
    for t in teams:
        members = team_member_service.list_members(session, t.id)
        result.append(
            TeamRead(
                id=t.id,
                name=t.name,
                slug=t.slug,
                description=t.description,
                avatar_url=t.avatar_url,
                owner_id=t.owner_id,
                member_count=len(members),
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )
    return result


@router.post("/", response_model=TeamRead, status_code=201)
def create_team(
    data: TeamCreate,
    session: Session = Depends(get_session),
    identity: PlatformIdentity = Depends(get_current_identity),
):
    team = team_service.create_team(session, data, int(identity.subject_id))
    log_crud_mutation(
        subject_id=identity.subject_id,
        subject_type=identity.subject_type,
        action="team.create",
        resource_id=str(team.id),
        resource_type="team",
        tenant_id=identity.tenant_id,
    )
    return TeamRead(
        id=team.id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        avatar_url=team.avatar_url,
        owner_id=team.owner_id,
        member_count=1,
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.get("/{team_id}", response_model=TeamRead)
def get_team(
    team_id: int,
    session: Session = Depends(get_session),
    identity: PlatformIdentity = Depends(get_current_identity),
):
    team = team_service.get_team(session, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    members = team_member_service.list_members(session, team_id)
    return TeamRead(
        id=team.id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        avatar_url=team.avatar_url,
        owner_id=team.owner_id,
        member_count=len(members),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: int,
    data: TeamUpdate,
    session: Session = Depends(get_session),
    identity: PlatformIdentity = Depends(get_current_identity),
):
    team = team_service.update_team(session, team_id, data)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    members = team_member_service.list_members(session, team_id)
    log_crud_mutation(
        subject_id=identity.subject_id,
        subject_type=identity.subject_type,
        action="team.update",
        resource_id=str(team_id),
        resource_type="team",
        tenant_id=identity.tenant_id,
    )
    return TeamRead(
        id=team.id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        avatar_url=team.avatar_url,
        owner_id=team.owner_id,
        member_count=len(members),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    session: Session = Depends(get_session),
    identity: PlatformIdentity = Depends(get_current_identity),
):
    if not team_service.delete_team(session, team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    log_crud_mutation(
        subject_id=identity.subject_id,
        subject_type=identity.subject_type,
        action="team.delete",
        resource_id=str(team_id),
        resource_type="team",
        tenant_id=identity.tenant_id,
    )
    return {"ok": True}


# ─── Members ─────────────────────────────────────────────────


@router.get("/{team_id}/members", response_model=List[TeamMemberRead])
def list_members(
    team_id: int,
    session: Session = Depends(get_session),
):
    return team_member_service.list_members(session, team_id)


@router.post("/{team_id}/members", response_model=TeamMemberRead, status_code=201)
def add_member(
    team_id: int,
    user_id: int,
    role: str = "member",
    session: Session = Depends(get_session),
):
    member = team_member_service.add_member(session, team_id, user_id, role)
    return TeamMemberRead(
        id=member.id,
        team_id=member.team_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.patch("/{team_id}/members/{user_id}", response_model=TeamMemberRead)
def update_member_role(
    team_id: int,
    user_id: int,
    data: TeamMemberUpdate,
    session: Session = Depends(get_session),
):
    member = team_member_service.update_member_role(session, team_id, user_id, data)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return TeamMemberRead(
        id=member.id,
        team_id=member.team_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete("/{team_id}/members/{user_id}")
def remove_member(
    team_id: int,
    user_id: int,
    session: Session = Depends(get_session),
):
    if not team_member_service.remove_member(session, team_id, user_id):
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}


# ─── Invites ─────────────────────────────────────────────────


@router.post("/{team_id}/invites", response_model=TeamInviteRead, status_code=201)
def create_invite(
    team_id: int,
    data: TeamInviteCreate,
    session: Session = Depends(get_session),
    identity: PlatformIdentity = Depends(get_current_identity),
):
    invite = team_invite_service.create_invite(
        session, team_id, data, int(identity.subject_id)
    )
    return TeamInviteRead(
        id=invite.id,
        team_id=invite.team_id,
        email=invite.email,
        role=invite.role,
        status=invite.status,
        expires_at=invite.expires_at,
        created_by=invite.created_by,
        created_at=invite.created_at,
    )


@router.get("/{team_id}/invites", response_model=List[TeamInviteRead])
def list_invites(
    team_id: int,
    session: Session = Depends(get_session),
):
    invites = team_invite_service.list_invites(session, team_id)
    return [
        TeamInviteRead(
            id=i.id,
            team_id=i.team_id,
            email=i.email,
            role=i.role,
            status=i.status,
            expires_at=i.expires_at,
            created_by=i.created_by,
            created_at=i.created_at,
        )
        for i in invites
    ]


@router.delete("/{team_id}/invites/{invite_id}")
def revoke_invite(
    team_id: int,
    invite_id: int,
    session: Session = Depends(get_session),
):
    if not team_invite_service.revoke_invite(session, team_id, invite_id):
        raise HTTPException(status_code=404, detail="Invite not found")
    return {"ok": True}


# ─── Workspace Settings ──────────────────────────────────────


@router.get("/{team_id}/workspace")
def get_workspace(
    team_id: int,
    session: Session = Depends(get_session),
):
    settings = workspace_service.get_settings(session, team_id)
    if not settings:
        return {"settings_json": "{}"}
    return {"settings_json": settings.settings_json}


@router.patch("/{team_id}/workspace")
def update_workspace(
    team_id: int,
    data: WorkspaceUpdate,
    session: Session = Depends(get_session),
):
    settings = workspace_service.update_settings(session, team_id, data)
    return {"settings_json": settings.settings_json}


# ─── Public invite endpoints ─────────────────────────────────


@router.post("/invites/{token}/accept")
def accept_invite(
    token: str,
    session: Session = Depends(get_session),
):
    return team_invite_service.accept_invite(session, token)


@router.post("/invites/{token}/decline")
def decline_invite(
    token: str,
    session: Session = Depends(get_session),
):
    return team_invite_service.decline_invite(session, token)
