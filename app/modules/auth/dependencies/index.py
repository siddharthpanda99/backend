from typing import Annotated, List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlmodel import Session, select
from pydantic import ValidationError

from app.modules.database.service.connection import get_session
from app.core.settings import get_settings
from app.modules.users.models.user import User
from app.modules.auth.types.index import TokenPayload
from app.modules.authorization.models.user_role import UserRole
from app.modules.authorization.models.role import Role

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/access-token")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)]
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # We used "sub" as the username/email in security.py create_access_token? 
    # Let's check security.py. It uses "sub": str(subject). 
    # Usually subject is user_id or email. Let's assume we'll use email or username.
    # Given User model has username and email. Let's try to query by email first or username.
    # In auth service I will use email as subject.
    
    user = session.exec(select(User).where(User.email == token_data.sub)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Annotated[User, Depends(get_current_active_user)]):
        # We need to fetch user roles.
        # Assuming user.roles is populated or we need to join.
        # Since 'roles' is a relationship, accessing it might trigger lazy load if not careful, 
        # but with SQLModel/SQLAlchemy async definitions (or sync session), it should work if session is active.
        # Wait, User model defined roles as: roles: List["Role"] = Relationship(...)
        
        user_role_names = [role.name for role in user.roles]
        
        # Check if user has any of the allowed roles
        has_role = any(role in self.allowed_roles for role in user_role_names)
        
        if not has_role:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return user
