"""
Schema Builder — ORM Model Generation Route

POST /api/v1/schema/models — auto-generate ORM model code from table definitions
Supports TypeScript (Prisma, Drizzle, TypeORM), Python (SQLAlchemy, Django), Go (GORM).

Each table gets its own model code (not the full schema for every table).
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    SchemaTableRecord, SchemaRelationshipRecord,
    ModelGenerateRequest, ModelGenerateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/models", tags=["Schema Models"])


def _to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in name.split("_"))


def _to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# ─── Prisma Generator (per table) ───────────────────────────────────

def _generate_prisma_model(
    table: SchemaTableRecord,
    relationships: List[SchemaRelationshipRecord],
    table_names: Dict[str, str],
) -> str:
    """Generate a Prisma model for a single table."""
    model_name = _to_pascal(table.name)
    lines = [f"model {model_name} {{"]

    for col in (table.columns or []):
        col_name = col.get("name", "unknown")
        ts_type = _TS_TYPE_MAP.get(col.get("type", "String"), "String")
        optional = "" if not col.get("nullable", True) else "?"
        attrs = []
        if col.get("primary_key"):
            attrs.append("@id")
            if col.get("type") == "UUID":
                attrs.append('@default(uuid())')
        if col.get("default") is not None and not col.get("primary_key"):
            def_val = col["default"]
            if col.get("type") in ("Integer", "BigInteger", "Float", "Decimal"):
                attrs.append(f"@default({def_val})")
            elif def_val.lower() in ("now()", "current_timestamp"):
                attrs.append("@default(now())")
            else:
                attrs.append(f'@default("{def_val}")')
        if col.get("unique"):
            attrs.append("@unique")
        lines.append(f"  {col_name}{optional} {ts_type} {' '.join(attrs)}".rstrip())

    # Add relationship references
    for rel in relationships:
        if rel.source_table_id == table.id:
            target_name = _to_pascal(table_names.get(rel.target_table_id, "Unknown"))
            lines.append(f"  {_to_camel(target_name)} {target_name}? @relation(fields: [{rel.source_column}], references: [{rel.target_column}])")
        if rel.target_table_id == table.id:
            source_name = _to_pascal(table_names.get(rel.source_table_id, "Unknown"))
            lines.append(f"  {_to_camel(source_name)}s {source_name}[]")

    lines.append("}")
    return "\n".join(lines)


# ─── SQLAlchemy Generator (per table) ──────────────────────────────

def _generate_sqlalchemy_model(
    table: SchemaTableRecord,
    relationships: List[SchemaRelationshipRecord],
    table_names: Dict[str, str],
) -> str:
    """Generate a SQLAlchemy model for a single table."""
    model_name = _to_pascal(table.name)
    lines = [
        "from datetime import datetime, date, time",
        "from decimal import Decimal",
        "from typing import Optional, List",
        "from sqlalchemy import Column, String, Integer, BigInteger, Float, Boolean,",
        "    DateTime, Date, Time, Text, JSON, Enum, ForeignKey, Table, UniqueConstraint, Index",
        "from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column",
        "",
        "Base = declarative_base()",
        "",
    ]

    lines.append(f"class {model_name}(Base):")
    lines.append(f'    __tablename__ = "{table.name}"')
    lines.append("")

    for col in (table.columns or []):
        col_name = col.get("name", "unknown")
        py_type = _PYTHON_TYPE_MAP.get(col.get("type", "String"), "str")
        nullable = col.get("nullable", True)
        is_pk = col.get("primary_key", False)

        type_annotation = f"Optional[{py_type}]" if nullable else py_type
        mapped = f"    {col_name}: Mapped[{type_annotation}] = mapped_column("
        if is_pk:
            mapped += "primary_key=True"
        if not nullable:
            if is_pk:
                mapped += ", "
            mapped += "nullable=False"
        mapped += ")"
        lines.append(mapped)

    lines.append("")
    return "\n".join(lines)


# ─── GORM Generator (per table) ────────────────────────────────────

def _generate_gorm_model(
    table: SchemaTableRecord,
    relationships: List[SchemaRelationshipRecord],
    table_names: Dict[str, str],
) -> str:
    """Generate a GORM model for a single table."""
    model_name = _to_pascal(table.name)
    lines = ['package models', '', 'import (', '  "time"', ')', '']

    lines.append(f"// {model_name} maps to the {table.name} table")
    lines.append(f"type {model_name} struct {{")

    for col in (table.columns or []):
        col_name = _to_pascal(col.get("name", "unknown"))
        go_type = _GO_TYPE_MAP.get(col.get("type", "String"), "string")
        gorm_tags = [f"column:{col.get('name', 'unknown')}"]
        if col.get("primary_key"):
            gorm_tags.append("primaryKey")
        if not col.get("nullable", True):
            gorm_tags.append("not null")
        tag = f'`gorm:"{";".join(gorm_tags)}"`'
        lines.append(f"  {col_name} {go_type} {tag}")

    # Add relationship references
    for rel in relationships:
        if rel.source_table_id == table.id:
            target_name = _to_pascal(table_names.get(rel.target_table_id, "Unknown"))
            lines.append(f"  // {target_name} (FK: {rel.source_column} → {rel.target_column})")

    lines.append("}")
    return "\n".join(lines)


# ─── Type Maps ──────────────────────────────────────────────────────

_PYTHON_TYPE_MAP: Dict[str, str] = {
    "String": "str", "Integer": "int", "BigInteger": "int", "Float": "float",
    "Decimal": "Decimal", "Boolean": "bool", "DateTime": "datetime",
    "Date": "date", "Time": "time", "Text": "str", "JSON": "dict",
    "JSONB": "dict", "UUID": "str", "Enum": "str", "Binary": "bytes",
}

_TS_TYPE_MAP: Dict[str, str] = {
    "String": "string", "Integer": "number", "BigInteger": "number",
    "Float": "number", "Decimal": "number", "Boolean": "boolean",
    "DateTime": "Date", "Date": "Date", "Time": "string", "Text": "string",
    "JSON": "Record<string, any>", "JSONB": "Record<string, any>",
    "UUID": "string", "Enum": "string", "Binary": "Buffer",
}

_GO_TYPE_MAP: Dict[str, str] = {
    "String": "string", "Integer": "int", "BigInteger": "int64",
    "Float": "float64", "Decimal": "float64", "Boolean": "bool",
    "DateTime": "time.Time", "Date": "time.Time", "Time": "string",
    "Text": "string", "JSON": "map[string]interface{}",
    "JSONB": "map[string]interface{}", "UUID": "string",
    "Enum": "string", "Binary": "[]byte",
}

_GENERATOR_MAP = {
    "prisma": _generate_prisma_model,
    "drizzle": _generate_prisma_model,
    "typeorm": _generate_prisma_model,
    "sqlalchemy": _generate_sqlalchemy_model,
    "django": _generate_sqlalchemy_model,
    "gorm": _generate_gorm_model,
}


@router.post("/", response_model=ModelGenerateResponse)
async def generate_models(
    data: ModelGenerateRequest,
    db: Session = Depends(get_session),
):
    """Generate per-table ORM model code from table definitions."""
    if not data.tables:
        raise HTTPException(status_code=400, detail="No tables specified")

    tables = []
    for table_id in data.tables:
        table = db.execute(
            select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
        ).scalar_one_or_none()
        if not table:
            raise HTTPException(status_code=404, detail=f"Table with ID '{table_id}' not found")
        tables.append(table)

    # Get relationships for these tables
    table_ids = [t.id for t in tables]
    relationships = db.execute(
        select(SchemaRelationshipRecord).where(
            (SchemaRelationshipRecord.source_table_id.in_(table_ids)) |
            (SchemaRelationshipRecord.target_table_id.in_(table_ids))
        )
    ).scalars().all()

    table_names = {t.id: t.name for t in tables}
    generator = _GENERATOR_MAP.get(data.framework, _generate_prisma_model)

    # Generate per-table model code
    models: Dict[str, str] = {}
    for table in tables:
        table_rels = [
            r for r in relationships
            if r.source_table_id == table.id or r.target_table_id == table.id
        ]
        code = generator(table, table_rels, table_names)
        models[table.name] = code

    logger.info(
        f"Generated {data.framework} models for {len(tables)} table(s)"
    )
    return ModelGenerateResponse(
        models=models,
        language=data.language,
        framework=data.framework,
        table_count=len(tables),
    )
