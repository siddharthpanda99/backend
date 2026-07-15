"""Visual Database Designers API routes.
Thin wrapper — all logic in common_lib.modules.db_studio.visual_designers.service.
"""

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.db_studio.visual_designers import (
    VisualDesignerService,
    DiagramCreate, DiagramUpdate, DiagramOut, DiagramListResponse,
    NodeCreate, NodeUpdate, NodeOut,
    EdgeCreate, EdgeUpdate, EdgeOut,
    BulkNodesRequest, BulkEdgesRequest,
    LayoutCreate, LayoutOut,
    ReverseEngineerRequest, ReverseEngineerResponse,
    DDLGenerateRequest, DDLGenerateResponse,
    CompareRequest, CompareResponse,
    SyncRequest, SyncResponse, SyncHistoryOut,
    DesignTemplateCreate, DesignTemplateOut,
    CompareSessionOut,
)

router = APIRouter(prefix="/api/v1/designers", tags=["Visual Database Designers"])
svc = VisualDesignerService()


# ── Diagram CRUD ───────────────────────────────────────────────────────

@router.post("/diagrams", response_model=DiagramOut)
def create_diagram(req: DiagramCreate):
    return svc.create_diagram(req)


@router.get("/diagrams/{diagram_id}", response_model=DiagramOut)
def get_diagram(diagram_id: str):
    d = svc.get_diagram(diagram_id)
    if not d:
        raise HTTPException(404, "Diagram not found")
    return d


@router.get("/diagrams", response_model=DiagramListResponse)
def list_diagrams(
    search: str = None,
    connection_id: str = None,
    is_template: bool = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_diagrams(search, connection_id, is_template, offset, limit)


@router.put("/diagrams/{diagram_id}", response_model=DiagramOut)
def update_diagram(diagram_id: str, req: DiagramUpdate):
    d = svc.update_diagram(diagram_id, req)
    if not d:
        raise HTTPException(404, "Diagram not found")
    return d


@router.delete("/diagrams/{diagram_id}")
def delete_diagram(diagram_id: str):
    if not svc.delete_diagram(diagram_id):
        raise HTTPException(404, "Diagram not found")
    return {"ok": True}


# ── Node Management ────────────────────────────────────────────────────

@router.post("/nodes", response_model=NodeOut)
def add_node(req: NodeCreate):
    return svc.add_node(req)


@router.get("/nodes/{node_id}", response_model=NodeOut)
def get_node(node_id: str):
    n = svc.get_node(node_id)
    if not n:
        raise HTTPException(404, "Node not found")
    return n


@router.get("/diagrams/{diagram_id}/nodes", response_model=list[NodeOut])
def list_nodes(diagram_id: str):
    return svc.list_nodes(diagram_id)


@router.put("/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: str, req: NodeUpdate):
    n = svc.update_node(node_id, req)
    if not n:
        raise HTTPException(404, "Node not found")
    return n


@router.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    if not svc.delete_node(node_id):
        raise HTTPException(404, "Node not found")
    return {"ok": True}


@router.post("/nodes/bulk", response_model=list[NodeOut])
def add_bulk_nodes(req: BulkNodesRequest):
    return svc.add_bulk_nodes(req)


# ── Edge/Relationship Management ──────────────────────────────────────

@router.post("/edges", response_model=EdgeOut)
def add_edge(req: EdgeCreate):
    return svc.add_edge(req)


@router.get("/edges/{edge_id}", response_model=EdgeOut)
def get_edge(edge_id: str):
    e = svc.get_edge(edge_id)
    if not e:
        raise HTTPException(404, "Edge not found")
    return e


@router.get("/diagrams/{diagram_id}/edges", response_model=list[EdgeOut])
def list_edges(diagram_id: str):
    return svc.list_edges(diagram_id)


@router.put("/edges/{edge_id}", response_model=EdgeOut)
def update_edge(edge_id: str, req: EdgeUpdate):
    e = svc.update_edge(edge_id, req)
    if not e:
        raise HTTPException(404, "Edge not found")
    return e


@router.delete("/edges/{edge_id}")
def delete_edge(edge_id: str):
    if not svc.delete_edge(edge_id):
        raise HTTPException(404, "Edge not found")
    return {"ok": True}


@router.post("/edges/bulk", response_model=list[EdgeOut])
def add_bulk_edges(req: BulkEdgesRequest):
    return svc.add_bulk_edges(req)


# ── Layout Management ──────────────────────────────────────────────────

@router.post("/layouts", response_model=LayoutOut)
def save_layout(req: LayoutCreate):
    return svc.save_layout(req)


@router.get("/diagrams/{diagram_id}/layouts", response_model=list[LayoutOut])
def list_layouts(diagram_id: str):
    return svc.list_layouts(diagram_id)


@router.delete("/layouts/{layout_id}")
def delete_layout(layout_id: str):
    if not svc.delete_layout(layout_id):
        raise HTTPException(404, "Layout not found")
    return {"ok": True}


# ── Reverse Engineering ────────────────────────────────────────────────

@router.post("/reverse-engineer", response_model=ReverseEngineerResponse)
def reverse_engineer(req: ReverseEngineerRequest):
    return svc.reverse_engineer(req)


# ── DDL Generation ─────────────────────────────────────────────────────

@router.post("/generate-ddl", response_model=DDLGenerateResponse)
def generate_ddl(req: DDLGenerateRequest):
    return svc.generate_ddl(req)


# ── Schema Comparison ──────────────────────────────────────────────────

@router.post("/compare", response_model=CompareResponse)
def compare(req: CompareRequest):
    return svc.compare(req)


# ── Synchronization ────────────────────────────────────────────────────

@router.post("/synchronize", response_model=SyncResponse)
def synchronize(req: SyncRequest):
    return svc.synchronize(req)


@router.get("/sync-history", response_model=list[SyncHistoryOut])
def list_sync_history(
    diagram_id: str = None,
    connection_id: str = None,
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_sync_history(diagram_id, connection_id, limit)


# ── Design Templates ──────────────────────────────────────────────────

@router.get("/templates", response_model=list[DesignTemplateOut])
def list_templates(
    category: str = None,
    database_type: str = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_templates(category, database_type, offset, limit)


@router.post("/templates", response_model=DesignTemplateOut)
def create_template(req: DesignTemplateCreate):
    return svc.create_template(req)


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    if not svc.delete_template(template_id):
        raise HTTPException(404, "Template not found")
    return {"ok": True}


# ── Compare Sessions ──────────────────────────────────────────────────

@router.get("/compare-sessions", response_model=list[CompareSessionOut])
def list_compare_sessions(limit: int = Query(50, ge=1, le=200)):
    return svc.list_compare_sessions(limit)
