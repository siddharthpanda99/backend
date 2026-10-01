"""Session endpoints for the authenticated caller.

These used to be a stub: every handler passed a hardcoded ``"user_12345"`` or
``"dummy_token"``. That only ever appeared to work because
``get_current_session`` was fail-open — it returned a synthetic
``SessionResponse(is_current=True)`` for a token that matched no session, so the
placeholder produced a plausible 200 instead of an error.

That fail-open is fixed. Left alone, ``/current`` would now 500, so the placeholders
had to go as well: a hardcoded identity is not a smaller version of real auth, it
is no auth.

Identity comes from ``get_current_active_user``, the platform's existing
dependency, so there is exactly one place that decides what "authenticated" means
rather than a second opinion here.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.modules.auth.dependencies import get_current_active_user
from app.modules.common.types.index import APIResponse
from common_lib.modules.auth.sessions.schemas import SessionResponse
from common_lib.modules.auth.sessions.service import session_service

router = APIRouter()


def _bearer_token(request: Request) -> str:
    """Extract the raw session token from the Authorization header.

    Deliberately returns 401 rather than a placeholder when the header is absent
    or malformed. A caller with no token is unauthenticated; that is a different
    answer from "here is an empty session".
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or not header[7:].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return header[7:].strip()


@router.get("/", response_model=APIResponse[list[SessionResponse]])
def get_sessions(
    user: Annotated[object, Depends(get_current_active_user)],
) -> APIResponse[list[SessionResponse]]:
    """Active sessions for the authenticated user, most recent first."""
    sessions = session_service.get_active_sessions(str(user.id))
    return APIResponse(data=sessions, message="Active sessions retrieved")


@router.get("/current", response_model=APIResponse[SessionResponse])
def get_current_session(
    request: Request,
) -> APIResponse[SessionResponse]:
    """The session for the presented token.

    An unmatched token is 401, not an empty session. Previously this returned
    ``SessionResponse(id="", is_current=True)`` for anything, so a caller that only
    checked ``is_current`` would believe it was authenticated on any garbage.
    """
    token = _bearer_token(request)
    try:
        session = session_service.get_current_session(token)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return APIResponse(data=session, message="Current session retrieved")


@router.delete("/{session_id}", response_model=APIResponse[dict])
def revoke_session(
    session_id: str,
    user: Annotated[object, Depends(get_current_active_user)],
) -> APIResponse[dict]:
    """Revoke one of the authenticated user's own sessions."""
    result = session_service.revoke_session(str(user.id), session_id)
    return APIResponse(data=result, message="Session revoked")
