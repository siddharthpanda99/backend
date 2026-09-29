from common_lib.modules.memory.service import MemoryService
from common_lib.modules.memory.memory_storage.repositories.memory_repository import (
    MemoryRepository,
)
from common_lib.modules.memory.memory_storage.adapters.pgvector_adapter import (
    PgVectorAdapter,
)
from common_lib.modules.memory.memory_storage.adapters.redis_adapter import RedisAdapter
from app.core.settings import get_settings
import os
import logging

logger = logging.getLogger(__name__)

_memory_service = None


def get_memory_service() -> MemoryService:
    """Get or create the MemoryService singleton with all configured adapters.

    Environment variables:
    - REDIS_HOST, REDIS_PORT, REDIS_DB: Redis connection settings
    - EMBEDDING_DIM: Vector embedding dimension (default: 384)
    - VECTOR_INDEX_TYPE: Index type - 'ivfflat' or 'hnsw' (default: 'ivfflat')
    """
    global _memory_service
    if _memory_service is None:
        settings = get_settings()
        database_url = settings.SQLALCHEMY_DATABASE_URI

        # Primary pgvector adapter
        adapter = PgVectorAdapter(database_url)
        try:
            adapter.connect_sync()
            logger.info("Primary pgvector adapter connected successfully")
        except Exception as e:
            logger.warning(f"Primary adapter connection failed: {e}")
        repository = MemoryRepository(adapter)

        # Hot tier (Redis) adapter
        hot_adapter = None
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        redis_db = int(os.environ.get("REDIS_DB", "0"))
        redis_password = os.environ.get("REDIS_PASSWORD")
        redis_ttl = int(os.environ.get("REDIS_DEFAULT_TTL", "300"))

        try:
            hot_adapter = RedisAdapter(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                default_ttl=redis_ttl,
                key_prefix="memory:",
            )
            # Connect will fall back to in-memory if Redis unavailable
            hot_adapter.connect_sync()
        except Exception as e:
            logger.warning(f"Hot adapter initialization failed: {e}")
            hot_adapter = None

        # Vector (pgvector) adapter
        vector_adapter = None
        vector_url = os.environ.get("VECTOR_DB_URL", database_url)
        embedding_dim = int(os.environ.get("EMBEDDING_DIM", "384"))
        index_type = os.environ.get("VECTOR_INDEX_TYPE", "ivfflat")

        try:
            if "postgresql" in vector_url:
                vector_adapter = PgVectorAdapter(
                    connection_string=vector_url,
                    embedding_dim=embedding_dim,
                    index_type=index_type,
                    use_pgvector=True,
                )
                vector_adapter.connect_sync()
                logger.info(
                    f"Vector adapter connected (dim={embedding_dim}, index={index_type})"
                )
            else:
                logger.info("Vector adapter skipped: not a PostgreSQL connection")
        except Exception as e:
            logger.warning(f"Vector adapter initialization failed: {e}")
            vector_adapter = None

        _memory_service = MemoryService(
            repository=repository,
            hot_adapter=hot_adapter,
            vector_adapter=vector_adapter,
        )
        logger.info("MemoryService initialized with all adapters")

    return _memory_service
