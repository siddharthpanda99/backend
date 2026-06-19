"""
Schema Builder — Pydantic Schemas for API request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Table Schemas ──────────────────────────────────────────────────

class ColumnDef(BaseModel):
    name: str
    type: str = "String"
    nullable: bool = True
    default: Optional[str] = None
    primary_key: bool = False
    unique: bool = False
    index: bool = False
    enum_values: Optional[List[str]] = None
    is_computed: bool = False
    computed_expr: Optional[str] = None
    description: Optional[str] = None


class TableConstraints(BaseModel):
    unique_constraints: Optional[List[Dict[str, Any]]] = None
    check_constraints: Optional[List[Dict[str, Any]]] = None
    indexes: Optional[List[Dict[str, Any]]] = None


class TableCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    schema_id: str = "default"
    columns: List[ColumnDef] = []
    constraints: Optional[TableConstraints] = None


class TableUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    columns: Optional[List[ColumnDef]] = None
    constraints: Optional[TableConstraints] = None


class TableResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    schema_id: str
    columns: List[ColumnDef] = []
    constraints: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TableListResponse(BaseModel):
    items: List[TableResponse]
    total: int = 0


# ─── Column (sub-resource) Schemas ──────────────────────────────────

class ColumnCreate(BaseModel):
    table_id: str
    column: ColumnDef


class ColumnUpdate(BaseModel):
    column: ColumnDef


# ─── Relationship Schemas ───────────────────────────────────────────

class RelationshipCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    schema_id: str = "default"
    relation_type: str = Field(..., pattern=r"^(one_to_one|one_to_many|many_to_many)$")
    source_table_id: str
    source_column: str
    target_table_id: str
    target_column: str
    on_delete: str = "CASCADE"
    on_update: str = "CASCADE"
    through_table: Optional[str] = None
    inverse_name: Optional[str] = None


class RelationshipUpdate(BaseModel):
    name: Optional[str] = None
    relation_type: Optional[str] = None
    source_table_id: Optional[str] = None
    source_column: Optional[str] = None
    target_table_id: Optional[str] = None
    target_column: Optional[str] = None
    on_delete: Optional[str] = None
    on_update: Optional[str] = None
    through_table: Optional[str] = None
    inverse_name: Optional[str] = None


class RelationshipResponse(BaseModel):
    id: str
    name: str
    schema_id: str
    relation_type: str
    source_table_id: str
    source_column: str
    target_table_id: str
    target_column: str
    on_delete: str
    on_update: str
    through_table: Optional[str] = None
    inverse_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RelationshipListResponse(BaseModel):
    items: List[RelationshipResponse]
    total: int = 0


# ─── Migration Schemas ──────────────────────────────────────────────

class MigrationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    schema_id: str = "default"
    version: str = Field(..., min_length=1, max_length=32)
    sql_up: str
    sql_down: Optional[str] = None
    diff_summary: Optional[str] = None


class MigrationUpdate(BaseModel):
    name: Optional[str] = None
    sql_up: Optional[str] = None
    sql_down: Optional[str] = None
    diff_summary: Optional[str] = None
    scheduled_for: Optional[str] = None
    deploy_window_start: Optional[str] = None
    deploy_window_end: Optional[str] = None
    status: Optional[str] = None


class MigrationResponse(BaseModel):
    id: str
    name: str
    schema_id: str
    version: str
    status: str
    sql_up: str
    sql_down: Optional[str] = None
    diff_summary: Optional[str] = None
    executed_at: Optional[datetime] = None
    executed_by: Optional[str] = None
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    deploy_window_start: Optional[str] = None
    deploy_window_end: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MigrationListResponse(BaseModel):
    items: List[MigrationResponse]
    total: int = 0


# ─── DDL Generation Schemas ─────────────────────────────────────────

class DDLGenerateRequest(BaseModel):
    tables: List[str] = Field(..., description="List of table IDs to generate DDL for")
    dialect: str = Field("postgresql", pattern=r"^(postgresql|mysql|sqlite)$")


class DDLGenerateResponse(BaseModel):
    sql: str
    dialect: str
    tables: List[str]


# ─── ORM Model Generation Schemas ──────────────────────────────────

class ModelGenerateRequest(BaseModel):
    tables: List[str] = Field(..., description="List of table IDs to generate models for")
    language: str = Field("typescript", pattern=r"^(typescript|python|go)$")
    framework: str = Field("prisma", pattern=r"^(prisma|drizzle|typeorm|sqlalchemy|django|gorm)$")


class ModelGenerateResponse(BaseModel):
    models: Dict[str, str] = Field(..., description="Map of table_name -> generated code")
    language: str
    framework: str
    table_count: int


# ─── Common Response ────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    message: str = "OK"
    error: Optional[str] = None
