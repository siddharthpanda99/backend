"""Memory Documentation API Routes.

Serves memory system docs via the shared DocsService.
Now includes frontmatter metadata for agent-parseable docs.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException

from common_lib.modules.docs_service import DocsService
from common_lib.paths import get_repo_root

router = APIRouter(tags=["memory-docs"])

logger = logging.getLogger(__name__)


@router.get("/docs")
async def list_docs():
    """List all available memory documentation with frontmatter metadata."""
    try:
        docs_dir = (
            Path(get_repo_root())
            / "Python Libs" / "common_lib" / "src" / "common_lib"
            / "modules" / "memory" / "docs"
        )
        if not docs_dir.exists():
            raise HTTPException(status_code=404, detail="Documentation directory not found")

        service = DocsService(docs_dir)
        documents = service.list_docs()
        return {"status": "ok", "documents": documents, "count": len(documents)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list docs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/docs/{doc_id}")
async def get_doc(doc_id: str):
    """Retrieve a specific memory document by ID with frontmatter metadata."""
    try:
        docs_dir = (
            Path(get_repo_root())
            / "Python Libs" / "common_lib" / "src" / "common_lib"
            / "modules" / "memory" / "docs"
        )
        service = DocsService(docs_dir)
        doc = service.get_doc(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
        return {"status": "ok", **doc}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve doc {doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
