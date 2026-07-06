"""Tests for DataBrowserService — paginated data browsing with CRUD operations.

Requires: running PostgreSQL with test data (conftest.py handles setup).
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Python Libs"))

from common_lib.modules.admin_db.service import DataBrowserService, _validate_identifier
from common_lib.modules.admin_db.schemas import (
    DataBrowserRequest, RowInsertRequest, RowUpdateRequest, RowDeleteRequest,
)

TEST_SCHEMA = "test_admin_db_schema"


class TestValidateIdentifier:
    """Unit tests for the _validate_identifier helper (no DB needed)."""

    def test_valid_identifiers(self):
        assert _validate_identifier("users") == "users"
        assert _validate_identifier("my_table_123") == "my_table_123"
        assert _validate_identifier("_private") == "_private"
        assert _validate_identifier("CamelCase") == "CamelCase"

    def test_invalid_identifiers(self):
        with pytest.raises(ValueError):
            _validate_identifier("123bad")
        with pytest.raises(ValueError):
            _validate_identifier("has space")
        with pytest.raises(ValueError):
            _validate_identifier("has-dash")
        with pytest.raises(ValueError):
            _validate_identifier("'; DROP TABLE users; --")


class TestFetchData:
    """Integration tests for DataBrowserService.fetch_data."""

    def test_fetch_all_rows(self, connection_profile_id, setup_test_table):
        """Fetch all rows from a table."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            page=1,
            page_size=100,
        ))
        assert resp.error is None
        assert resp.total_rows == 25
        assert len(resp.rows) == 25
        assert "id" in resp.columns
        assert "name" in resp.columns
        assert "email" in resp.columns

    def test_fetch_pagination(self, connection_profile_id, setup_test_table):
        """Test pagination returns correct page and total."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            page=1,
            page_size=10,
        ))
        assert resp.total_rows == 25
        assert len(resp.rows) == 10
        assert resp.page == 1
        assert resp.page_size == 10

        # Page 3 should have 5 rows
        resp3 = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            page=3,
            page_size=10,
        ))
        assert resp3.total_rows == 25
        assert len(resp3.rows) == 5

    def test_fetch_sort_ascending(self, connection_profile_id, setup_test_table):
        """Test sorting by column ascending."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            sort_column="age",
            sort_direction="ASC",
            page_size=25,
        ))
        ages = [r["age"] for r in resp.rows]
        assert ages == sorted(ages)

    def test_fetch_sort_descending(self, connection_profile_id, setup_test_table):
        """Test sorting by column descending."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            sort_column="age",
            sort_direction="DESC",
            page_size=25,
        ))
        ages = [r["age"] for r in resp.rows]
        assert ages == sorted(ages, reverse=True)

    def test_fetch_with_equals_filter(self, connection_profile_id, setup_test_table):
        """Test filter with = operator."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "active", "op": "=", "value": True}],
            page_size=100,
        ))
        assert resp.error is None
        assert resp.total_rows > 0
        assert all(r["active"] is True for r in resp.rows)

    def test_fetch_with_like_filter(self, connection_profile_id, setup_test_table):
        """Test filter with LIKE operator."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "name", "op": "LIKE", "value": "User 1"}],
            page_size=100,
        ))
        assert resp.error is None
        assert all("User 1" in r["name"] for r in resp.rows)

    def test_fetch_with_search(self, connection_profile_id, setup_test_table):
        """Test global search across all columns."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            search="user5@example.com",
            page_size=100,
        ))
        assert resp.error is None
        assert resp.total_rows == 1
        assert resp.rows[0]["email"] == "user5@example.com"

    def test_fetch_with_compound_filters(self, connection_profile_id, setup_test_table):
        """Test multiple filters combined with AND."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[
                {"column": "active", "op": "=", "value": True},
                {"column": "age", "op": ">=", "value": 30},
            ],
            page_size=100,
        ))
        assert resp.error is None
        assert all(r["active"] is True and r["age"] >= 30 for r in resp.rows)

    def test_fetch_with_is_null_filter(self, connection_profile_id, setup_test_table):
        """Test IS NULL filter."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "email", "op": "IS NULL"}],
            page_size=100,
        ))
        assert resp.error is None
        # All rows have emails, so 0 results
        assert resp.total_rows == 0

    def test_fetch_invalid_identifier_rejected(self, connection_profile_id):
        """Test that injection via table name is rejected."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table="bad table'; DROP TABLE users; --",
            page_size=10,
        ))
        assert resp.error is not None

    def test_fetch_injection_via_filter_column_rejected(self, connection_profile_id, setup_test_table):
        """Test that injection via filter column name is rejected."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "'; DROP TABLE users; --", "op": "=", "value": 1}],
            page_size=10,
        ))
        assert resp.error is not None

    def test_fetch_injection_via_sort_column_rejected(self, connection_profile_id, setup_test_table):
        """Test that injection via sort column name is rejected."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            sort_column="1=1; DROP TABLE users; --",
            page_size=10,
        ))
        assert resp.error is not None

    def test_fetch_injection_via_schema_rejected(self, connection_profile_id, setup_test_table):
        """Test that injection via schema name is rejected."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema="'; DROP TABLE users; --",
            table=setup_test_table,
            page_size=10,
        ))
        assert resp.error is not None

    def test_fetch_nonexistent_table(self, connection_profile_id):
        """Test fetch from a table that doesn't exist returns error."""
        resp = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table="nonexistent_table_xyz",
            page_size=10,
        ))
        assert resp.error is not None


class TestInsertRow:
    """Integration tests for DataBrowserService.insert_row."""

    def test_insert_row(self, connection_profile_id, setup_test_table):
        """Test inserting a single row."""
        resp = DataBrowserService.insert_row(RowInsertRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            data={"name": "New User", "email": "new@example.com", "age": 25},
        ))
        assert resp.success is True
        assert resp.affected_rows >= 1

    def test_insert_empty_data_fails(self, connection_profile_id, setup_test_table):
        """Test insert with empty data returns failure."""
        resp = DataBrowserService.insert_row(RowInsertRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            data={},
        ))
        assert resp.success is False

    def test_insert_increases_row_count(self, connection_profile_id, setup_test_table):
        """Test that inserting a row increases total count."""
        before = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            page_size=1,
        ))
        DataBrowserService.insert_row(RowInsertRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            data={"name": "Counted User", "age": 42},
        ))
        after = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            page_size=1,
        ))
        assert after.total_rows == before.total_rows + 1


class TestUpdateRow:
    """Integration tests for DataBrowserService.update_row."""

    def test_update_row(self, connection_profile_id, setup_test_table):
        """Test updating a row by primary key."""
        # Get first row's id
        data = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            sort_column="id",
            sort_direction="ASC",
            page_size=1,
        ))
        row_id = data.rows[0]["id"]

        resp = DataBrowserService.update_row(RowUpdateRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            primary_key={"id": row_id},
            data={"name": "Updated Name"},
        ))
        assert resp.success is True

        # Verify update
        verify = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "id", "op": "=", "value": row_id}],
            page_size=1,
        ))
        assert verify.rows[0]["name"] == "Updated Name"

    def test_update_empty_data_fails(self, connection_profile_id, setup_test_table):
        """Test update with empty data returns failure."""
        resp = DataBrowserService.update_row(RowUpdateRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            primary_key={"id": 1},
            data={},
        ))
        assert resp.success is False

    def test_update_empty_pk_fails(self, connection_profile_id, setup_test_table):
        """Test update with empty primary key returns failure."""
        resp = DataBrowserService.update_row(RowUpdateRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            primary_key={},
            data={"name": "Should Fail"},
        ))
        assert resp.success is False


class TestDeleteRow:
    """Integration tests for DataBrowserService.delete_row."""

    def test_delete_row(self, connection_profile_id, setup_test_table):
        """Test deleting a row by primary key."""
        # Get first row
        data = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            sort_column="id",
            sort_direction="ASC",
            page_size=1,
        ))
        row_id = data.rows[0]["id"]

        resp = DataBrowserService.delete_row(RowDeleteRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            primary_key={"id": row_id},
        ))
        assert resp.success is True
        assert resp.affected_rows == 1

        # Verify deletion
        verify = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "id", "op": "=", "value": row_id}],
            page_size=1,
        ))
        assert verify.total_rows == 0

    def test_delete_empty_pk_fails(self, connection_profile_id, setup_test_table):
        """Test delete with empty primary key returns failure."""
        resp = DataBrowserService.delete_row(RowDeleteRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            primary_key={},
        ))
        assert resp.success is False


class TestCRUDRoundTrip:
    """End-to-end test: insert, fetch, update, delete."""

    def test_full_crud_lifecycle(self, connection_profile_id, setup_test_table):
        """Full CRUD: insert -> read -> update -> verify -> delete -> verify."""
        # Insert
        insert_resp = DataBrowserService.insert_row(RowInsertRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            data={"name": "Lifecycle User", "email": "lifecycle@test.com", "age": 30, "score": 99.5},
        ))
        assert insert_resp.success

        # Read (find by email)
        fetch = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "email", "op": "=", "value": "lifecycle@test.com"}],
            page_size=1,
        ))
        assert fetch.total_rows == 1
        row = fetch.rows[0]
        assert row["name"] == "Lifecycle User"

        # Update
        update_resp = DataBrowserService.update_row(RowUpdateRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            primary_key={"id": row["id"]},
            data={"name": "Updated Lifecycle", "score": 100.0},
        ))
        assert update_resp.success

        # Verify update
        verify = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "id", "op": "=", "value": row["id"]}],
            page_size=1,
        ))
        assert verify.rows[0]["name"] == "Updated Lifecycle"
        assert float(verify.rows[0]["score"]) == 100.0

        # Delete
        delete_resp = DataBrowserService.delete_row(RowDeleteRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            primary_key={"id": row["id"]},
        ))
        assert delete_resp.success

        # Verify deletion
        gone = DataBrowserService.fetch_data(DataBrowserRequest(
            profile_id=connection_profile_id,
            schema=TEST_SCHEMA,
            table=setup_test_table,
            filters=[{"column": "id", "op": "=", "value": row["id"]}],
            page_size=1,
        ))
        assert gone.total_rows == 0
