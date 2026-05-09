from fastapi import APIRouter
from .ingestion import router as ingestion_router
from .pipeline import router as pipeline_router
from .kg import router as kg_router
from .storage import router as storage_router
from .rag import router as rag_router
from .embeddings import router as embeddings_router

router = APIRouter()

# Include all DIP sub-modules
router.include_router(ingestion_router)
router.include_router(pipeline_router)
router.include_router(kg_router)
router.include_router(storage_router)
router.include_router(rag_router)
router.include_router(embeddings_router)

__all__ = ["router"]
