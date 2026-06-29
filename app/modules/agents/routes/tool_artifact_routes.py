"""Tool artifact routes — view and manage archived tool outputs."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.modules.common.types.index import APIResponse
from common_lib.modules.agents.services.tool_artifact_service import ToolArtifactService
from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)

router = APIRouter()


class ToolArtifactRead(BaseModel):
    id: str
    session_id: str
    tool_name: str
    original_size: int
    truncated_preview: str
    content_hash: str | None
    created_at: str | None


@router.get("/", response_model=APIResponse[List[ToolArtifactRead]])
def list_artifacts(
    session_id: str,
    limit: int = 50,
    db: Session = Depends(get_db_session),
):
    svc = ToolArtifactService()
    artifacts = svc.list_artifacts(db, session_id, limit=limit)
    return APIResponse(
        data=[
            ToolArtifactRead(
                id=a.id,
                session_id=a.session_id,
                tool_name=a.tool_name,
                original_size=a.original_size,
                truncated_preview=a.truncated_preview,
                content_hash=a.content_hash,
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
            for a in artifacts
        ],
        message="Retrieved tool artifacts",
    )


@router.get("/{artifact_id}", response_model=APIResponse[ToolArtifactRead])
def get_artifact(
    artifact_id: str,
    db: Session = Depends(get_db_session),
):
    svc = ToolArtifactService()
    artifact = svc.get_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return APIResponse(
        data=ToolArtifactRead(
            id=artifact.id,
            session_id=artifact.session_id,
            tool_name=artifact.tool_name,
            original_size=artifact.original_size,
            truncated_preview=artifact.truncated_preview,
            content_hash=artifact.content_hash,
            created_at=artifact.created_at.isoformat() if artifact.created_at else None,
        ),
        message="Retrieved artifact",
    )


@router.get("/{artifact_id}/preview")
def get_preview(
    artifact_id: str,
    db: Session = Depends(get_db_session),
):
    svc = ToolArtifactService()
    preview = svc.get_preview(db, artifact_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return APIResponse(data={"preview": preview}, message="Retrieved preview")


@router.delete("/{artifact_id}")
def delete_artifact(
    artifact_id: str,
    db: Session = Depends(get_db_session),
):
    svc = ToolArtifactService()
    deleted = svc.delete_artifact(db, artifact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return APIResponse(data={"deleted": True}, message="Artifact deleted")
