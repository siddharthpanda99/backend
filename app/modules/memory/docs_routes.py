"""Memory Documentation API Routes.

Provides REST endpoints for retrieving memory system markdown guides and submodule reference documents.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["memory-docs"])

logger = logging.getLogger(__name__)


def _extract_title(file_path: Path) -> str:
    """Extract first # header as title, fall back to cleaned filename."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
    except Exception:
        pass
    return file_path.stem.replace("_", " ").title()


@router.get("/docs")
async def list_docs():
    """List all available memory documentation guides and submodule files."""
    try:
        from common_lib.paths import get_repo_root

        docs_dir = (
            Path(get_repo_root())
            / "Python Libs"
            / "common_lib"
            / "src"
            / "common_lib"
            / "modules"
            / "memory"
            / "docs"
        )

        if not docs_dir.exists():
            raise HTTPException(
                status_code=404, detail="Documentation directory not found on disk"
            )

        docs_list = []

        # 1. Root documents
        for file in docs_dir.glob("*.md"):
            docs_list.append(
                {
                    "id": file.stem.lower(),
                    "title": _extract_title(file),
                    "category": "Guides & Reference",
                    "filename": file.name,
                    "subfolder": "",
                }
            )

        # 2. Submodule documents
        memory_dir = docs_dir / "memory"
        if memory_dir.exists():
            for file in memory_dir.glob("*.md"):
                docs_list.append(
                    {
                        "id": f"memory_{file.stem.lower()}",
                        "title": _extract_title(file),
                        "category": "Submodule Deep Dive",
                        "filename": file.name,
                        "subfolder": "memory",
                    }
                )

        # Sort: Index first, then guides, then submodules
        docs_list.sort(key=lambda x: (x["category"] != "Guides & Reference", x["title"]))

        return {"status": "ok", "documents": docs_list, "count": len(docs_list)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list documentation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/docs/{doc_id}")
async def get_doc(doc_id: str):
    """Retrieve raw markdown content and title of a specific guide by ID."""
    try:
        from common_lib.paths import get_repo_root

        docs_dir = (
            Path(get_repo_root())
            / "Python Libs"
            / "common_lib"
            / "src"
            / "common_lib"
            / "modules"
            / "memory"
            / "docs"
        )

        target_file = None
        if doc_id.startswith("memory_"):
            filename = doc_id[7:] + ".md"
            target_file = docs_dir / "memory" / filename
            # Fallback for uppercase files in filesystem if any
            if not target_file.exists():
                for f in (docs_dir / "memory").glob("*.md"):
                    if f.name.lower() == filename.lower():
                        target_file = f
                        break
        else:
            filename = doc_id + ".md"
            target_file = docs_dir / filename
            if not target_file.exists():
                for f in docs_dir.glob("*.md"):
                    if f.name.lower() == filename.lower():
                        target_file = f
                        break

        if not target_file or not target_file.exists():
            raise HTTPException(
                status_code=404, detail=f"Documentation file not found for: {doc_id}"
            )

        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "status": "ok",
            "id": doc_id,
            "title": _extract_title(target_file),
            "content": content,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve document {doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
