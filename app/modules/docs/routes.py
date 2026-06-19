"""
Generic Documentation Router — serves markdown docs from common_lib/docs/<module>/.

Endpoint: GET /api/v1/docs/{module}/        — list docs for a module
          GET /api/v1/docs/{module}/{doc_id} — get a specific doc

Docs are stored as .md files under Backend Monorepo/Python Libs/common_lib/docs/<module>/
Each file can have YAML frontmatter for agent-parseable metadata.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException

from common_lib.modules.docs_service import DocsService
from common_lib.paths import get_repo_root

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documentation"])

def _get_docs_base() -> Path:
    """Lazy resolve the docs base directory to avoid import-time path resolution."""
    return (
        Path(get_repo_root())
        / "Python Libs" / "common_lib" / "docs"
    )


def _get_docs_service(module: str) -> DocsService:
    """Get a DocsService for a given module, raising 404 if the module dir doesn't exist."""
    module_dir = _get_docs_base() / module
    if not module_dir.exists() or not module_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Documentation module '{module}' not found at {module_dir}"
        )
    return DocsService(module_dir)


@router.get("/docs/{module}")
async def list_module_docs(module: str):
    """List all documentation documents for a given module (e.g., 'memory', 'harness', 'knowledgebase')."""
    try:
        service = _get_docs_service(module)
        documents = service.list_docs()
        return {"status": "ok", "module": module, "documents": documents, "count": len(documents)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list docs for module '{module}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/docs/{module}/{doc_id}")
async def get_module_doc(module: str, doc_id: str):
    """Retrieve a specific documentation document by module and doc_id."""
    try:
        service = _get_docs_service(module)
        doc = service.get_doc(doc_id)
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{doc_id}' not found in module '{module}'"
            )
        return {"status": "ok", "module": module, **doc}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve doc '{doc_id}' from module '{module}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
