"""
Audio Library Browser API Routes (AURA Module 36).

Endpoints for browsing, searching, managing collections, tags, and metadata.
"""

import os
import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from common_lib.modules.audio_processing.library.asset_library import AssetLibrary
from common_lib.modules.audio_processing.library.browser import LibraryBrowser
from common_lib.modules.audio_processing.library.collections import CollectionManager
from common_lib.modules.audio_processing.library.search_service import SearchService, SearchQuery
from common_lib.modules.audio_processing.library.metadata_editor import MetadataEditor
from common_lib.modules.audio_processing.library.metadata import AudioMetadataExtractor

router = APIRouter()

# ── Shared singletons ──────────────────────────────────────────────────
_asset_library = AssetLibrary()
_library_browser = LibraryBrowser(_asset_library)
_collection_manager = CollectionManager()
_search_service = SearchService(_collection_manager)
_metadata_editor = MetadataEditor()


# ════════════════════════════════════════════════════════════════════════
# Schemas
# ════════════════════════════════════════════════════════════════════════

class LibraryScanRequest(BaseModel):
    scan_dir: str = Field(..., description="Directory path to scan for audio files")


class SearchRequest(BaseModel):
    query: str = ""
    tags: Optional[List[str]] = None
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None
    key: Optional[str] = None
    duration_min: Optional[float] = None
    duration_max: Optional[float] = None
    file_ext: Optional[str] = None
    collection_id: Optional[str] = None
    sort_by: str = "relevance"
    sort_order: str = "desc"
    limit: int = 50
    offset: int = 0
    semantic: bool = False


class CollectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    color: str = "#6366f1"
    icon: str = "folder"
    tags: Optional[List[str]] = None


class CollectionUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    tags: Optional[List[str]] = None
    sort_order: Optional[int] = None
    pinned: Optional[bool] = None


class CollectionAssetsRequest(BaseModel):
    asset_ids: List[str]


class MetadataTagsRequest(BaseModel):
    tags: List[str]


class MetadataDescriptionRequest(BaseModel):
    description: str = ""


class MetadataRatingRequest(BaseModel):
    rating: int = Field(0, ge=0, le=5)


class CustomFieldRequest(BaseModel):
    key: str
    value: Any


class BulkTagRequest(BaseModel):
    asset_paths: List[str]
    tags: List[str]
    mode: str = "add"  # add, set, remove


class BulkRatingRequest(BaseModel):
    asset_paths: List[str]
    rating: int = Field(0, ge=0, le=5)


class SmartRuleCreateRequest(BaseModel):
    name: str
    conditions: Dict[str, Any]
    collection_id: Optional[str] = None


class FolderScanRequest(BaseModel):
    folder_path: str = Field(..., description="Root folder path to build hierarchy from")


# ════════════════════════════════════════════════════════════════════════
# Library Overview
# ════════════════════════════════════════════════════════════════════════

@router.get("/overview")
async def library_overview():
    """Get library overview with counts, stats, and recent assets."""
    assets = _asset_library.get_assets()
    col_stats = _collection_manager.get_collection_stats()
    meta_stats = _metadata_editor.get_metadata_stats()
    facets = _search_service.get_facets(assets)

    return {
        "total_assets": len(assets),
        "total_duration_seconds": sum(a.get("duration_seconds", 0) for a in assets),
        "total_size_bytes": sum(a.get("file_size", 0) for a in assets),
        "collections": col_stats,
        "metadata": meta_stats,
        "facets": facets,
        "recent_assets": sorted(assets, key=lambda a: a.get("mtime", 0), reverse=True)[:10],
    }


# ════════════════════════════════════════════════════════════════════════
# Scanning
# ════════════════════════════════════════════════════════════════════════

@router.post("/scan")
async def scan_library(request: LibraryScanRequest):
    """Scan a directory for audio files and index them."""
    if not os.path.exists(request.scan_dir):
        raise HTTPException(status_code=400, detail=f"Directory not found: {request.scan_dir}")

    newly_added = _asset_library.scan_library(request.scan_dir)

    # Auto-tag newly indexed assets
    assets = _asset_library.get_assets()
    for asset in assets:
        path = asset.get("path", "")
        existing_tags = _metadata_editor.get_tags(path)
        if not existing_tags:
            auto_tags = _metadata_editor.auto_tag(asset)
            if auto_tags:
                _metadata_editor.set_tags(path, auto_tags)

    # Index into Elasticsearch if available
    _search_service.index_assets(assets)

    return {
        "success": True,
        "newly_added": newly_added,
        "total_indexed": len(assets),
    }


@router.get("/folders/tree")
async def get_folder_tree(root_path: str = Query("", description="Root path for folder tree")):
    """Build folder hierarchy from indexed assets."""
    assets = _asset_library.get_assets()

    tree: Dict[str, Any] = {}

    for asset in assets:
        path = asset.get("path", "")
        if not path:
            continue

        # Build tree nodes
        parts = os.path.normpath(path).split(os.sep)
        current = tree

        for part in parts:
            if part not in current:
                current[part] = {
                    "name": part,
                    "children": {},
                    "asset_count": 0,
                    "is_leaf": False,
                }
            current[part]["asset_count"] += 1
            current = current[part]["children"]

    def flatten_tree(node: Dict[str, Any], path: str = "") -> List[Dict[str, Any]]:
        result = []
        for name, data in sorted(node.items()):
            node_path = os.path.join(path, name) if path else name
            children = flatten_tree(data["children"], node_path)
            result.append({
                "name": name,
                "path": node_path,
                "asset_count": data["asset_count"],
                "children": children,
                "is_leaf": len(children) == 0,
            })
        return result

    return {"tree": flatten_tree(tree)}


# ════════════════════════════════════════════════════════════════════════
# Assets
# ════════════════════════════════════════════════════════════════════════

@router.get("/assets")
async def list_assets(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List all indexed assets with pagination."""
    assets = _asset_library.get_assets()
    paginated = assets[offset:offset + limit]

    # Enrich with metadata
    enriched = []
    for asset in paginated:
        path = asset.get("path", "")
        enriched.append({
            **asset,
            "user_tags": _metadata_editor.get_tags(path),
            "description": _metadata_editor.get_description(path),
            "rating": _metadata_editor.get_rating(path),
            "custom_fields": _metadata_editor.get_custom_fields(path),
            "collections": _collection_manager.get_asset_collections(path),
        })

    return {
        "assets": enriched,
        "total": len(assets),
        "limit": limit,
        "offset": offset,
    }


@router.get("/assets/{asset_path:path}")
async def get_asset_detail(asset_path: str):
    """Get detailed metadata for a single asset."""
    asset = _asset_library.get_asset_by_path(asset_path)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_path}")

    path = asset.get("path", asset_path)
    return {
        **asset,
        "user_tags": _metadata_editor.get_tags(path),
        "description": _metadata_editor.get_description(path),
        "rating": _metadata_editor.get_rating(path),
        "custom_fields": _metadata_editor.get_custom_fields(path),
        "collections": _collection_manager.get_asset_collections(path),
    }


# ════════════════════════════════════════════════════════════════════════
# Search
# ════════════════════════════════════════════════════════════════════════

@router.post("/search")
async def search_assets(request: SearchRequest):
    """Full-text and metadata search across audio assets."""
    assets = _asset_library.get_assets()

    query = SearchQuery(
        query=request.query,
        tags=request.tags,
        bpm_min=request.bpm_min,
        bpm_max=request.bpm_max,
        key=request.key,
        duration_min=request.duration_min,
        duration_max=request.duration_max,
        file_ext=request.file_ext,
        collection_id=request.collection_id,
        sort_by=request.sort_by,
        sort_order=request.sort_order,
        limit=request.limit,
        offset=request.offset,
        semantic=request.semantic,
    )

    results = _search_service.search(query, assets)

    # Enrich results
    enriched = []
    for result in results:
        path = result.asset.get("path", "")
        enriched.append({
            **result.asset,
            "score": result.score,
            "highlights": result.highlights,
            "user_tags": _metadata_editor.get_tags(path),
            "description": _metadata_editor.get_description(path),
            "rating": _metadata_editor.get_rating(path),
        })

    return {
        "results": enriched,
        "total": len(enriched),
        "query": request.query,
    }


@router.get("/suggestions")
async def get_suggestions(prefix: str = Query("", min_length=1)):
    """Get autocomplete suggestions for tags and asset names."""
    assets = _asset_library.get_assets()
    return {"suggestions": _search_service.get_suggestions(prefix, assets)}


@router.get("/facets")
async def get_facets():
    """Get facet counts for the current library (tags, keys, BPM ranges, extensions)."""
    assets = _asset_library.get_assets()
    return _search_service.get_facets(assets)


# ════════════════════════════════════════════════════════════════════════
# Collections
# ════════════════════════════════════════════════════════════════════════

@router.get("/collections")
async def list_collections(sort_by: str = Query("sort_order")):
    """List all collections."""
    return {"collections": _collection_manager.list_collections(sort_by)}


@router.post("/collections")
async def create_collection(request: CollectionCreateRequest):
    """Create a new collection."""
    col = _collection_manager.create_collection(
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
        tags=request.tags,
    )
    return col.to_dict()


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str):
    """Get a collection with its assets."""
    col = _collection_manager.get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Enrich with asset data
    assets = _asset_library.get_assets()
    asset_map = {a.get("path", a.get("name", "")): a for a in assets}

    enriched_assets = []
    for aid in col.asset_ids:
        if aid in asset_map:
            asset = asset_map[aid]
            enriched_assets.append({
                **asset,
                "user_tags": _metadata_editor.get_tags(aid),
                "description": _metadata_editor.get_description(aid),
                "rating": _metadata_editor.get_rating(aid),
            })

    return {
        **col.to_dict(),
        "assets": enriched_assets,
    }


@router.put("/collections/{collection_id}")
async def update_collection(collection_id: str, request: CollectionUpdateRequest):
    """Update a collection."""
    col = _collection_manager.update_collection(
        collection_id=collection_id,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
        tags=request.tags,
        sort_order=request.sort_order,
        pinned=request.pinned,
    )
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col.to_dict()


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str):
    """Delete a collection."""
    if not _collection_manager.delete_collection(collection_id):
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"success": True}


@router.post("/collections/{collection_id}/assets")
async def add_assets_to_collection(collection_id: str, request: CollectionAssetsRequest):
    """Add assets to a collection."""
    count = _collection_manager.add_assets(collection_id, request.asset_ids)
    return {"success": True, "added": count}


@router.delete("/collections/{collection_id}/assets/{asset_path:path}")
async def remove_asset_from_collection(collection_id: str, asset_path: str):
    """Remove an asset from a collection."""
    if not _collection_manager.remove_asset(collection_id, asset_path):
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True}


@router.post("/collections/{collection_id}/reorder")
async def reorder_collection_assets(collection_id: str, request: CollectionAssetsRequest):
    """Reorder assets in a collection."""
    if not _collection_manager.reorder_assets(collection_id, request.asset_ids):
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"success": True}


# ════════════════════════════════════════════════════════════════════════
# Smart Rules
# ════════════════════════════════════════════════════════════════════════

@router.get("/smart-rules")
async def list_smart_rules():
    """List all smart rules."""
    return {"rules": _collection_manager.list_smart_rules()}


@router.post("/smart-rules")
async def create_smart_rule(request: SmartRuleCreateRequest):
    """Create a smart rule."""
    rule = _collection_manager.create_smart_rule(
        name=request.name,
        conditions=request.conditions,
        collection_id=request.collection_id,
    )
    return rule.to_dict()


@router.delete("/smart-rules/{rule_id}")
async def delete_smart_rule(rule_id: str):
    """Delete a smart rule."""
    if not _collection_manager.delete_smart_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}


@router.post("/smart-rules/apply")
async def apply_smart_rules():
    """Apply smart rules to all assets and return matches."""
    assets = _asset_library.get_assets()
    return {"matches": _collection_manager.apply_smart_rules(assets)}


# ════════════════════════════════════════════════════════════════════════
# Metadata
# ════════════════════════════════════════════════════════════════════════

@router.get("/assets/{asset_path:path}/metadata")
async def get_asset_metadata(asset_path: str):
    """Get full metadata for an asset."""
    return {
        "asset_path": asset_path,
        "tags": _metadata_editor.get_tags(asset_path),
        "description": _metadata_editor.get_description(asset_path),
        "rating": _metadata_editor.get_rating(asset_path),
        "custom_fields": _metadata_editor.get_custom_fields(asset_path),
    }


@router.put("/assets/{asset_path:path}/tags")
async def set_asset_tags(asset_path: str, request: MetadataTagsRequest):
    """Replace all tags on an asset."""
    tags = _metadata_editor.set_tags(asset_path, request.tags)
    return {"success": True, "tags": tags}


@router.post("/assets/{asset_path:path}/tags")
async def add_asset_tags(asset_path: str, request: MetadataTagsRequest):
    """Add tags to an asset (merge with existing)."""
    tags = _metadata_editor.add_tags(asset_path, request.tags)
    return {"success": True, "tags": tags}


@router.delete("/assets/{asset_path:path}/tags")
async def remove_asset_tags(asset_path: str, request: MetadataTagsRequest):
    """Remove specific tags from an asset."""
    tags = _metadata_editor.remove_tags(asset_path, request.tags)
    return {"success": True, "tags": tags}


@router.put("/assets/{asset_path:path}/description")
async def set_asset_description(asset_path: str, request: MetadataDescriptionRequest):
    """Set description on an asset."""
    desc = _metadata_editor.set_description(asset_path, request.description)
    return {"success": True, "description": desc}


@router.put("/assets/{asset_path:path}/rating")
async def set_asset_rating(asset_path: str, request: MetadataRatingRequest):
    """Set rating (0-5) on an asset."""
    rating = _metadata_editor.set_rating(asset_path, request.rating)
    return {"success": True, "rating": rating}


@router.put("/assets/{asset_path:path}/custom-field")
async def set_custom_field(asset_path: str, request: CustomFieldRequest):
    """Set a custom field on an asset."""
    fields = _metadata_editor.set_custom_field(asset_path, request.key, request.value)
    return {"success": True, "custom_fields": fields}


@router.delete("/assets/{asset_path:path}/custom-field/{field_key}")
async def delete_custom_field(asset_path: str, field_key: str):
    """Delete a custom field from an asset."""
    if not _metadata_editor.delete_custom_field(asset_path, field_key):
        raise HTTPException(status_code=404, detail="Field not found")
    return {"success": True}


# ════════════════════════════════════════════════════════════════════════
# Bulk Operations
# ════════════════════════════════════════════════════════════════════════

@router.post("/bulk/tags")
async def bulk_set_tags(request: BulkTagRequest):
    """Bulk set/add/remove tags on multiple assets."""
    if request.mode == "set":
        count = _metadata_editor.bulk_set_tags(request.asset_paths, request.tags)
    elif request.mode == "remove":
        count = 0
        for path in request.asset_paths:
            _metadata_editor.remove_tags(path, request.tags)
            count += 1
    else:  # add
        count = _metadata_editor.bulk_add_tags(request.asset_paths, request.tags)
    return {"success": True, "affected": count}


@router.post("/bulk/rating")
async def bulk_set_rating(request: BulkRatingRequest):
    """Bulk set rating on multiple assets."""
    count = _metadata_editor.bulk_set_rating(request.asset_paths, request.rating)
    return {"success": True, "affected": count}


# ════════════════════════════════════════════════════════════════════════
# Tags Taxonomy
# ════════════════════════════════════════════════════════════════════════

@router.get("/tags")
async def list_all_tags():
    """Get all tags with counts."""
    return {"tags": _metadata_editor.get_all_tags()}


@router.get("/tags/taxonomy")
async def get_tag_taxonomy():
    """Get the smart tag taxonomy."""
    from common_lib.modules.audio_processing.library.metadata_editor import TAG_CATEGORIES
    return {"taxonomy": TAG_CATEGORIES}


__all__ = ["router"]
