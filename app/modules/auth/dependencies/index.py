from fastapi import Depends
from common_lib.modules.users.models import User


async def get_current_active_user():
    raise NotImplementedError("Dependency not implemented")


class RoleChecker:
    def __init__(self, roles):
        self.roles = roles

    def __call__(self):
        raise NotImplementedError("Dependency not implemented")
