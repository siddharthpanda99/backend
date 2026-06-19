"""
Schema Builder — SQLModel DB Models

Persists schema definitions (tables, columns, relationships, migrations)
to PostgreSQL. Seeded with a clean slate on first startup.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel import SQLModel, Field, Column, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy import DateTime


class SchemaTableRecord(SQLModel, table=True):
    """A database table definition within the schema builder."""
    __tablename__ = "schema_tables"

    id: str = Field(
        primary_key=True, max_length=128,
        description="Unique table ID (UUID)",
    )
    name: str = Field(
        max_length=256, index=True,
        description="Table name (snake_case)",
    )
    description: Optional[str] = Field(
        default=None, sa_column=Column(Text),
    )
    schema_id: str = Field(
        default="default", max_length=128, index=True,
        description="Schema namespace / app_id",
    )
    columns: List[Dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON),
        description="List of column definitions",
    )
    constraints: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON),
        description="Unique constraints, check constraints, indexes",
    )
    metadata_json: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON),
        description="Extra metadata (version, tags, etc.)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )


class SchemaRelationshipRecord(SQLModel, table=True):
    """A foreign key relationship between two tables."""
    __tablename__ = "schema_relationships"

    id: str = Field(
        primary_key=True, max_length=128,
        description="Unique relationship ID (UUID)",
    )
    name: str = Field(
        max_length=256,
        description="Relationship name (auto-suggested)",
    )
    schema_id: str = Field(
        default="default", max_length=128, index=True,
    )
    relation_type: str = Field(
        max_length=16,
        description="one_to_one | one_to_many | many_to_many",
    )
    source_table_id: str = Field(
        max_length=128, index=True,
        description="References schema_tables.id",
    )
    source_column: str = Field(
        max_length=256,
        description="Column name in source table",
    )
    target_table_id: str = Field(
        max_length=128, index=True,
        description="References schema_tables.id",
    )
    target_column: str = Field(
        max_length=256,
        description="Column name in target table",
    )
    on_delete: str = Field(
        default="CASCADE", max_length=32,
        description="CASCADE | SET NULL | RESTRICT | NO ACTION | SET DEFAULT",
    )
    on_update: str = Field(
        default="CASCADE", max_length=32,
    )
    through_table: Optional[str] = Field(
        default=None, max_length=256,
        description="Junction table name (M:N only)",
    )
    inverse_name: Optional[str] = Field(
        default=None, max_length=256,
        description="Reverse accessor name for ORM",
    )
    metadata_json: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )


class SchemaMigrationRecord(SQLModel, table=True):
    """A schema migration with UP/DOWN SQL and execution status."""
    __tablename__ = "schema_migrations"

    id: str = Field(
        primary_key=True, max_length=128,
        description="Unique migration ID (UUID)",
    )
    name: str = Field(
        max_length=256,
        description="Migration name (e.g. 'add_users_table')",
    )
    schema_id: str = Field(
        default="default", max_length=128, index=True,
    )
    version: str = Field(
        max_length=32,
        description="Version string (e.g. '001', timestamp-based)",
    )
    status: str = Field(
        default="pending", max_length=32,
        description="pending | applied | failed | dry_run_passed",
    )
    sql_up: str = Field(
        sa_column=Column(Text),
        description="UP migration SQL",
    )
    sql_down: Optional[str] = Field(
        default=None, sa_column=Column(Text),
        description="DOWN rollback SQL",
    )
    diff_summary: Optional[str] = Field(
        default=None, max_length=1024,
        description="Human-readable summary of changes",
    )
    executed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True)),
    )
    executed_by: Optional[str] = Field(
        default=None, max_length=128,
    )
    duration_ms: Optional[float] = Field(default=None)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))
    scheduled_for: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True)),
    )
    deploy_window_start: Optional[str] = Field(
        default=None, max_length=8,
        description="HH:MM format, e.g. '22:00'",
    )
    deploy_window_end: Optional[str] = Field(
        default=None, max_length=8,
    )
    metadata_json: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
