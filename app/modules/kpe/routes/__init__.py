"""KPE — Aggregated Router.

Collects all KPE sub-routers into a single APIRouter for registration.
All routes are thin wrappers delegating to common_lib.modules.knowledge_engine.kpe.
"""

from fastapi import APIRouter

from app.modules.kpe.routes.documents import router as documents_router
from app.modules.kpe.routes.ingestion import router as ingestion_router
from app.modules.kpe.routes.extraction import router as extraction_router
from app.modules.kpe.routes.classification import router as classification_router
from app.modules.kpe.routes.retrieval import router as retrieval_router
from app.modules.kpe.routes.processing import router as processing_router
from app.modules.kpe.routes.summarization import router as summarization_router
from app.modules.kpe.routes.kg import router as kg_router
from app.modules.kpe.routes.quality import router as quality_router
from app.modules.kpe.routes.embedding import router as embedding_router

router = APIRouter()

router.include_router(documents_router, prefix="/kpe/documents", tags=["KPE — Documents"])
router.include_router(ingestion_router, prefix="/kpe/ingestion", tags=["KPE — Ingestion"])
router.include_router(extraction_router, prefix="/kpe/extraction", tags=["KPE — Extraction"])
router.include_router(classification_router, prefix="/kpe/classification", tags=["KPE — Classification"])
router.include_router(retrieval_router, prefix="/kpe/retrieval", tags=["KPE — Retrieval"])
router.include_router(processing_router, prefix="/kpe/processing", tags=["KPE — Processing"])
router.include_router(summarization_router, prefix="/kpe/summarization", tags=["KPE — Summarization"])
router.include_router(kg_router, prefix="/kpe/kg", tags=["KPE — Knowledge Graph"])
router.include_router(quality_router, prefix="/kpe/quality", tags=["KPE — Quality"])
router.include_router(embedding_router, prefix="/kpe/embedding", tags=["KPE — Embedding"])
