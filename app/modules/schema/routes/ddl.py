"""
Schema Builder — DDL Generation Route

POST /api/v1/schema/ddl — generates CREATE TABLE SQL from schema definitions
Supports PostgreSQL, MySQL, and SQLite dialects.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from ..models import SchemaTableRecord, SchemaRelationshipRecord
from ..schemas import DDLGenerateRequest, DDLGenerateResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ddl", tags=["Schema DDL"])


# ─── Type Mapping ───────────────────────────────────────────────────

_TYPE_MAP: Dict[str, Dict[str, str]] = {
    "postgresql": {
        "String": "VARCHAR(255)",
        "Integer": "INTEGER",
        "BigInteger": "BIGINT",
        "Float": "FLOAT",
        "Decimal": "DECIMAL(10,2)",
        "Boolean": "BOOLEAN",
        "DateTime": "TIMESTAMP WITH TIME ZONE",
        "Date": "DATE",
        "Time": "TIME",
        "Text": "TEXT",
        "JSON": "JSONB",
        "JSONB": "JSONB",
        "UUID": "UUID",
        "Binary": "BYTEA",
    },
    "mysql": {
        "String": "VARCHAR(255)",
        "Integer": "INT",
        "BigInteger": "BIGINT",
        "Float": "FLOAT",
        "Decimal": "DECIMAL(10,2)",
        "Boolean": "TINYINT(1)",
        "DateTime": "DATETIME",
        "Date": "DATE",
        "Time": "TIME",
        "Text": "TEXT",
        "JSON": "JSON",
        "JSONB": "JSON",
        "UUID": "CHAR(36)",
        "Binary": "BLOB",
    },
    "sqlite": {
        "String": "TEXT",
        "Integer": "INTEGER",
        "BigInteger": "INTEGER",
        "Float": "REAL",
        "Decimal": "REAL",
        "Boolean": "INTEGER",
        "DateTime": "TEXT",
        "Date": "TEXT",
        "Time": "TEXT",
        "Text": "TEXT",
        "JSON": "TEXT",
        "JSONB": "TEXT",
        "UUID": "TEXT",
        "Binary": "BLOB",
    },
}


def _map_type(col_type: str, dialect: str) -> str:
    """Map a generic column type to dialect-specific SQL type."""
    type_map = _TYPE_MAP.get(dialect, _TYPE_MAP["postgresql"])
    sql_type = type_map.get(col_type, col_type)

    # Handle Enum specially
    if col_type == "Enum" and dialect == "postgresql":
        return "VARCHAR(50)"  # PostgreSQL enums need CREATE TYPE; use VARCHAR for simplicity

    return sql_type


def _escape_name(name: str, dialect: str) -> str:
    """Quote identifier names per dialect."""
    if dialect == "mysql":
        return f"`{name}`"
    return f'"{name}"'


def _generate_ddl_for_table(
    table: SchemaTableRecord,
    relationships: List[SchemaRelationshipRecord],
    dialect: str,
    table_name_map: Dict[str, str] = None,
) -> str:
    """Generate CREATE TABLE SQL for a single table."""
    lines = []
    table_name = _escape_name(table.name, dialect)
    lines.append(f"CREATE TABLE {table_name} (")
    cols: List[str] = []
    pk_columns = []

    for col in (table.columns or []):
        col_name = _escape_name(col.get("name", "unknown"), dialect)
        sql_type = _map_type(col.get("type", "String"), dialect)

        # Handle Enum with inline values
        if col.get("type") == "Enum" and col.get("enum_values"):
            if dialect == "postgresql":
                sql_type = f"VARCHAR(50)"  # We'd normally do CREATE TYPE, simplified here
            elif dialect == "mysql":
                vals = ",".join(f"'{v}'" for v in col["enum_values"])
                sql_type = f"ENUM({vals})"

        col_def = f"  {col_name} {sql_type}"

        if not col.get("nullable", True):
            col_def += " NOT NULL"
        if col.get("default") is not None:
            default_val = col["default"]
            # Handle special defaults
            if default_val.lower() in ("now()", "current_timestamp"):
                col_def += f" DEFAULT {default_val}"
            elif col.get("type") in ("Integer", "BigInteger", "Float", "Decimal"):
                col_def += f" DEFAULT {default_val}"
            else:
                col_def += f" DEFAULT '{default_val}'"
        if col.get("unique"):
            col_def += " UNIQUE"
        if col.get("primary_key"):
            pk_columns.append(col_name)

        cols.append(col_def)

    # Add primary key constraint
    if pk_columns:
        pk_def = f"  PRIMARY KEY ({', '.join(pk_columns)})"
        cols.append(pk_def)

    # Add unique constraints
    constraints = table.constraints or {}
    for uc in (constraints.get("unique_constraints") or []):
        uc_cols = [_escape_name(c, dialect) for c in uc.get("columns", [])]
        if uc_cols:
            cols.append(f"  CONSTRAINT {_escape_name(uc.get('name', 'uq'), dialect)} UNIQUE ({', '.join(uc_cols)})")

    # Add check constraints
    for cc in (constraints.get("check_constraints") or []):
        name = _escape_name(cc.get("name", "chk"), dialect)
        expr = cc.get("expression", "1=1")
        cols.append(f"  CONSTRAINT {name} CHECK ({expr})")

    lines.append(",\n".join(cols))
    lines.append(");\n")

    # Add indexes
    for idx in (constraints.get("indexes") or []):
        idx_name = _escape_name(idx.get("name", f"idx_{table.name}"), dialect)
        idx_cols = [_escape_name(c, dialect) for c in idx.get("columns", [])]
        if idx_cols:
            idx_type = idx.get("type", "")
            if idx_type:
                idx_type = f" USING {idx_type}"
            lines.append(f"CREATE INDEX {idx_name} ON {table_name}{idx_type} ({', '.join(idx_cols)});")

    # Add foreign keys from relationships
    for rel in relationships:
        if rel.source_table_id == table.id:
            target_name = (table_name_map or {}).get(
                rel.target_table_id, f"target_{rel.id[:8]}"
            )
            target_escaped = _escape_name(target_name, dialect)
            lines.append(
                f"ALTER TABLE {table_name} ADD FOREIGN KEY ({_escape_name(rel.source_column, dialect)}) "
                f"REFERENCES {target_escaped} ({_escape_name(rel.target_column, dialect)}) "
                f"ON DELETE {rel.on_delete} ON UPDATE {rel.on_update};"
            )

    return "\n".join(lines)


@router.post("/", response_model=DDLGenerateResponse)
async def generate_ddl(
    data: DDLGenerateRequest,
    db: Session = Depends(get_session),
):
    """Generate DDL CREATE TABLE SQL from table IDs and dialect."""
    if not data.tables:
        raise HTTPException(status_code=400, detail="No tables specified")

    tables = []
    for table_id in data.tables:
        table = db.execute(
            select(SchemaTableRecord).where(SchemaTableRecord.id == table_id)
        ).scalar_one_or_none()
        if not table:
            raise HTTPException(
                status_code=404,
                detail=f"Table with ID '{table_id}' not found",
            )
        tables.append(table)

    # Get all relationships for these tables
    table_ids = [t.id for t in tables]
    relationships = db.execute(
        select(SchemaRelationshipRecord).where(
            SchemaRelationshipRecord.source_table_id.in_(table_ids)
        )
    ).scalars().all()

    # Build a name map for FK references
    table_name_map = {t.id: t.name for t in tables}

    sql_parts = []
    for table in tables:
        # Filter relationships relevant to this table
        table_rels = [r for r in relationships if r.source_table_id == table.id]

        # Generate DDL with table name map for FK resolution
        ddl = _generate_ddl_for_table(table, table_rels, data.dialect, table_name_map)
        sql_parts.append(ddl)

    full_sql = "\n".join(sql_parts)
    logger.info(f"Generated {data.dialect.upper()} DDL for {len(tables)} table(s)")

    return DDLGenerateResponse(
        sql=full_sql,
        dialect=data.dialect,
        tables=[t.name for t in tables],
    )
