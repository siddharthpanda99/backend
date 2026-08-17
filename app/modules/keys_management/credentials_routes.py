import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.modules.common.types.index import APIResponse
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.security.credentials.models import Credential
from common_lib.modules.security.credentials.service import CredentialsService

logger = logging.getLogger(__name__)

router = APIRouter()

# Schema helper for creation
from pydantic import BaseModel

class CredentialCreate(BaseModel):
    name: str
    type: str
    secret_value: str

class CredentialRead(BaseModel):
    id: int
    name: str
    type: str
    is_active: bool

@router.get("/", response_model=APIResponse)
def list_credentials(
    request: Request,
    session: Session = Depends(get_session)
):
    try:
        # Default user ID to 1 if no identity is present in request state
        user_id = 1
        if hasattr(request.state, "identity") and request.state.identity:
            try:
                user_id = int(request.state.identity.subject_id)
            except (ValueError, TypeError):
                pass
                
        creds = CredentialsService.list_credentials(session, owner_user_id=user_id)
        # Format response
        result = [
            {"id": c.id, "name": c.name, "type": c.type, "is_active": c.is_active}
            for c in creds
        ]
        return APIResponse(data=result, message="Credentials retrieved successfully")
    except Exception as e:
        logger.error(f"Failed to list credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=APIResponse)
def create_credential(
    request: Request,
    payload: CredentialCreate,
    session: Session = Depends(get_session)
):
    try:
        user_id = 1
        if hasattr(request.state, "identity") and request.state.identity:
            try:
                user_id = int(request.state.identity.subject_id)
            except (ValueError, TypeError):
                pass
                
        cred = CredentialsService.create_credential(
            session=session,
            name=payload.name,
            type_=payload.type,
            secret_value=payload.secret_value,
            owner_user_id=user_id
        )
        return APIResponse(
            data={"id": cred.id, "name": cred.name, "type": cred.type},
            message="Credential created successfully"
        )
    except Exception as e:
        logger.error(f"Failed to create credential: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{credential_id}", response_model=APIResponse)
def delete_credential(
    credential_id: int,
    session: Session = Depends(get_session)
):
    try:
        success = CredentialsService.delete_credential(session, credential_id)
        if not success:
            raise HTTPException(status_code=404, detail="Credential not found")
        return APIResponse(data={"success": True}, message="Credential deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))
