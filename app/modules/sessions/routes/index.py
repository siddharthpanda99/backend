from fastapi import APIRouter
from app.modules.common.types.index import APIResponse
from common_lib.modules.auth.sessions.schemas import SessionResponse
from common_lib.modules.auth.sessions.service import session_service

router = APIRouter()


@router.get("/", response_model=APIResponse[list[SessionResponse]])
def get_sessions():
    sessions = session_service.get_active_sessions("user_12345")
    return APIResponse(data=sessions, message="Active sessions retrieved")


@router.get("/current", response_model=APIResponse[SessionResponse])
def get_current_session():
    session = session_service.get_current_session("dummy_token")
    return APIResponse(data=session, message="Current session retrieved")


@router.delete("/{session_id}", response_model=APIResponse[dict])
def revoke_session(session_id: str):
    result = session_service.revoke_session("user_12345", session_id)
    return APIResponse(data=result, message="Session revoked")


@router.post("/revoke-all", response_model=APIResponse[dict])
def revoke_all_sessions():
    result = session_service.revoke_all_sessions("user_12345")
    return APIResponse(data=result, message="All sessions revoked")
