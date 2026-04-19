# Common Exceptions
from fastapi import HTTPException


class NotFoundError(Exception):
    """Resource not found"""

    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(self.message)


class ConflictError(Exception):
    """Resource conflict"""

    def __init__(self, message: str = "Resource conflict"):
        self.message = message
        super().__init__(self.message)


class ValidationError(Exception):
    """Validation error"""

    def __init__(self, message: str = "Validation error"):
        self.message = message
        super().__init__(self.message)


def not_found_error(message: str) -> HTTPException:
    """Create a 404 HTTPException"""
    return HTTPException(status_code=404, detail=message)


def conflict_error(message: str) -> HTTPException:
    """Create a 409 HTTPException"""
    return HTTPException(status_code=409, detail=message)


def validation_error(message: str) -> HTTPException:
    """Create a 422 HTTPException"""
    return HTTPException(status_code=422, detail=message)
