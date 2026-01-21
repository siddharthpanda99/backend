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
