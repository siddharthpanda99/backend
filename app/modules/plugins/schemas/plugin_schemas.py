from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from common_lib.modules.plugins.schemas import HealthStatus, PluginType

class PluginResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: str
    version: str
    status: HealthStatus
    plugin_type: PluginType
    node_count: int # Backward compat / Simple display
    total_nodes: int = 0
    active_node_count: int = 0
    author_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    downloads_count: int = 0
    updated_at: str = "2026-04-07"
    author: Optional[str] = "System"
    tags: List[str] = []

class NodeDefinitionSchema(BaseModel):
    id: str
    name: str
    description: Optional[str]
    parameters: Dict[str, Any]

class PluginDetailResponse(PluginResponse):
    nodes: List[NodeDefinitionSchema] = []
    author: Optional[str] = None

class NodeCandidateSchema(BaseModel):
    name: str
    description: Optional[str]
    parameters: Dict[str, Any]
    module_path: str
    approved: bool = False

class OnboardRequest(BaseModel):
    plugin_id: str
    node_candidates: List[NodeCandidateSchema]
    category: str = "general"
    install_deps: bool = False

class PluginUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    author: Optional[str] = None
    author_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[List[str]] = None
