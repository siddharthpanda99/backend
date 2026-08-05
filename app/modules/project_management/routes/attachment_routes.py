"""Attachment Routes — file upload/download/listing endpoints."""

import os
import uuid
import hashlib
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from typing import Optional

from app.modules.auth.dependencies import require_permission

router = APIRouter()


def _get_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# Image MIME types for auto-detection
IMAGE_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/svg+xml", "image/bmp", "image/tiff",
}


def _safe_filename(original: str) -> str:
    """Generate a safe storage filename: uuid + extension."""
    ext = os.path.splitext(original)[1].lower()
    return f"{uuid.uuid4().hex}{ext}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/issues/{issue_id}/attachments", status_code=201)
async def upload_attachment(issue_id: str, file: UploadFile = File(...), uploaded_by: str = "system",
    _perm: None = require_permission("attachment.create", "*", "attachment")):
    """Upload a file attachment to an issue."""
    from common_lib.modules.project_management.attachments.service import AttachmentService

    # Validate file exists
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Size limit: 50 MB
    if file_size > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    # Determine storage path
    storage_dir = "resources/pm_attachments"
    os.makedirs(storage_dir, exist_ok=True)
    safe_name = _safe_filename(file.filename)
    storage_path = os.path.join(storage_dir, safe_name)

    # Write file to temp location first
    tmp_path = storage_path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(content)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {e}")

    # Detect image properties
    mime_type = file.content_type or "application/octet-stream"
    is_image = mime_type in IMAGE_MIME_TYPES
    width = None
    height = None

    if is_image:
        try:
            from PIL import Image
            with Image.open(tmp_path) as img:
                width, height = img.size
        except ImportError:
            pass
        except Exception:
            pass

    # Record in DB first, then atomically rename the file
    try:
        with _get_session() as session:
            svc = AttachmentService(session, upload_dir=storage_dir)
            attachment = svc.record_attachment(
                issue_id=issue_id,
                filename=safe_name,
                original_filename=file.filename,
                storage_path=storage_path,
                mime_type=mime_type,
                file_size=file_size,
                is_image=is_image,
                width=width,
                height=height,
                uploaded_by=uploaded_by,
            )
        # DB succeeded — move temp file to final location
        os.replace(tmp_path, storage_path)
    except Exception:
        # DB failed — clean up the temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


    return {
        "id": attachment.id,
        "filename": safe_name,
        "original_filename": file.filename,
        "mime_type": mime_type,
        "file_size": file_size,
        "is_image": is_image,
        "download_url": f"/api/v1/pm/attachments/{attachment.id}/download",
    }


@router.get("/issues/{issue_id}/attachments")
async def list_attachments(issue_id: str, _perm: None = require_permission("attachment.read", "*", "attachment")):
    """List all attachments for an issue."""
    from common_lib.modules.project_management.attachments.service import AttachmentService
    with _get_session() as session:
        svc = AttachmentService(session)
        attachments = svc.list_attachments(issue_id)
        return {
            "attachments": [
                {
                    "id": a.id,
                    "filename": a.filename,
                    "original_filename": a.original_filename,
                    "mime_type": a.mime_type,
                    "file_size": a.file_size,
                    "is_image": a.is_image,
                    "width": a.width,
                    "height": a.height,
                    "uploaded_by": a.uploaded_by,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "download_url": f"/api/v1/pm/attachments/{a.id}/download",
                }
                for a in attachments
            ],
            "total": len(attachments),
        }


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: str, _perm: None = require_permission("attachment.read", "*", "attachment")):
    """Download an attachment file."""
    from common_lib.modules.project_management.attachments.service import AttachmentService
    with _get_session() as session:
        svc = AttachmentService(session)
        attachment = svc.get_attachment(attachment_id)
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        if not os.path.exists(attachment.storage_path):
            raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=attachment.storage_path,
        filename=attachment.original_filename,
        media_type=attachment.mime_type or "application/octet-stream",
    )


@router.get("/attachments/{attachment_id}")
async def get_attachment_info(attachment_id: str, _perm: None = require_permission("attachment.read", "*", "attachment")):
    """Get attachment metadata."""
    from common_lib.modules.project_management.attachments.service import AttachmentService
    with _get_session() as session:
        svc = AttachmentService(session)
        attachment = svc.get_attachment(attachment_id)
        if not attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        return {
            "id": attachment.id,
            "issue_id": attachment.issue_id,
            "filename": attachment.filename,
            "original_filename": attachment.original_filename,
            "mime_type": attachment.mime_type,
            "file_size": attachment.file_size,
            "is_image": attachment.is_image,
            "width": attachment.width,
            "height": attachment.height,
            "uploaded_by": attachment.uploaded_by,
            "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
            "download_url": f"/api/v1/pm/attachments/{attachment.id}/download",
        }


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: str, _perm: None = require_permission("attachment.delete", "*", "attachment")):
    """Delete an attachment."""
    from common_lib.modules.project_management.attachments.service import AttachmentService
    with _get_session() as session:
        svc = AttachmentService(session)
        success = svc.delete_attachment(attachment_id)
        if not success:
            raise HTTPException(status_code=404, detail="Attachment not found")
        return {"success": True, "attachment_id": attachment_id}
