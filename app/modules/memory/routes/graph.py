"""Memory Graph — CRUD routes for memory graph visualization tables.

Orphaned legacy tables: memory_god_nodes, memory_links, memory_communities, memory_versions.
These power the knowledge graph visualization in the Cognitive Memory module.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from common_lib.modules.data_storage.database.connection import get_engine

router = APIRouter(prefix="/graph", tags=["Memory — Graph"])


# ── God Nodes ──────────────────────────────────────────────────────

class GodNodeResponse(BaseModel):
    id: int
    session_id: str
    memory_id: int
    degree: Optional[int] = None
    betweenness: Optional[float] = None
    closeness: Optional[float] = None
    topic: Optional[str] = None
    summary: Optional[str] = None
    last_updated: Optional[datetime] = None


class GodNodeListResponse(BaseModel):
    items: list[GodNodeResponse]
    total: int


# ── Links ──────────────────────────────────────────────────────────

class MemoryLinkCreate(BaseModel):
    from_memory_id: int
    to_memory_id: int
    link_type: str = "related"
    weight: float = 1.0
    description: str = ""


class MemoryLinkResponse(BaseModel):
    id: int
    from_memory_id: int
    to_memory_id: int
    link_type: str
    weight: float
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class MemoryLinkListResponse(BaseModel):
    items: list[MemoryLinkResponse]
    total: int


# ── Communities ────────────────────────────────────────────────────

class MemoryCommunityCreate(BaseModel):
    name: str
    member_ids: str = "[]"
    theme: Optional[str] = None
    keywords: Optional[str] = None


class MemoryCommunityResponse(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    member_ids: Optional[str] = None
    god_node_id: Optional[int] = None
    god_node_centrality: Optional[float] = None
    density: Optional[float] = None
    size: Optional[int] = None
    theme: Optional[str] = None
    keywords: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MemoryCommunityListResponse(BaseModel):
    items: list[MemoryCommunityResponse]
    total: int


# ── Versions ───────────────────────────────────────────────────────

class MemoryVersionResponse(BaseModel):
    id: Optional[int] = None
    memory_id: int
    content: str
    importance: float = 0.0
    reason: str = ""
    version: int = 0
    created_at: Optional[datetime] = None


class MemoryVersionListResponse(BaseModel):
    items: list[MemoryVersionResponse]
    total: int


# ── Import ORM models ─────────────────────────────────────────────

from common_lib.modules.memory.db_models import (
    MemoryGodNodes,
    MemoryLinks,
    MemoryCommunities,
    MemoryVersions,
)


def _god_node_response(row: MemoryGodNodes) -> GodNodeResponse:
    return GodNodeResponse(
        id=row.id,
        session_id=row.session_id or "",
        memory_id=row.memory_id or 0,
        degree=row.degree,
        betweenness=row.betweenness,
        closeness=row.closeness,
        topic=row.topic,
        summary=row.summary,
        last_updated=row.last_updated,
    )


def _link_response(row: MemoryLinks) -> MemoryLinkResponse:
    return MemoryLinkResponse(
        id=row.id,
        from_memory_id=row.from_memory_id or 0,
        to_memory_id=row.to_memory_id or 0,
        link_type=row.link_type or "related",
        weight=row.weight or 0.0,
        description=row.description,
        created_at=row.created_at,
    )


def _community_response(row: MemoryCommunities) -> MemoryCommunityResponse:
    return MemoryCommunityResponse(
        id=row.id,
        name=row.name,
        member_ids=row.member_ids,
        god_node_id=row.god_node_id,
        god_node_centrality=row.god_node_centrality,
        density=row.density,
        size=row.size,
        theme=row.theme,
        keywords=row.keywords,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _version_response(row: MemoryVersions) -> MemoryVersionResponse:
    return MemoryVersionResponse(
        id=row.id,
        memory_id=row.memory_id or 0,
        content=row.content or "",
        importance=row.importance or 0.0,
        reason=row.reason or "",
        version=row.version or 0,
        created_at=row.created_at,
    )


# ── God Nodes endpoints ───────────────────────────────────────────

@router.get("/god-nodes", response_model=GodNodeListResponse)
def list_god_nodes(
    session_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    with Session(get_engine()) as session:
        query = select(MemoryGodNodes)
        if session_id:
            query = query.where(MemoryGodNodes.session_id == session_id)
        query = query.order_by(MemoryGodNodes.degree.desc()).limit(limit)
        rows = session.exec(query).all()
        return GodNodeListResponse(
            items=[_god_node_response(r) for r in rows],
            total=len(rows),
        )


@router.get("/god-nodes/stats")
def god_node_stats():
    with Session(get_engine()) as session:
        all_rows = session.exec(select(MemoryGodNodes)).all()
        total = len(all_rows)
        sessions = set(r.session_id for r in all_rows if r.session_id)
        avg_degree = sum(r.degree or 0 for r in all_rows) / max(total, 1)
        avg_betweenness = sum(r.betweenness or 0 for r in all_rows) / max(total, 1)
        return {
            "total_god_nodes": total,
            "unique_sessions": len(sessions),
            "avg_degree": round(avg_degree, 2),
            "avg_betweenness": round(avg_betweenness, 4),
        }


# ── Links endpoints ───────────────────────────────────────────────

@router.get("/links", response_model=MemoryLinkListResponse)
def list_links(
    from_memory_id: Optional[int] = Query(None),
    to_memory_id: Optional[int] = Query(None),
    link_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    with Session(get_engine()) as session:
        query = select(MemoryLinks)
        if from_memory_id is not None:
            query = query.where(MemoryLinks.from_memory_id == from_memory_id)
        if to_memory_id is not None:
            query = query.where(MemoryLinks.to_memory_id == to_memory_id)
        if link_type:
            query = query.where(MemoryLinks.link_type == link_type)
        query = query.order_by(MemoryLinks.created_at.desc()).limit(limit)
        rows = session.exec(query).all()
        return MemoryLinkListResponse(
            items=[_link_response(r) for r in rows],
            total=len(rows),
        )


@router.post("/links", response_model=MemoryLinkResponse, status_code=201)
def create_link(body: MemoryLinkCreate):
    with Session(get_engine()) as session:
        row = MemoryLinks(
            from_memory_id=body.from_memory_id,
            to_memory_id=body.to_memory_id,
            link_type=body.link_type,
            weight=body.weight,
            description=body.description,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _link_response(row)


@router.delete("/links/{link_id}", status_code=204)
def delete_link(link_id: int):
    with Session(get_engine()) as session:
        row = session.get(MemoryLinks, link_id)
        if not row:
            raise HTTPException(status_code=404, detail="Link not found")
        session.delete(row)
        session.commit()


# ── Communities endpoints ─────────────────────────────────────────

@router.get("/communities", response_model=MemoryCommunityListResponse)
def list_communities(
    theme: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    with Session(get_engine()) as session:
        query = select(MemoryCommunities)
        if theme:
            query = query.where(MemoryCommunities.theme == theme)
        query = query.order_by(MemoryCommunities.size.desc()).limit(limit)
        rows = session.exec(query).all()
        return MemoryCommunityListResponse(
            items=[_community_response(r) for r in rows],
            total=len(rows),
        )


@router.get("/communities/stats")
def community_stats():
    with Session(get_engine()) as session:
        all_rows = session.exec(select(MemoryCommunities)).all()
        total = len(all_rows)
        avg_size = sum(r.size or 0 for r in all_rows) / max(total, 1)
        avg_density = sum(r.density or 0 for r in all_rows) / max(total, 1)
        themes = set(r.theme for r in all_rows if r.theme)
        return {
            "total_communities": total,
            "unique_themes": len(themes),
            "avg_size": round(avg_size, 1),
            "avg_density": round(avg_density, 4),
        }


# ── Versions endpoints ────────────────────────────────────────────

@router.get("/versions", response_model=MemoryVersionListResponse)
def list_versions(
    memory_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    with Session(get_engine()) as session:
        query = select(MemoryVersions)
        if memory_id is not None:
            query = query.where(MemoryVersions.memory_id == memory_id)
        query = query.order_by(MemoryVersions.version.desc()).limit(limit)
        rows = session.exec(query).all()
        return MemoryVersionListResponse(
            items=[_version_response(r) for r in rows],
            total=len(rows),
        )


@router.get("/versions/{version_id}", response_model=MemoryVersionResponse)
def get_version(version_id: int):
    with Session(get_engine()) as session:
        row = session.get(MemoryVersions, version_id)
        if not row:
            raise HTTPException(status_code=404, detail="Version not found")
        return _version_response(row)


@router.get("/summary")
def graph_summary():
    """Aggregate stats across all memory graph tables."""
    with Session(get_engine()) as session:
        god_nodes = len(session.exec(select(MemoryGodNodes)).all())
        links = len(session.exec(select(MemoryLinks)).all())
        communities = len(session.exec(select(MemoryCommunities)).all())
        versions = len(session.exec(select(MemoryVersions)).all())
        return {
            "god_nodes": god_nodes,
            "links": links,
            "communities": communities,
            "versions": versions,
            "total_entities": god_nodes + links + communities + versions,
        }
