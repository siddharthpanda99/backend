import logging
import traceback
from typing import Any, Dict, Optional
from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import ValidationError
from common_lib.modules.ai_models.domain.exceptions import ModelNotFoundError
from common_lib.modules.exceptions import ServiceError
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class NexusException(Exception):
    def __init__(
        self,
        message: str,
        code: str = "GENERIC_ERROR",
        module: Optional[str] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.module = module
        self.status_code = status_code
        self.details = details or {}


def _get_module_from_request(url: str) -> str:
    """Extracts module name from URL (e.g., /api/v1/users/ -> Users)"""
    parts = url.split("/")
    if len(parts) > 3:
        return parts[3].capitalize()
    return "Global"


def _build_error_response(
    status_code: int,
    code: str,
    message: str,
    module: str,
    detail: Any = None,
    exc: Exception = None,
    headers: Optional[dict[str, str]] = None,
) -> JSONResponse:
    content = {
        "error": code,
        "message": message,
        "module": module,
        "detail": detail,
    }

    # P2-2: Stack traces only in development — never leak to production clients.
    if exc and get_settings().ENVIRONMENT == "development":
        content["stack_trace"] = traceback.format_exc().splitlines()

    return JSONResponse(status_code=status_code, content=content, headers=headers)

async def nexus_exception_handler(request: Request, exc: NexusException):
    module = exc.module or _get_module_from_request(str(request.url))
    logger.error(
        "NexusException [%s] %s — %s %s",
        exc.code,
        exc.message,
        request.method,
        request.url,
        exc_info=False,  # NexusException is domain-level, not a crash
    )
    return _build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        module=module,
        detail=exc.details,
        exc=exc,
    )


async def model_not_found_exception_handler(request: Request, exc: ModelNotFoundError):
    module = _get_module_from_request(str(request.url))
    logger.warning(
        "ModelNotFound — %s %s: %s",
        request.method,
        request.url,
        exc,
    )
    return _build_error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        code="MODEL_NOT_FOUND",
        message=str(exc),
        module=module,
        detail=None,
        exc=exc,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    module = _get_module_from_request(str(request.url))
    errors = []
    for error in exc.errors():
        err_msg = error.get("msg")
        field = ".".join(str(x) for x in error.get("loc", []))
        errors.append(f"{field}: {err_msg}")

    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Data validation failed",
        module=module,
        detail=errors,
        exc=None,  # Validation errors don't really need stack traces
    )


async def pydantic_exception_handler(request: Request, exc: ValidationError):
    module = _get_module_from_request(str(request.url))
    errors = []
    for error in exc.errors():
        err_msg = error.get("msg")
        field = ".".join(str(x) for x in error.get("loc", []))
        errors.append(f"{field}: {err_msg}")

    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Data validation failed",
        module=module,
        detail=errors,
        exc=None,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    module = _get_module_from_request(str(request.url))
    return _build_error_response(
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        module=module,
        detail=None,
        exc=exc,
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    module = _get_module_from_request(str(request.url))
    error_msg = str(exc)

    code = "DATABASE_ERROR"
    message = "A database error occurred"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    if isinstance(exc, IntegrityError):
        status_code = status.HTTP_400_BAD_REQUEST
        orig_msg = str(exc.orig) if exc.orig else str(exc)

        if "unique constraint" in orig_msg.lower():
            code = "DUPLICATE_RESOURCE"
            message = "This resource already exists."
            if "Key (" in orig_msg:
                try:
                    field = orig_msg.split("Key (")[1].split(")")[0]
                    message = f"{module} with this {field} already exists."
                except Exception:
                    pass
        elif "foreign key constraint" in orig_msg.lower():
            code = "REFERENCE_ERROR"
            message = "Referenced resource does not exist."

    return _build_error_response(
        status_code=status_code,
        code=code,
        message=message,
        module=module,
        detail=str(exc),
        exc=exc,
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Last-resort handler — P2-2: log the full traceback server-side but
    only return a safe message to clients in non-development environments."""
    module = _get_module_from_request(str(request.url))
    tb = traceback.format_exc()

    # Always log the full trace server-side so it appears in the observability pipeline
    logger.error(
        "Unhandled exception [%s] — %s %s\n%s",
        type(exc).__name__,
        request.method,
        request.url,
        tb,
    )

    settings = get_settings()
    if settings.ENVIRONMENT == "development":
        # In dev, expose detail to aid debugging
        message = f"Error: {str(exc)} | Trace: {tb[:500]}"
        detail = str(exc)
    else:
        # P2-2: Do NOT leak internal details / stack traces to production clients
        message = "An internal server error occurred. Please try again later."
        detail = None

    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message=message,
        module=module,
        detail=detail,
        exc=exc,
    )


async def service_error_handler(request: Request, exc: ServiceError):
    """Convert common_lib ServiceError to an HTTP JSON response.

    Registered in main.py to catch ServiceError exceptions raised by
    service-layer code and convert them to consistent HTTP error responses.
    This keeps service code framework-agnostic while maintaining
    proper HTTP semantics in the API layer.
    """
    module = _get_module_from_request(str(request.url))
    headers = getattr(exc, "headers", None) if hasattr(exc, "headers") else None
    logger.error(
        "ServiceError [%s] %s — %s %s",
        exc.code,
        exc.message,
        request.method,
        request.url,
    )
    return _build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        module=module,
        detail=exc.detail,
        exc=exc,
        headers=headers,
    )
