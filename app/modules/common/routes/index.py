from fastapi import APIRouter
from app.modules.common.types.index import APIResponse

router = APIRouter()

@router.get("/health", response_model=APIResponse, tags=["Common"])
def health_check():
    """
    Health check endpoint to verify service status.
    """
    return APIResponse(
        status="success",
        message="Nexus AI Backend is online",
        data={"service": "Nexus AI Backend", "version": "0.1.0"}
    )

@router.get("/hello-lib", response_model=APIResponse, tags=["Common"])
def hello_lib():
    """
    Demonstrate usage of the external common_lib.
    """
    try:
        from common_lib import hello_from_lib
        message = hello_from_lib()
    except ImportError:
        message = "common_lib not installed. Run 'uv sync' to install it."
        
    return APIResponse(
        status="success",
        message="External Library Check",
        data={"lib_message": message}
    )
