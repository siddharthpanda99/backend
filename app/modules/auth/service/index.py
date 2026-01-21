from datetime import datetime, timedelta
from app.modules.auth.types.index import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse
)

class AuthService:
    def authenticate_user(self, login_data: LoginRequest) -> TokenResponse:
        # Dummy logic: Always return a success token
        return TokenResponse(
            access_token="dummy_access_token_jwt",
            refresh_token="dummy_refresh_token_jwt",
            expires_in=3600
        )

    def register_user(self, register_data: RegisterRequest) -> UserResponse:
        # Dummy logic: Return a mocked user
        return UserResponse(
            id="user_12345",
            email=register_data.email,
            full_name=register_data.full_name,
            is_active=True
        )

    def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        return TokenResponse(
            access_token="new_dummy_access_token",
            refresh_token="new_dummy_refresh_token",
            expires_in=3600
        )

    def forgot_password(self, email: str) -> dict:
        return {"message": f"Password reset email sent to {email}"}

    def reset_password(self, token: str, new_password: str) -> dict:
        return {"message": "Password has been successfully reset"}
    
    def logout(self, user_id: str) -> dict:
        return {"message": "User logged out successfully"}

    def get_current_user(self, token: str) -> UserResponse:
        # Mock user profile
        return UserResponse(
            id="user_12345",
            email="demo@nexus.ai",
            full_name="Nexus User",
            is_active=True
        )

    def change_password(self, user_id: str, old_pass: str, new_pass: str) -> dict:
        return {"message": "Password changed successfully"}

    def verify_email(self, token: str) -> dict:
        return {"message": "Email verified successfully"}

    def resend_verification(self, email: str) -> dict:
        return {"message": "Verification email sent"}
    


auth_service = AuthService()
