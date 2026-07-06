"""Tests for AiAssistantService — NL-to-SQL generation with schema context.

Requires: running PostgreSQL with test data (conftest.py handles setup).
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Python Libs"))

from common_lib.modules.admin_db.service import AiAssistantService
from common_lib.modules.admin_db.schemas import AiGenerateRequest

TEST_SCHEMA = "test_admin_db_schema"


class TestAIGenerate:
    """Integration tests for AiAssistantService.generate."""

    def test_generate_count_query(self, connection_profile_id, setup_test_table):
        """Test generating a COUNT query from natural language."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"how many users are in the {setup_test_table} table",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert resp.sql is not None
        assert "COUNT" in resp.sql.upper()
        assert setup_test_table in resp.sql

    def test_generate_show_all_query(self, connection_profile_id, setup_test_table):
        """Test generating a SELECT ALL query."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"show me all rows from {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert "SELECT" in resp.sql.upper()
        assert setup_test_table in resp.sql

    def test_generate_latest_query(self, connection_profile_id, setup_test_table):
        """Test generating a latest/recent query."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"get the latest records from {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert "ORDER BY" in resp.sql.upper()
        assert "DESC" in resp.sql.upper()

    def test_generate_distinct_query(self, connection_profile_id, setup_test_table):
        """Test generating a DISTINCT query."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"show distinct values from {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert "DISTINCT" in resp.sql.upper()

    def test_generate_default_query(self, connection_profile_id, setup_test_table):
        """Test generating a default SELECT query."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"tell me about {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert "SELECT" in resp.sql.upper()
        assert "LIMIT" in resp.sql.upper()

    def test_generate_returns_confidence(self, connection_profile_id, setup_test_table):
        """Test that generated SQL includes a confidence score."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"list all from {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert resp.confidence is not None
        assert 0.0 <= resp.confidence <= 1.0

    def test_generate_returns_explanation(self, connection_profile_id, setup_test_table):
        """Test that generated SQL includes an explanation."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"select all from {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert resp.explanation is not None
        assert len(resp.explanation) > 0

    def test_generate_returns_tables_used(self, connection_profile_id, setup_test_table):
        """Test that tables_used tracks which tables were referenced."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"query the {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert resp.tables_used is not None
        # Should include the table name (either from prompt matching or default)
        assert resp.tables_used != [] or setup_test_table in resp.sql

    def test_generate_returns_duration(self, connection_profile_id, setup_test_table):
        """Test that generation returns a duration."""
        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"count rows in {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None
        assert resp.duration_ms > 0

    def test_generate_higher_confidence_when_table_name_matched(self, connection_profile_id, setup_test_table):
        """Test confidence is higher when the table name appears in the prompt."""
        with_name = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"count rows in {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        without_name = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt="count rows in the table",
            schema_name=TEST_SCHEMA,
        ))
        assert with_name.confidence is not None
        assert without_name.confidence is not None
        # When table name is matched, confidence should be higher
        assert with_name.confidence >= without_name.confidence

    def test_generate_sql_is_executable(self, connection_profile_id, setup_test_table):
        """Test that the generated SQL can actually be executed against the DB."""
        from common_lib.modules.admin_db.service import QueryExecutorService
        from common_lib.modules.admin_db.schemas import QueryExecuteRequest

        resp = AiAssistantService.generate(AiGenerateRequest(
            profile_id=connection_profile_id,
            prompt=f"count total rows in {setup_test_table}",
            schema_name=TEST_SCHEMA,
        ))
        assert resp.error is None

        # Execute the generated SQL
        query_resp = QueryExecutorService.execute(QueryExecuteRequest(
            profile_id=connection_profile_id,
            sql=resp.sql,
        ))
        assert query_resp.error is None
        assert query_resp.row_count >= 1
