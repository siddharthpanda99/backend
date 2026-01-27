from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.modules.database.service.connection import get_session
from app.modules.common.types.index import APIResponse
from app.modules.auth.types.index import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse,
    ForgotPasswordRequest, ResetPasswordRequest, RefreshTokenRequest,
    ChangePasswordRequest, VerifyEmailRequest, ResendVerificationRequest
)
from app.modules.auth.service.index import auth_service
from app.modules.auth.dependencies.index import get_current_active_user, RoleChecker
from app.modules.users.models.user import User
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter()

@router.post("/access-token", response_model=TokenResponse)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)]
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Used primarily by Swagger UI Authorization.
    """
    # Create a LoginRequest from the form data (mapping username to email)
    login_data = LoginRequest(email=form_data.username, password=form_data.password)
    
    # We use the same service method
    # Note: authenticate_user might raise 401, which is fine.
    token = auth_service.authenticate_user(session, login_data)
    
    # Return standard JSON (not wrapped in APIResponse) for Swagger UI to correctly extract the token
    return token

@router.post("/login", response_model=APIResponse[TokenResponse])
def login(
    data: LoginRequest, 
    session: Annotated[Session, Depends(get_session)]
):
    """
    Authenticate user and return access token.
    """
    print(f"DEBUG: Login attempt for {data.email}")
    token = auth_service.authenticate_user(session, data)
    print("DEBUG: Authentication successful")
    return APIResponse(data=token, message="Login successful")

@router.post("/register", response_model=APIResponse[UserResponse])
def register(
    data: RegisterRequest,
    session: Annotated[Session, Depends(get_session)]
):
    """
    Register a new user account.
    """
    if data.password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
        
    user = auth_service.register_user(session, data)
    return APIResponse(data=user, message="Registration successful")

@router.post("/refresh-token", response_model=APIResponse[TokenResponse])
def refresh_token(
    data: RefreshTokenRequest,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Refresh access token using refresh token.
    Note: Requires auth for now as we haven't implemented logic to refresh without auth or validating refresh token from DB.
    """
    token = auth_service.refresh_access_token(data.refresh_token)
    return APIResponse(data=token, message="Token refreshed")

@router.post("/forgot-password", response_model=APIResponse[dict])
def forgot_password(data: ForgotPasswordRequest):
    """
    Initiate password reset process.
    """
    result = auth_service.forgot_password(data.email)
    return APIResponse(data=result, message="Password reset initiated")

@router.post("/reset-password", response_model=APIResponse[dict])
def reset_password(data: ResetPasswordRequest):
    """
    Complete password reset process.
    """
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
        
    result = auth_service.reset_password(data.token, data.new_password)
    return APIResponse(data=result, message="Password reset complete")

@router.post("/logout", response_model=APIResponse[dict])
def logout(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Logout current user and invalidate token.
    """
    auth_service.logout(str(current_user.id))
    return APIResponse(message="Logged out successfully")

@router.get("/me", response_model=APIResponse[UserResponse])
def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Get profile of currently logged-in user.
    """
    # Convert User model to UserResponse (Pydantic will handle this roughly, but IDs might need str conversion if auto-convert fails, 
    # but configs usually handle it. Let's return the model directly)
    return APIResponse(data=UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        is_active=current_user.is_active
    ))

@router.post("/change-password", response_model=APIResponse[dict])
def change_password(
    data: ChangePasswordRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Change password for the authenticated user.
    """
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
        
    result = auth_service.change_password(session, current_user.id, data.old_password, data.new_password)
    return APIResponse(data=result, message="Password updated")

@router.post("/verify-email", response_model=APIResponse[dict])
def verify_email(data: VerifyEmailRequest):
    """
    Verify user email address using token.
    """
    result = auth_service.verify_email(data.token)
    return APIResponse(data=result, message="Email verified")

@router.post("/resend-verification", response_model=APIResponse[dict])
def resend_verification(data: ResendVerificationRequest):
    """
    Resend email verification link.
    """
    result = auth_service.resend_verification(data.email)
    return APIResponse(data=result, message="Verification sent")

# Example RBAC Route
@router.get("/admin-only", dependencies=[Depends(RoleChecker(["admin"]))])
def admin_only_route():
    return APIResponse(data={"message": "You are an admin!"})
