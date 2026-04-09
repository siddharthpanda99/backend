from typing import List, Dict, Any, Optional
import asyncio
import logging
from common_lib.modules.orchestration.knowledgebase.service import (
    KnowledgeBaseService,
    KnowledgeBaseConfig,
    QueryResult,
)
from common_lib.modules.orchestration.knowledgebase.backends.pgvector import (
    PGVectorStore,
    KBEmbedding,
)
from common_lib.modules.orchestration.knowledgebase.factory import (
    create_embedding_function,
)
from common_lib.modules.orchestration.knowledgebase.contracts.types import Document
from app.core.common_lib_integration import common_memory
import hashlib

logger = logging.getLogger(__name__)


class SyncProgressTracker:
    """Singleton to track background indexing progress."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SyncProgressTracker, cls).__new__(cls)
            cls._instance.current = 0
            cls._instance.total = 0
            cls._instance.status = "idle"  # idle, importing, indexing, completed, error
            cls._instance.description = ""
            cls._instance.last_update = 0
        return cls._instance

    def update(self, current: int, total: int, status: str, description: str = ""):
        self.current = current
        self.total = total
        self.status = status
        self.description = description

    def reset(self):
        self.current = 0
        self.total = 0
        self.status = "idle"
        self.description = ""


class RegistrySearchService:
    def __init__(self, session_factory: Optional[Any] = None):
        import app.core.common_lib_integration as cli

        self.config = KnowledgeBaseConfig(
            backend_type="pgvector",
            embedding_provider="local",
            embedding_model="all-MiniLM-L6-v2",
            dimension=384,
            namespace="registry_entities",
        )
        self.tracker = SyncProgressTracker()
        self.session_factory = session_factory or cli.common_memory._get_session

        self.embedder = create_embedding_function(self.config)
        self.store = PGVectorStore(
            session_factory=self.session_factory, dimension=self.config.dimension
        )
        self.kb_service = KnowledgeBaseService(
            config=self.config,
            vector_store=self.store,
            embedding_function=self.embedder,
        )

    async def search(
        self, query: str, entity_type: str = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        # Coldboot check: if the store is empty, trigger indexing once in background
        # (This is handled by the route, but safe here too)

        filters = {}
        if entity_type and entity_type != "all" and entity_type != "none":
            filters["entity_type"] = entity_type

        # results = self.kb_service.search(query, limit=limit, filters=filters)
        # Note: kb_service.search is synchronous currently based on viewed code
        results = self.kb_service.search(query, limit=limit, filters=filters)

        # Format results nicely for API
        formatted = []
        for r in results:
            doc_id = r.metadata.get("id") or r.document_id
            name = r.metadata.get("name") or r.metadata.get("title") or "Unnamed Entity"
            desc = r.metadata.get("description") or ""

            formatted.append(
                {
                    "id": doc_id,
                    "name": name,
                    "content": r.content,
                    "entity_type": r.metadata.get("entity_type") or "tool",
                    "description": desc,
                    "score": 1.0 - r.score if hasattr(r, "score") else 1.0,
                }
            )
        return formatted

    def reindex_all(self, registry_svc: Optional[Any] = None, force: bool = False):
        """
        Full background re-indexing of all registry entities.
        Scans tools, skills, and agents and embeds them.
        """
        try:
            self.tracker.update(0, 1, "indexing", "Preparing entity list...")

            entities = []

            # 1. Gather Tools
            if registry_svc:
                tools = registry_svc.get_all_tools_flat()
                for t in tools:
                    # Build rich content for semantic search - include both short and long descriptions
                    tool_desc = t.get("description", "")
                    long_desc = t.get("long_description", "")
                    category = t.get("category", "")

                    # Combine all descriptive text for better semantic matching
                    full_content = f"Tool: {t['name']}. {tool_desc}"
                    if long_desc:
                        full_content += f" {long_desc}"
                    full_content += f" Category: {category}."

                    entities.append(
                        {
                            "id": t["id"],
                            "name": t["name"],
                            "description": tool_desc,
                            "type": "tool",
                            "content": full_content,
                        }
                    )

            # 2. Gather Skills
            try:
                skills = common_memory.list_skill_definitions()
                for s in skills:
                    entities.append(
                        {
                            "id": s["id"],
                            "name": s.get("name", s["id"]),
                            "description": s.get("description", ""),
                            "type": "skill",
                            "content": f"Skill: {s.get('name', s['id'])}. {s.get('description', '')}.",
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch skills for indexing: {e}")

            # 3. Gather Agents
            try:
                agents = common_memory.list_agent_definitions()
                for a in agents:
                    entities.append(
                        {
                            "id": a["id"],
                            "name": a.get("name", a["id"]),
                            "description": a.get("description", ""),
                            "type": "agent",
                            "content": f"Agent: {a.get('name', a['id'])}. {a.get('description', '')}.",
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch agents for indexing: {e}")

            total = len(entities)
            self.tracker.update(
                0,
                total,
                "indexing",
                f"Discovered {total} entities. Starting embedding...",
            )

            def get_content_hash(text: str) -> str:
                return hashlib.sha256(text.encode("utf-8")).hexdigest()

            batch_size = 50
            skipped_count = 0
            for i in range(0, total, batch_size):
                batch = entities[i : i + batch_size]
                for entity in batch:
                    content = entity["content"]
                    entity_id = entity["id"]
                    new_hash = get_content_hash(content)

                    # Incremental check
                    if not force:
                        with self.session_factory() as session:
                            from sqlalchemy import select

                            stmt = (
                                select(KBEmbedding)
                                .where(KBEmbedding.document_id == entity_id)
                                .limit(1)
                            )
                            existing = session.execute(stmt).scalars().first()
                            if existing:
                                existing_hash = (existing.metadata_ or {}).get(
                                    "content_hash"
                                )
                                if existing_hash == new_hash:
                                    skipped_count += 1
                                    continue

                    # If we reach here, we index (either forced or changed)
                    # 1. Clean up existing if any
                    self.kb_service.delete_document(entity_id)

                    # 2. Add new doc
                    doc = Document(
                        content=content,
                        document_id=entity_id,
                        metadata={
                            "id": entity_id,
                            "name": entity["name"],
                            "entity_type": entity["type"],
                            "description": entity["description"],
                            "content_hash": new_hash,
                        },
                    )
                    self.kb_service.add_document(doc)

                current = min(i + batch_size, total)
                progress_msg = f"Indexed {current}/{total} entities"
                if skipped_count > 0:
                    progress_msg += f" ({skipped_count} skipped)"
                progress_msg += "..."

                self.tracker.update(current, total, "indexing", progress_msg)
                # Yield to other threads/processes
                import time

                time.sleep(0.1)

            self.tracker.update(
                total, total, "completed", "Semantic search index ready."
            )
            logger.info(f"Background indexing completed for {total} entities.")

        except Exception as e:
            logger.error(f"Background indexing failed: {e}")
            self.tracker.update(0, 0, "error", str(e))

    def run_full_lifecycle(
        self, registry_svc: Optional[Any] = None, force: bool = False
    ):
        """
        Complete registry lifecycle:
        1. Sync Filesystem -> Database
        2. Rebuild Vector Index
        """
        try:
            from common_lib.modules.orchestration.db_operations import import_files

            logger.info("Starting background registry sync lifecycle...")
            # We don't know total yet for importing, so stick to 0/0
            self.tracker.update(0, 0, "importing", "Syncing filesystem to database...")

            # 1. Import Files (FS -> DB)
            result = import_files(force=force)

            # Relax check: proceed if any files were imported, even if some errors/warnings occurred
            # This handles cases where 99% of entities are fine but 1% have resolution warnings
            files_count = result.get("data", {}).get("files_imported", 0)

            if not result.get("success") and files_count == 0:
                error_msg = result.get("message", "Filesystem sync failed")
                logger.error(f"Registry import failed: {error_msg}")
                self.tracker.update(0, 0, "error", f"Sync Failed: {error_msg}")
                return
            elif not result.get("success"):
                logger.warning(
                    f"Registry import had partial success ({files_count} files imported). Proceeding to indexing."
                )

            # 2. Re-indexing (DB -> Vector)
            # This method updates tracker to 'indexing' internally
            self.reindex_all(registry_svc, force=force)

        except Exception as e:
            logger.error(f"Registry lifecycle failed: {e}")
            self.tracker.update(0, 0, "error", f"Lifecycle Error: {str(e)}")


_search_service = None


def get_search_service():
    global _search_service
    if _search_service is None:
        _search_service = RegistrySearchService()
    return _search_service
