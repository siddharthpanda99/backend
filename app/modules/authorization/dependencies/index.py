from typing import Annotated, List
from fastapi import Depends, HTTPException, status
from sqlmodel import select

from app.modules.auth.dependencies.index import get_current_active_user
from app.modules.users.models.user import User
from app.modules.authorization.models.permission import Permission
from app.modules.authorization.models.role import Role

class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(self, user: Annotated[User, Depends(get_current_active_user)]):
        # Flatten permissions from all user roles
        user_permissions = set()
        for role in user.roles:
            for permission in role.permissions:
                user_permissions.add(permission.name)
        
        if self.required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {self.required_permission}"
            )
        return user
