from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from app.modules.common.types.index import APIResponse
from common_lib.modules.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RefreshTokenRequest,
    ChangePasswordRequest,
    VerifyEmailRequest,
    ResendVerificationRequest,
)
from common_lib.modules.auth.service import auth_service
from app.modules.auth.dependencies import get_current_active_user, RoleChecker
from common_lib.modules.users.models import User
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter()


@router.post("/access-token", response_model=TokenResponse)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
):
    from app.core.settings import get_settings

    settings = get_settings()
    login_data = LoginRequest(email=form_data.username, password=form_data.password)
    token = auth_service.authenticate_user(
        session,
        login_data,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
    return token


@router.post("/login", response_model=APIResponse[TokenResponse])
def login(data: LoginRequest, session: Annotated[Session, Depends(get_session)]):
    from app.core.settings import get_settings

    settings = get_settings()
    token = auth_service.authenticate_user(
        session,
        data,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
    return APIResponse(data=token, message="Login successful")


@router.post("/register", response_model=APIResponse[UserResponse])
def register(data: RegisterRequest, session: Annotated[Session, Depends(get_session)]):
    if data.password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user = auth_service.register_user(session, data)
    return APIResponse(data=user, message="Registration successful")


@router.post("/refresh-token", response_model=APIResponse[TokenResponse])
def refresh_token(
    data: RefreshTokenRequest,
    session: Annotated[Session, Depends(get_session)],
):
    from app.core.settings import get_settings

    settings = get_settings()
    token = auth_service.refresh_access_token(
        session,
        data.refresh_token,
        refresh_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
    return APIResponse(data=token, message="Token refreshed")


@router.post("/forgot-password", response_model=APIResponse[dict])
def forgot_password(
    data: ForgotPasswordRequest,
    session: Annotated[Session, Depends(get_session)],
):
    result = auth_service.forgot_password(session, data.email)
    return APIResponse(data=result, message="Password reset initiated")


@router.post("/reset-password", response_model=APIResponse[dict])
def reset_password(
    data: ResetPasswordRequest,
    session: Annotated[Session, Depends(get_session)],
):
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    result = auth_service.reset_password(
        session, data.token, data.new_password
    )
    return APIResponse(data=result, message="Password reset complete")


@router.post("/logout", response_model=APIResponse[dict])
def logout(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    auth_service.logout(session, current_user.id)
    return APIResponse(message="Logged out successfully")


@router.get("/me", response_model=APIResponse[UserResponse])
def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return APIResponse(
        data=UserResponse(
            id=str(current_user.id),
            email=current_user.email,
            username=current_user.username,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
        )
    )


@router.post("/change-password", response_model=APIResponse[dict])
def change_password(
    data: ChangePasswordRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    result = auth_service.change_password(
        session,
        current_user.id,
        data.old_password,
        data.new_password,
    )
    return APIResponse(data=result, message="Password updated")


@router.post("/verify-email", response_model=APIResponse[dict])
def verify_email(
    data: VerifyEmailRequest,
    session: Annotated[Session, Depends(get_session)],
):
    result = auth_service.verify_email(session, data.token)
    return APIResponse(data=result, message="Email verified")


@router.post("/resend-verification", response_model=APIResponse[dict])
def resend_verification(
    data: ResendVerificationRequest,
    session: Annotated[Session, Depends(get_session)],
):
    result = auth_service.resend_verification(session, data.email)
    return APIResponse(data=result, message="Verification sent")


@router.get("/admin-only", dependencies=[Depends(RoleChecker(["admin"]))])
def admin_only_route():
    return APIResponse(data={"message": "You are an admin!"})


# ── Include Submodule Routes ──────────────────────────────────────────

from app.modules.auth.routes.mfa_routes import router as mfa_router
from app.modules.auth.routes.session_routes import router as session_router
from app.modules.auth.routes.lifecycle_routes import router as lifecycle_router
from app.modules.auth.routes.domain_verification_routes import router as domain_router
from app.modules.auth.routes.sso_routes import router as sso_router

router.include_router(mfa_router)
router.include_router(session_router)
router.include_router(lifecycle_router)
router.include_router(domain_router)
router.include_router(sso_router)

