"""
schema/routes/router.py — Schema Migration Dry-Run API

Provides a POST /dry-run endpoint that validates SQL migration statements
against the connected PostgreSQL database without committing any changes.

Strategy:
  - Each SQL statement is wrapped in BEGIN; ... ROLLBACK; and executed in
    a separate connection. PostgreSQL supports transactional DDL (CREATE
    TABLE, ALTER TABLE, DROP TABLE, CREATE INDEX, etc.), so the changes
    are safely rolled back.
  - Non-transactional statements (CREATE INDEX CONCURRENTLY, VACUUM, etc.)
    are flagged as warnings.
  - A statement_timeout of 10s prevents runaway queries.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, DatabaseError, SQLAlchemyError

from common_lib.modules.data_storage.database.connection import engine as db_engine

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Request / Response Schemas ─────────────────────────────────────

class DryRunRequest(BaseModel):
    sql: str = Field(..., description="The SQL migration text to validate")


class DryRunResponse(BaseModel):
    success: bool
    issues: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    affected_tables: list[str] = []


# ─── SQL Parsing Helpers ────────────────────────────────────────────

# Regex to identify DDL operations that affect specific tables
_DDL_TABLE_PATTERN = re.compile(
    r"(?:CREATE\s+(?:TABLE|INDEX|SEQUENCE|VIEW)|"
    r"ALTER\s+TABLE|DROP\s+TABLE|TRUNCATE\s+TABLE|"
    r"CREATE\s+OR\s+REPLACE\s+VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:\w+\.)?(\w+)",
    re.IGNORECASE,
)

# Statements that PostgreSQL cannot roll back
_NON_TRANSACTIONAL_KEYWORDS = re.compile(
    r"(CREATE\s+INDEX\s+CONCURRENTLY|"
    r"DROP\s+DATABASE|CREATE\s+DATABASE|"
    r"VACUUM|REINDEX|CLUSTER|"
    r"CREATE\s+TABLESPACE|DROP\s+TABLESPACE|"
    r"CREATE\s+SUBSCRIPTION|ALTER\s+SUBSCRIPTION|DROP\s+SUBSCRIPTION)",
    re.IGNORECASE,
)


def _split_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements."""
    # Remove single-line comments
    cleaned = re.sub(r"--[^\n]*", "", sql)
    # Remove multi-line comments
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    # Split on semicolons and filter empty/whitespace
    stmts = [s.strip() for s in cleaned.split(";") if s.strip()]
    return stmts


def _extract_table_names(statement: str) -> list[str]:
    """Extract referenced table names from a DDL/DML statement."""
    tables: list[str] = []
    for match in _DDL_TABLE_PATTERN.finditer(statement):
        tables.append(match.group(1))
    return tables


def _is_select_only(statement: str) -> bool:
    """Check if a statement is a read-only SELECT (safe to EXPLAIN)."""
    upper = statement.strip().upper()
    return upper.startswith("SELECT") and not any(
        kw in upper
        for kw in ["INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TRUNCATE"]
    )


def _check_syntax_only(sql: str) -> list[str]:
    """
    Quick local syntax checks before hitting the database.
    Returns a list of issues found (empty = no issues).
    """
    issues: list[str] = []
    stmts = _split_statements(sql)

    if not stmts:
        issues.append("SQL text is empty or contains only comments")

    for i, stmt in enumerate(stmts):
        if not re.match(r"^\s*(CREATE|ALTER|DROP|TRUNCATE|INSERT|UPDATE|DELETE|SELECT|BEGIN|COMMIT|ROLLBACK|SET|GRANT|REVOKE|ANALYZE|EXPLAIN)", stmt, re.IGNORECASE):
            issues.append(f"Statement {i+1} does not start with a recognized SQL keyword")

        # Check for dangling DDL pattern (no table name)
        if re.match(r"^\s*(ALTER|DROP|TRUNCATE)\s+TABLE\s*;?\s*$", stmt, re.IGNORECASE):
            issues.append(f"Statement {i+1}: ALTER/DROP/TRUNCATE TABLE without a table name")

    return issues


# ─── Main Validation Logic ──────────────────────────────────────────

def _validate_via_rollback(statement: str) -> dict[str, Any]:
    """
    Execute a single SQL statement inside BEGIN; ... ROLLBACK; to validate
    it against the live schema without committing.

    Returns:
        { "errors": [...], "warnings": [...], "affected_tables": [...] }
    """
    errors: list[str] = []
    warnings: list[str] = []
    affected_tables: list[str] = _extract_table_names(statement)

    # Check for non-transactional operations
    if _NON_TRANSACTIONAL_KEYWORDS.search(statement):
        warnings.append(
            "Statement uses non-transactional DDL (e.g. CREATE INDEX CONCURRENTLY). "
            "Dry-run cannot fully validate this — review manually."
        )
        # Still try the rollback validation; it may fail but we record what we can
        warnings.append("Proceeding with rollback validation (may still fail on non-transactional DDL)")

    # Build wrapped SQL
    wrapped = f"BEGIN;\nSET LOCAL statement_timeout = '10000';\n{statement}\nROLLBACK;"

    try:
        # Use a raw connection (not a transaction-managed session) so we control
        # the BEGIN/ROLLBACK lifecycle ourselves.
        with db_engine.connect() as conn:
            conn.execute(text(wrapped))

        # If no exception, the statement parsed and executed successfully (then rolled back)
        logger.debug("Dry-run OK for statement: %.80s", statement)

    except ProgrammingError as e:
        # SQL syntax or schema errors
        err_msg = _extract_pg_error(str(e))
        errors.append(f"SQL error: {err_msg}")
    except DatabaseError as e:
        err_msg = _extract_pg_error(str(e))
        errors.append(f"Database error: {err_msg}")
    except SQLAlchemyError as e:
        errors.append(f"Validation error: {_extract_pg_error(str(e))}")

    return {
        "errors": errors,
        "warnings": warnings,
        "affected_tables": affected_tables,
    }


def _extract_pg_error(raw: str) -> str:
    """
    Extract the most relevant part of a PostgreSQL error message.
    The raw SQLAlchemy exception typically contains the full PG error detail.
    """
    # Try to extract the DETAIL or HINT line first
    for prefix in ("DETAIL: ", "HINT: ", "ERROR: "):
        idx = raw.find(prefix)
        if idx != -1:
            end = raw.find("\n", idx)
            return raw[idx:end] if end != -1 else raw[idx:].strip()

    # Fallback: return the last meaningful line
    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    for line in reversed(lines):
        if line.startswith("ERROR:"):
            return line
    # Last resort: truncate to 200 chars
    return raw[:200]


# ─── Batch Dry-Run ──────────────────────────────────────────────────

def _batch_validate(migrations: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Validate multiple migration SQLs sequentially.

    Each migration dict has { "id": str, "name": str, "sql": str }.
    Returns a list of per-migration results with the same keys as _validate_via_rollback.
    """
    results: list[dict[str, Any]] = []
    for m in migrations:
        sql = m.get("sql", "")
        name = m.get("name", "unknown")
        mid = m.get("id", "")

        # Phase 1: local syntax checks
        local_issues = _check_syntax_only(sql)
        if local_issues:
            results.append({
                "id": mid,
                "name": name,
                "success": False,
                "issues": local_issues,
                "warnings": [],
                "errors": ["Local syntax validation failed"],
                "affected_tables": [],
            })
            continue

        # Phase 2: database-backed rollback validation
        combined_errors: list[str] = []
        combined_warnings: list[str] = []
        all_tables: list[str] = []
        stmts = _split_statements(sql)

        for stmt in stmts:
            result = _validate_via_rollback(stmt)
            combined_errors.extend(result["errors"])
            combined_warnings.extend(result["warnings"])
            all_tables.extend(result["affected_tables"])

        # Also attempt EXPLAIN for SELECT-only statements to verify relation names
        for stmt in stmts:
            if _is_select_only(stmt):
                try:
                    with db_engine.connect() as conn:
                        conn.execute(text(f"EXPLAIN (FORMAT JSON) {stmt}"))
                except Exception as e:
                    combined_warnings.append(f"EXPLAIN warning for SELECT: {_extract_pg_error(str(e))}")

        results.append({
            "id": mid,
            "name": name,
            "success": len(combined_errors) == 0,
            "issues": [],
            "warnings": combined_warnings,
            "errors": combined_errors,
            "affected_tables": list(dict.fromkeys(all_tables)),  # dedup, preserve order
        })

    return results


# ─── Endpoints ──────────────────────────────────────────────────────

@router.post("/dry-run", response_model=DryRunResponse)
async def dry_run_migration(request: DryRunRequest):
    """
    Validate a single migration SQL against the connected database schema.

    The SQL is executed inside BEGIN; ... ROLLBACK; so no changes persist.
    Returns validation errors, warnings, and a list of affected tables.
    """
    sql = request.sql.strip()
    if not sql:
        return DryRunResponse(
            success=False,
            errors=["SQL text is empty"],
        )

    # Phase 1: local syntax checks
    local_issues = _check_syntax_only(sql)
    if local_issues:
        has_critical = any("empty" in issue.lower() or "without a table name" in issue.lower() for issue in local_issues)
        return DryRunResponse(
            success=not has_critical,
            issues=local_issues,
            warnings=[],
            errors=[] if not has_critical else ["Local syntax validation detected critical issues"],
        )

    # Phase 2: database-backed rollback validation for each statement
    all_errors: list[str] = []
    all_warnings: list[str] = []
    all_tables: list[str] = []
    stmts = _split_statements(sql)

    for stmt in stmts:
        result = _validate_via_rollback(stmt)
        all_errors.extend(result["errors"])
        all_warnings.extend(result["warnings"])
        all_tables.extend(result["affected_tables"])

    # Also attempt EXPLAIN for SELECT-only statements to verify relation names
    for stmt in stmts:
        if _is_select_only(stmt):
            try:
                with db_engine.connect() as conn:
                    conn.execute(text(f"EXPLAIN (FORMAT JSON) {stmt}"))
            except Exception as e:
                all_warnings.append(f"EXPLAIN warning for SELECT: {_extract_pg_error(str(e))}")

    deduped_tables = list(dict.fromkeys(all_tables))

    return DryRunResponse(
        success=len(all_errors) == 0,
        issues=[f"Validated {len(stmts)} statement(s)"],
        warnings=all_warnings,
        errors=all_errors,
        affected_tables=deduped_tables,
    )


@router.post("/batch-dry-run")
async def batch_dry_run_migrations(payload: dict):
    """
    Validate multiple migration SQLs against the connected database.

    Request body: { "migrations": [{ "id": "...", "name": "...", "sql": "..." }] }

    Returns a list of per-migration results, each with the same schema as
    the single dry-run endpoint.
    """
    migrations = payload.get("migrations", [])
    if not migrations:
        return []

    results = _batch_validate(migrations)
    return results
