"""RIP Routes — Aggregated FastAPI router.

All RIP sub-module route handlers are imported here and mounted.
This replaces the old common_lib/.../rip/routes/ module.
"""

from fastapi import APIRouter

from .search import router as search_router
from .documents import router as documents_router
from .embeddings import router as embeddings_router
from .query import router as query_router
from .graph import router as graph_router
from .memory import router as memory_router
from .rag import router as rag_router
from .evaluation import router as evaluation_router
from .cache import router as cache_router
from .fusion import router as fusion_router
from .reranking import router as reranking_router
from .synthesis import router as synthesis_router
from .index import router as index_router
from .sql_retrieval import router as sql_router
from .multi_hop import router as multi_hop_router
from .raptor import router as raptor_router
from .federated import router as federated_router
from .context import router as context_router
from .colbert import router as colbert_router
from .hallucination import router as hallucination_router
from .manifest import router as manifest_router
from .capabilities import router as capabilities_router
from .experiment import router as experiment_router
from .etl import router as etl_router
from .unified_etl import router as unified_etl_router

router = APIRouter()

router.include_router(search_router)
router.include_router(documents_router)
router.include_router(embeddings_router)
router.include_router(query_router)
router.include_router(graph_router)
router.include_router(memory_router)
router.include_router(rag_router)
router.include_router(evaluation_router)
router.include_router(cache_router)
router.include_router(fusion_router)
router.include_router(reranking_router)
router.include_router(synthesis_router)
router.include_router(index_router)
router.include_router(sql_router)
router.include_router(multi_hop_router)
router.include_router(raptor_router)
router.include_router(federated_router)
router.include_router(context_router)
router.include_router(colbert_router)
router.include_router(hallucination_router)
router.include_router(manifest_router)
router.include_router(capabilities_router)
router.include_router(experiment_router)
router.include_router(etl_router)
router.include_router(unified_etl_router)

__all__ = ["router"]
