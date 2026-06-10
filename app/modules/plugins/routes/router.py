import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Query
from common_lib.modules.plugins.schemas import (
    PluginResponse,
    NodeCandidateSchema,
    PluginDetailResponse,
    PluginUpdateRequest,
)
from common_lib.modules.plugins.manager import PluginManager
from common_lib.modules.plugins.plugin_service import PluginService
from common_lib.modules.knowledge_base.service import get_kb_service, init_kb_service

# Path constants
_DOCS_BASE = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    / "Python Libs/common_lib/docs"
)
_KB_BASE = (
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "Knowledgebase"
)
_TEMPLATES_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "Python Libs" / "common_lib" / "src" / "common_lib" / "templates" / "tools" / "discovered"
)

# Initialize services at module load
init_kb_service(_DOCS_BASE, _KB_BASE)

router = APIRouter(tags=["Plugins"])
plugin_manager = PluginManager()
plugin_manager.start()

from app.core.common_lib_integration import common_memory

# Initialize plugin service with injected common_memory
_plugin_svc = PluginService(common_memory, _TEMPLATES_ROOT)


@router.get("", response_model=List[PluginResponse])
@router.get("/", response_model=List[PluginResponse])
async def list_plugins():
    return _plugin_svc.list_plugins(plugin_manager)


@router.get("/{plugin_id}", response_model=PluginDetailResponse)
async def get_plugin_details(plugin_id: str):
    result = _plugin_svc.get_plugin_details(plugin_id, plugin_manager)
    if not result:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return result


@router.post("/analyze", response_model=List[NodeCandidateSchema])
async def analyze_plugin(file: UploadFile = File(...)):
    """
    Uploads a python plugin file and returns candidate nodes found via static analysis.
    """
    if not file.filename.endswith(".py"):
        raise HTTPException(
            status_code=400, detail="Only .py files are supported for analysis."
        )

    # Save to a temporary location for analysis
    temp_dir = Path("resources/temp_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        candidates = plugin_manager.analyze_plugin_file(temp_path)
        return [
            NodeCandidateSchema(
                name=c.name,
                description=c.description,
                parameters=c.parameters,
                module_path=str(temp_path),
            )
            for c in candidates
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/onboard")
async def onboard_plugin_tools(
    plugin_id: str = Form(...),
    name: str = Form(...),
    category: str = Form("general"),
    author: str = Form("System"),
    author_url: Optional[str] = Form(None),
    thumbnail_url: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma separated
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """
    Comprehensive onboarding endpoint:
    1. Uploads ZIP or .py file.
    2. Extracts and analyzes tools.
    3. Generates enriched Plugin and Tool YAMLs.
    """
    # Create temp directory for upload
    temp_dir = Path("resources/temp_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Prepare metadata for PluginManager
        metadata = {
            "description": description,
            "author_url": author_url,
            "thumbnail_url": thumbnail_url,
            "tags": [tag.strip() for tag in tags.split(",")] if tags else [],
        }

        # Determine if it's a zip or py
        if file.filename.endswith(".zip"):
            result = plugin_manager.onboard_plugin(
                plugin_id=plugin_id,
                name=name,
                zip_path=temp_path,
                metadata=metadata,
                category=category,
                author=author,
            )
        elif file.filename.endswith(".py"):
            with open(temp_path, "r", encoding="utf-8") as f:
                code = f.read()
            result = plugin_manager.onboard_plugin(
                plugin_id=plugin_id,
                name=name,
                source_code=code,
                metadata=metadata,
                category=category,
                author=author,
            )
        else:
            raise HTTPException(
                status_code=400, detail="Unsupported file type. Use .zip or .py"
            )

        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()

        return result

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=f"Onboarding failed: {str(e)}")


@router.patch("/{plugin_id}", response_model=PluginResponse)
async def update_plugin(plugin_id: str, request: PluginUpdateRequest):
    """Update plugin metadata."""
    result = _plugin_svc.update_plugin(
        plugin_id, request.model_dump(exclude_unset=True), plugin_manager
    )
    if not result:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return result


@router.delete("/{plugin_id}")
async def delete_plugin(plugin_id: str):
    """Remove plugin definition from registry."""
    success = _plugin_svc.delete_plugin(plugin_id)
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"status": "success", "message": f"Plugin {plugin_id} deleted"}


# ==================== Project KB / Documentation ====================


_kb_svc = get_kb_service()


@router.get("/project-kb/graph")
async def get_project_kb_graph(refresh: bool = Query(False)):
    """
    Returns the project knowledge base graph for visualization.
    Syncs all docs/*.md files and returns them as nodes.
    """
    return _kb_svc.load_graph(refresh=refresh)


@router.get("/project-kb/nodes")
async def get_project_kb_nodes():
    """Returns all wiki nodes for documentation browser."""
    graph = _kb_svc.load_graph()
    return {"nodes": graph.get("nodes", []), "categories": graph.get("categories", [])}


@router.get("/project-kb/node/{node_id}")
async def get_project_kb_node(node_id: str):
    """Returns details for a specific wiki node."""
    node = _kb_svc.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


@router.get("/project-kb/search")
async def search_project_kb(q: str = ""):
    """Search wiki nodes by label or description."""
    return {"results": _kb_svc.find_nodes(q), "query": q}


@router.get("/docs/{doc_path:path}")
async def get_doc_content(doc_path: str):
    """Returns raw documentation content from markdown files."""
    docs_path = _DOCS_BASE / doc_path
    if not docs_path.exists():
        docs_path = _DOCS_BASE / f"{doc_path}.md"
    if docs_path.exists():
        with open(docs_path, "r", encoding="utf-8") as f:
            content = f.read()
            return {"content": content, "path": doc_path, "format": "markdown"}
    raise HTTPException(status_code=404, detail=f"Documentation {doc_path} not found")
