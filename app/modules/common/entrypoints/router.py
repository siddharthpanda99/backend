from fastapi import APIRouter

common_router = APIRouter()

@common_router.get("/health", tags=["Common"])
def health_check():
    """
    Health check endpoint to verify service status.
    """
    return {"status": "ok", "service": "Nexus AI Backend"}
