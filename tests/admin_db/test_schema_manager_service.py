"""Tests for SchemaManagerService — DDL operations (CREATE/DROP table, indexes, schemas).

Requires: running PostgreSQL (conftest.py handles setup).
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Python Libs"))

from common_lib.modules.admin_db.service import SchemaManagerService
from common_lib.modules.admin_db.schemas import (
    CreateTableRequest, DropTableRequest, CreateIndexRequest, CreateSchemaRequest,
)
from sqlalchemy import create_engine, text, inspect as sa_inspect
from sqlalchemy.pool import NullPool

TEST_SCHEMA = "test_admin_db_schema"
DB_HOST = os.environ.get("TEST_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("TEST_DB_PORT", "5432"))
DB_NAME = os.environ.get("TEST_DB_NAME", "test_admin_db")
DB_USER = os.environ.get("TEST_DB_USER", "postgres")
DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "postgres")


class TestCreateTable:
    """Integration tests for SchemaManagerService.create_table."""

    def test_create_table_basic(self, connection_profile_id, db_engine):
        """Test creating a simple table with 3 columns."""
        table_name = "test_create_basic"
        resp = SchemaManagerService.create_table(CreateTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
            columns=[
                {"name": "id", "type": "SERIAL", "nullable": False, "is_pk": True},
                {"name": "name", "type": "VARCHAR(100)", "nullable": False},
                {"name": "email", "type": "VARCHAR(200)", "nullable": True},
            ],
        ))
        assert resp.success is True
        assert resp.sql is not None
        assert "CREATE TABLE" in resp.sql

        # Verify table exists
        with db_engine.connect() as conn:
            inspector = sa_inspect(conn)
            tables = inspector.get_table_names(schema=TEST_SCHEMA)
            assert table_name in tables

            # Verify columns
            cols = inspector.get_columns(table_name, schema=TEST_SCHEMA)
            col_names = [c["name"] for c in cols]
            assert "id" in col_names
            assert "name" in col_names
            assert "email" in col_names

        # Cleanup
        SchemaManagerService.drop_table(DropTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
            cascade=True,
        ))

    def test_create_table_with_not_null(self, connection_profile_id, db_engine):
        """Test creating a table with NOT NULL constraints."""
        table_name = "test_create_notnull"
        resp = SchemaManagerService.create_table(CreateTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
            columns=[
                {"name": "id", "type": "SERIAL", "nullable": False, "is_pk": True},
                {"name": "required_field", "type": "TEXT", "nullable": False},
                {"name": "optional_field", "type": "TEXT", "nullable": True},
            ],
        ))
        assert resp.success is True

        # Verify NOT NULL constraint
        with db_engine.connect() as conn:
            inspector = sa_inspect(conn)
            cols = inspector.get_columns(table_name, schema=TEST_SCHEMA)
            required_col = [c for c in cols if c["name"] == "required_field"][0]
            optional_col = [c for c in cols if c["name"] == "optional_field"][0]
            assert required_col["nullable"] is False
            assert optional_col["nullable"] is True

        # Cleanup
        SchemaManagerService.drop_table(DropTableRequest(
            profile_id=connection_profile_id, schema_name=TEST_SCHEMA,
            table_name=table_name, cascade=True,
        ))

    def test_create_table_sql_preview(self, connection_profile_id):
        """Test SQL preview without actually creating the table."""
        resp = SchemaManagerService.create_table(CreateTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name="should_not_exist",
            columns=[
                {"name": "id", "type": "INTEGER", "nullable": False},
            ],
            sql_preview_only=True,
        ))
        assert resp.success is True
        assert resp.sql is not None
        assert "CREATE TABLE" in resp.sql
        assert "should_not_exist" in resp.sql

    def test_create_table_invalid_identifier_rejected(self, connection_profile_id):
        """Test that injection via table name is rejected."""
        resp = SchemaManagerService.create_table(CreateTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name="bad; DROP TABLE users",
            columns=[{"name": "id", "type": "INTEGER"}],
        ))
        assert resp.success is False


class TestDropTable:
    """Integration tests for SchemaManagerService.drop_table."""

    def test_drop_table(self, connection_profile_id, db_engine):
        """Test dropping a table."""
        table_name = "test_drop_me"
        # Create first
        SchemaManagerService.create_table(CreateTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
            columns=[{"name": "id", "type": "INTEGER"}],
        ))

        # Drop
        resp = SchemaManagerService.drop_table(DropTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
        ))
        assert resp.success is True

        # Verify gone
        with db_engine.connect() as conn:
            inspector = sa_inspect(conn)
            tables = inspector.get_table_names(schema=TEST_SCHEMA)
            assert table_name not in tables

    def test_drop_table_with_cascade(self, connection_profile_id, db_engine):
        """Test dropping a table with CASCADE."""
        table_name = "test_drop_cascade"
        SchemaManagerService.create_table(CreateTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
            columns=[{"name": "id", "type": "INTEGER"}],
        ))
        resp = SchemaManagerService.drop_table(DropTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
            cascade=True,
        ))
        assert resp.success is True

    def test_drop_table_sql_preview(self, connection_profile_id):
        """Test drop table SQL preview."""
        resp = SchemaManagerService.drop_table(DropTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name="preview_drop",
            sql_preview_only=True,
        ))
        assert resp.success is True
        assert "DROP TABLE" in resp.sql


class TestCreateIndex:
    """Integration tests for SchemaManagerService.create_index."""

    def test_create_index(self, connection_profile_id, db_engine):
        """Test creating an index on a table."""
        table_name = "test_idx_table"
        # Create table
        SchemaManagerService.create_table(CreateTableRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
            columns=[
                {"name": "id", "type": "SERIAL", "nullable": False, "is_pk": True},
                {"name": "email", "type": "VARCHAR(200)"},
            ],
        ))

        # Create index
        resp = SchemaManagerService.create_index(CreateIndexRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=table_name,
            index_name=f"idx_{table_name}_email",
            columns=["email"],
            unique=True,
        ))
        assert resp.success is True

        # Verify index exists
        with db_engine.connect() as conn:
            inspector = sa_inspect(conn)
            indexes = inspector.get_indexes(table_name, schema=TEST_SCHEMA)
            idx_names = [i["name"] for i in indexes]
            assert f"idx_{table_name}_email" in idx_names

        # Cleanup
        SchemaManagerService.drop_table(DropTableRequest(
            profile_id=connection_profile_id, schema_name=TEST_SCHEMA,
            table_name=table_name, cascade=True,
        ))

    def test_create_index_sql_preview(self, connection_profile_id):
        """Test create index SQL preview."""
        resp = SchemaManagerService.create_index(CreateIndexRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name="some_table",
            columns=["col1", "col2"],
            sql_preview_only=True,
        ))
        assert resp.success is True
        assert "CREATE" in resp.sql
        assert "INDEX" in resp.sql


class TestCreateSchema:
    """Integration tests for SchemaManagerService.create_schema."""

    def test_create_schema(self, connection_profile_id, db_engine):
        """Test creating a new schema."""
        schema_name = f"test_new_schema_{__import__('uuid').uuid4().hex[:6]}"
        resp = SchemaManagerService.create_schema(CreateSchemaRequest(
            profile_id=connection_profile_id,
            schema_name=schema_name,
        ))
        assert resp.success is True

        # Verify schema exists
        with db_engine.connect() as conn:
            inspector = sa_inspect(conn)
            schemas = inspector.get_schema_names()
            assert schema_name in schemas

        # Cleanup
        with db_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            conn.commit()

    def test_create_schema_sql_preview(self, connection_profile_id):
        """Test create schema SQL preview."""
        resp = SchemaManagerService.create_schema(CreateSchemaRequest(
            profile_id=connection_profile_id,
            schema_name="preview_schema",
            sql_preview_only=True,
        ))
        assert resp.success is True
        assert "CREATE SCHEMA" in resp.sql
