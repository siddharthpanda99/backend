"""Tests for ExportService — CSV, JSON, and SQL INSERT export formats.

Requires: running PostgreSQL with test data (conftest.py handles setup).
"""
import os
import sys
import json
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Python Libs"))

from common_lib.modules.admin_db.service import ExportService
from common_lib.modules.admin_db.schemas import ExportRequest

TEST_SCHEMA = "test_admin_db_schema"


class TestExportCSV:
    """Integration tests for CSV export."""

    def test_export_csv_basic(self, connection_profile_id, setup_test_table):
        """Test basic CSV export with headers."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="csv",
            include_headers=True,
            max_rows=100,
        ))
        assert resp.success is True
        assert resp.error is None
        assert resp.data is not None
        lines = resp.data.strip().split("\n")
        # Header + 25 rows
        assert len(lines) == 26
        # Header should contain column names
        header = lines[0]
        assert "id" in header
        assert "name" in header
        assert "email" in header

    def test_export_csv_no_headers(self, connection_profile_id, setup_test_table):
        """Test CSV export without headers."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="csv",
            include_headers=False,
            max_rows=100,
        ))
        assert resp.success is True
        lines = resp.data.strip().split("\n")
        # First line should be data, not header
        assert not lines[0].startswith("id,")

    def test_export_csv_special_characters(self, connection_profile_id, setup_test_table):
        """Test CSV export handles commas and quotes in data."""
        from common_lib.modules.admin_db.service import DataBrowserService
        from common_lib.modules.admin_db.schemas import RowInsertRequest

        # Insert row with special chars
        DataBrowserService.insert_row(RowInsertRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            data={"name": 'User, "Special" chars', "age": 99},
        ))

        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="csv",
            include_headers=True,
            max_rows=100,
        ))
        assert resp.success is True
        assert 'User, "Special" chars' in resp.data

    def test_export_csv_row_count(self, connection_profile_id, setup_test_table):
        """Test CSV export returns correct row count."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="csv",
            max_rows=10,
        ))
        assert resp.success is True
        assert resp.row_count == 10


class TestExportJSON:
    """Integration tests for JSON export."""

    def test_export_json_basic(self, connection_profile_id, setup_test_table):
        """Test basic JSON export."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="json",
            max_rows=100,
        ))
        assert resp.success is True
        assert resp.data is not None
        data = json.loads(resp.data)
        assert isinstance(data, list)
        assert len(data) == 25
        assert "id" in data[0]
        assert "name" in data[0]

    def test_export_json_valid_syntax(self, connection_profile_id, setup_test_table):
        """Test JSON output is valid JSON syntax."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="json",
            max_rows=5,
        ))
        assert resp.success is True
        parsed = json.loads(resp.data)
        assert len(parsed) == 5

    def test_export_json_row_count(self, connection_profile_id, setup_test_table):
        """Test JSON export row count."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="json",
            max_rows=3,
        ))
        assert resp.row_count == 3


class TestExportSQL:
    """Integration tests for SQL INSERT export."""

    def test_export_sql_basic(self, connection_profile_id, setup_test_table):
        """Test SQL INSERT export."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="sql",
            max_rows=100,
        ))
        assert resp.success is True
        assert resp.data is not None
        lines = resp.data.strip().split("\n")
        assert len(lines) == 25
        # Each line should be an INSERT statement
        for line in lines:
            assert line.startswith("INSERT INTO")
            assert "VALUES" in line

    def test_export_sql_escapes_quotes(self, connection_profile_id, setup_test_table):
        """Test SQL export properly escapes single quotes."""
        from common_lib.modules.admin_db.service import DataBrowserService
        from common_lib.modules.admin_db.schemas import RowInsertRequest

        DataBrowserService.insert_row(RowInsertRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            data={"name": "O'Brien", "age": 40},
        ))

        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="sql",
            max_rows=30,
        ))
        assert resp.success is True
        # O'Brien should be escaped as O''Brien in SQL
        assert "O''Brien" in resp.data

    def test_export_sql_schema_in_statement(self, connection_profile_id, setup_test_table):
        """Test SQL export includes schema in INSERT statement."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="sql",
            max_rows=1,
        ))
        assert resp.success is True
        assert f'"{TEST_SCHEMA}"' in resp.data
        assert f'"{setup_test_table}"' in resp.data


class TestExportErrors:
    """Test error handling in export service."""

    def test_export_no_table_name(self, connection_profile_id):
        """Test export without table_name returns error."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=None,
            format="csv",
        ))
        assert resp.success is False
        assert resp.error is not None

    def test_export_unsupported_format(self, connection_profile_id, setup_test_table):
        """Test export with unsupported format returns error."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name=setup_test_table,
            format="parquet",
        ))
        assert resp.success is False
        assert "Unsupported format" in resp.error

    def test_export_nonexistent_table(self, connection_profile_id):
        """Test export from nonexistent table returns error."""
        resp = ExportService.export(ExportRequest(
            profile_id=connection_profile_id,
            schema_name=TEST_SCHEMA,
            table_name="nonexistent_xyz",
            format="csv",
        ))
        assert resp.success is False
