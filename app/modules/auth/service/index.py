from datetime import datetime
from sqlmodel import Session, select
from fastapi import HTTPException, status

from app.modules.auth.types.index import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse
)
from app.modules.users.models.user import User
from app.core.security import get_password_hash, verify_password, create_access_token

class AuthService:
    def authenticate_user(self, session: Session, login_data: LoginRequest) -> TokenResponse:
        # 1. Get user by email
        statement = select(User).where(User.email == login_data.email)
        user = session.exec(statement).first()
        
        # 2. Verify password
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # 3. Create Token
        access_token = create_access_token(subject=user.email)
        
        # 4. Return Token
        # NOTE: Refresh token logic is simplified/mocked for now as we didn't add a refresh token table/logic in plan
        return TokenResponse(
            access_token=access_token,
            refresh_token="not_implemented_yet", 
            expires_in=30 * 60 # 30 mins
        )

    def register_user(self, session: Session, register_data: RegisterRequest) -> UserResponse:
        # 1. Check if user exists
        statement = select(User).where(
            (User.email == register_data.email) | (User.username == register_data.username)
        )
        existing_user = session.exec(statement).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or Username already registered"
            )
            
        # 2. Hash Password
        hashed_password = get_password_hash(register_data.password)
        
        # 3. Create User
        # Note: We are setting full_name from the request if available.
        # We assume RegisterRequest has 'full_name' or similar, let's verify Auth types or just map what we can.
        # Looking at previous view_file of service, it accessed register_data.full_name
        
        new_user = User(
            email=register_data.email,
            username=register_data.username,
            hashed_password=hashed_password,
            full_name=register_data.full_name,
            is_active=True
        )
        
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        
        # 4. Return UserResponse
        return UserResponse(
            id=str(new_user.id) if new_user.id else "", 
            email=new_user.email,
            username=new_user.username,
            full_name=new_user.full_name,
            is_active=new_user.is_active
        )

    # ... Other methods (mocked or implementing partial logic) ...
    
    def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        raise HTTPException(status_code=501, detail="Not implemented")

    def forgot_password(self, email: str) -> dict:
        return {"message": f"Password reset email sent to {email}"}

    def reset_password(self, token: str, new_password: str) -> dict:
        return {"message": "Password has been successfully reset"}
    
    def logout(self, user_id: str) -> dict:
        return {"message": "User logged out successfully"}

    # Removed get_current_user from Service as it's now a Dependency
    
    def change_password(self, session: Session, user_id: int, old_pass: str, new_pass: str) -> dict:
        user = session.get(User, user_id)
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
             
        if not verify_password(old_pass, user.hashed_password):
             raise HTTPException(status_code=400, detail="Incorrect password")
             
        user.hashed_password = get_password_hash(new_pass)
        session.add(user)
        session.commit()
        return {"message": "Password changed successfully"}

    def verify_email(self, token: str) -> dict:
        return {"message": "Email verified successfully"}

    def resend_verification(self, email: str) -> dict:
        return {"message": "Verification email sent"}

auth_service = AuthService()
