from fastapi import APIRouter, Depends, HTTPException, status
from app.modules.common.types.index import APIResponse
from app.modules.auth.types.index import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse,
    ForgotPasswordRequest, ResetPasswordRequest, RefreshTokenRequest,
    ChangePasswordRequest, VerifyEmailRequest, ResendVerificationRequest
)
from app.modules.auth.service.index import auth_service

router = APIRouter()

@router.post("/login", response_model=APIResponse[TokenResponse])
def login(data: LoginRequest):
    """
    Authenticate user and return access token.
    """
    token = auth_service.authenticate_user(data)
    return APIResponse(data=token, message="Login successful")

@router.post("/register", response_model=APIResponse[UserResponse])
def register(data: RegisterRequest):
    """
    Register a new user account.
    """
    user = auth_service.register_user(data)
    return APIResponse(data=user, message="Registration successful")

@router.post("/refresh-token", response_model=APIResponse[TokenResponse])
def refresh_token(data: RefreshTokenRequest):
    """
    Refresh access token using refresh token.
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
    result = auth_service.reset_password(data.token, data.new_password)
    return APIResponse(data=result, message="Password reset complete")

@router.post("/logout", response_model=APIResponse[dict])
def logout():
    """
    Logout current user and invalidate token.
    """
    # In a real impl, we'd extract user_id from token dependency
    auth_service.logout("user_12345")
    return APIResponse(message="Logged out successfully")

@router.get("/me", response_model=APIResponse[UserResponse])
def get_current_user():
    """
    Get profile of currently logged-in user.
    """
    # Mock behavior
    user = auth_service.get_current_user("dummy_token")
    return APIResponse(data=user)

@router.post("/change-password", response_model=APIResponse[dict])
def change_password(data: ChangePasswordRequest):
    """
    Change password for the authenticated user.
    """
    # In real app: get user_id from dependency
    result = auth_service.change_password("user_12345", data.old_password, data.new_password)
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




