from typing import List, Dict, Any, Optional
from common_lib.modules.orchestration.knowledgebase.service import KnowledgeBaseService, KnowledgeBaseConfig, QueryResult
from common_lib.modules.orchestration.knowledgebase.backends.pgvector import PGVectorStore
from app.modules.database.service.connection import engine, Session
from common_lib.modules.orchestration.knowledgebase.factory import create_embedding_function

class RegistrySearchService:
    def __init__(self):
        self.config = KnowledgeBaseConfig(
            backend_type="pgvector",
            embedding_provider="local", 
            embedding_model="all-MiniLM-L6-v2",
            dimension=384,
            namespace="registry_entities"
        )
        
        def get_session():
            return Session(engine)
            
        self.embedder = create_embedding_function(self.config)
        self.store = PGVectorStore(session_factory=get_session, dimension=self.config.dimension)
        self.kb_service = KnowledgeBaseService(
            config=self.config, 
            vector_store=self.store, 
            embedding_function=self.embedder
        )

    async def search(self, query: str, entity_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        filters = {}
        if entity_type and entity_type != "all":
            filters["entity_type"] = entity_type
            
        results = self.kb_service.search(query, limit=limit, filters=filters)
        
        # Format results nicely for API
        formatted = []
        for r in results:
            # Safely extract from metadata or fallback to QueryResult fields
            doc_id = r.metadata.get("id") or r.document_id
            name = r.metadata.get("name") or r.metadata.get("title") or "Unnamed Entity"
            desc = r.metadata.get("description") or ""
            
            formatted.append({
                "id": doc_id,
                "name": name,
                "content": r.content,
                "entity_type": r.metadata.get("entity_type") or "prompt",
                "description": desc,
                "score": 1.0 - r.score if hasattr(r, 'score') else 1.0
            })
        return formatted

_search_service = None

def get_search_service():
    global _search_service
    if _search_service is None:
        _search_service = RegistrySearchService()
    return _search_service
