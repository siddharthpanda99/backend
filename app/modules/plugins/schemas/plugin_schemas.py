from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from common_lib.modules.plugins.schemas import HealthStatus, PluginType


class PluginResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: str
    version: str
    status: HealthStatus
    plugin_type: PluginType
    node_count: int
    total_nodes: int = 0
    active_node_count: int = 0
    author_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    downloads_count: int = 0
    updated_at: str = "2026-04-07"
    author: Optional[str] = "System"
    tags: List[str] = []


class FieldSchema(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    type: Literal[
        "string", "number", "integer", "boolean", "array", "object", "enum", "file"
    ]
    description: str = ""
    required: bool = True
    default: Optional[Any] = None
    enum_values: Optional[List[Any]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    pattern: Optional[str] = None
    items: Optional["FieldSchema"] = None
    properties: Optional[Dict[str, "FieldSchema"]] = None
    ui_widget: Optional[str] = None
    placeholder: Optional[str] = None
    examples: Optional[List[Any]] = None
    deprecated: bool = False


class SchemaObject(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    type: Literal["object"] = "object"
    properties: Dict[str, FieldSchema] = {}
    required: Optional[List[str]] = None


class NodeDefinitionSchema(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    version: str = "1.0.0"
    tags: List[str] = []
    audience: List[Literal["planner", "executor", "system"]] = Field(
        default=["executor"]
    )

    # Use Dict instead of SchemaObject to avoid Pydantic filling defaults
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    execution_timeout: int = 60
    execution_mode: Literal["sync", "async", "stream"] = "sync"

    cacheable: bool = False
    idempotent: bool = False

    # Custom metadata for AI context
    metadata: Optional[Dict[str, Any]] = None


class PluginDetailResponse(PluginResponse):
    nodes: List[NodeDefinitionSchema] = []
    author: Optional[str] = None


class NodeCandidateSchema(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = {}
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
