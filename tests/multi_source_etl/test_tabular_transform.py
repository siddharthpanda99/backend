"""Tests for TabularTransformService integration into the ETL pipeline.

Tests cover:
- Single-table transforms (filter, select, transform, aggregate, sort, limit, distinct)
- Collection-level transforms (multiple collections, pass-through)
- Full pipeline integration with MultiSourceETLService
- Edge cases: empty records, empty operations, unknown operation types
"""

from __future__ import annotations

import pytest
from typing import Any, Dict, List

from common_lib.modules.multi_source_etl.tabular_transform.service import (
    TabularTransformService,
    transform_table,
    transform_collection,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_records() -> List[Dict[str, Any]]:
    return [
        {"name": "Alice", "department": "Engineering", "salary": 120000, "active": True},
        {"name": "Bob", "department": "Engineering", "salary": 95000, "active": True},
        {"name": "Charlie", "department": "Marketing", "salary": 85000, "active": True},
        {"name": "Diana", "department": "Marketing", "salary": 92000, "active": False},
        {"name": "Eve", "department": "Engineering", "salary": 110000, "active": True},
        {"name": "Frank", "department": "Sales", "salary": None, "active": True},
    ]


@pytest.fixture
def svc() -> TabularTransformService:
    return TabularTransformService()


# ── transform_table tests ────────────────────────────────────────────


class TestTransformTable:
    def test_filter_equals(self, svc, sample_records):
        ops = [{"type": "filter", "column": "department", "operator": "==", "value": "Engineering"}]
        result = svc.transform_table(sample_records, ops)
        assert len(result) == 3
        assert all(r["department"] == "Engineering" for r in result)

    def test_filter_greater_than(self, svc, sample_records):
        ops = [{"type": "filter", "column": "salary", "operator": ">", "value": 100000}]
        result = svc.transform_table(sample_records, ops)
        assert len(result) == 2
        assert all(r["salary"] > 100000 for r in result)

    def test_filter_multiple_and(self, svc, sample_records):
        ops = [
            {"type": "filter", "column": "department", "operator": "==", "value": "Engineering"},
            {"type": "filter", "column": "active", "operator": "==", "value": True, "logical": "and"},
        ]
        result = svc.transform_table(sample_records, ops)
        # Alice, Bob, Eve are Engineering + active=True (3 employees)
        assert len(result) == 3
        assert all(r["department"] == "Engineering" and r["active"] for r in result)

    def test_select_columns(self, svc, sample_records):
        ops = [{"type": "select", "columns": ["name", "salary"]}]
        result = svc.transform_table(sample_records, ops)
        assert len(result) == 6
        assert list(result[0].keys()) == ["name", "salary"]

    def test_transform_computed_column(self, svc, sample_records):
        ops = [{"type": "transform", "expression": "pl.col('salary') * 1.1", "alias": "salary_with_bonus"}]
        result = svc.transform_table(sample_records, ops)
        assert len(result) == 6
        assert "salary_with_bonus" in result[0]
        # Alice: 120000 * 1.1 = 132000
        assert result[0]["salary_with_bonus"] == pytest.approx(132000.0)

    def test_aggregate_sum(self, svc, sample_records):
        ops = [{
            "type": "aggregate",
            "group_by": ["department"],
            "aggregations": [{"column": "salary", "function": "sum", "alias": "total_salary"}],
        }]
        result = svc.transform_table(sample_records, ops)
        assert len(result) == 3  # 3 departments
        dept_map = {r["department"]: r["total_salary"] for r in result}
        assert dept_map["Engineering"] == 325000  # 120000 + 95000 + 110000

    def test_sort_ascending(self, svc, sample_records):
        ops = [{"type": "sort", "columns": [{"column": "salary", "direction": "ascending"}]}]
        result = svc.transform_table(sample_records, ops)
        salaries = [r["salary"] for r in result if r["salary"] is not None]
        assert salaries == sorted(salaries)

    def test_sort_descending(self, svc, sample_records):
        ops = [{"type": "sort", "columns": [{"column": "name", "direction": "descending"}]}]
        result = svc.transform_table(sample_records, ops)
        names = [r["name"] for r in result]
        assert names == sorted(names, reverse=True)

    def test_limit(self, svc, sample_records):
        ops = [{"type": "limit", "value": 2}]
        result = svc.transform_table(sample_records, ops)
        assert len(result) == 2

    def test_distinct(self, svc, sample_records):
        # Add duplicate
        records = sample_records + [sample_records[0]]
        ops = [{"type": "distinct"}]
        result = svc.transform_table(records, ops)
        assert len(result) == len(sample_records)

    def test_no_operations_passthrough(self, svc, sample_records):
        result = svc.transform_table(sample_records, [])
        assert result == sample_records

    def test_invalid_operation_type(self, svc, sample_records):
        ops = [{"type": "nonexistent"}]
        # Should log warning and pass through
        result = svc.transform_table(sample_records, ops)
        assert len(result) == len(sample_records)

    def test_multiple_operations(self, svc, sample_records):
        """Filter → filter out nulls → select → sort — chain of operations."""
        ops = [
            {"type": "filter", "column": "active", "operator": "==", "value": True},
            {"type": "filter", "column": "salary", "operator": "is_not_null"},
            {"type": "select", "columns": ["name", "salary"]},
            {"type": "sort", "columns": [{"column": "salary", "direction": "descending"}]},
        ]
        result = svc.transform_table(sample_records, ops)
        # 6 records - Diana (inactive) - Frank (null salary) = 4
        assert len(result) == 4
        assert list(result[0].keys()) == ["name", "salary"]
        assert result[0]["salary"] >= result[-1]["salary"]

    def test_empty_records(self, svc):
        ops = [{"type": "filter", "column": "name", "operator": "==", "value": "nobody"}]
        result = svc.transform_table([], [])
        assert result == []

        result2 = svc.transform_table([], ops)
        assert result2 == []

    def test_contains_filter(self, svc, sample_records):
        ops = [{"type": "filter", "column": "name", "operator": "contains", "value": "li"}]
        result = svc.transform_table(sample_records, ops)
        assert len(result) == 2  # Alice, Charlie
        assert all("li" in r["name"].lower() for r in result)


# ── transform_collection tests ───────────────────────────────────────


class TestTransformCollection:
    @pytest.fixture
    def extracted(self, sample_records) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "employees": sample_records,
            "departments": [
                {"id": 1, "name": "Engineering"},
                {"id": 2, "name": "Marketing"},
                {"id": 3, "name": "Sales"},
            ],
        }

    def test_single_collection(self, svc, extracted):
        ops = {"employees": [{"type": "select", "columns": ["name", "salary"]}]}
        result = svc.transform_collection(extracted, ops)
        assert "employees" in result
        assert "departments" in result
        assert list(result["employees"][0].keys()) == ["name", "salary"]
        assert list(result["departments"][0].keys()) == ["id", "name"]  # Pass-through

    def test_multiple_collections(self, svc, extracted):
        ops = {
            "employees": [{"type": "select", "columns": ["name"]}],
            "departments": [{"type": "filter", "column": "id", "operator": "<=", "value": 2}],
        }
        result = svc.transform_collection(extracted, ops)
        assert len(result["employees"]) == 6
        assert list(result["employees"][0].keys()) == ["name"]
        assert len(result["departments"]) == 2
        assert result["departments"][0]["id"] == 1

    def test_missing_collection_pass_through(self, svc, extracted):
        ops = {"nonexistent": [{"type": "select", "columns": ["x"]}]}
        result = svc.transform_collection(extracted, ops)
        assert result == extracted

    def test_all_empty_operations(self, svc, extracted):
        result = svc.transform_collection(extracted, {})
        assert result == extracted


# ── transform_pipeline tests ─────────────────────────────────────────


class TestTransformPipeline:
    @pytest.fixture
    def pipeline_data(self, sample_records) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        return {
            "postgres": {
                "employees": sample_records,
                "departments": [
                    {"id": 1, "name": "Engineering"},
                    {"id": 2, "name": "Marketing"},
                ],
            },
            "mongo": {
                "orders": [
                    {"order_id": 1, "amount": 100},
                    {"order_id": 2, "amount": 200},
                ],
            },
        }

    def test_full_pipeline_transform(self, svc, pipeline_data):
        transforms = {
            "postgres": {
                "employees": [
                    {"type": "filter", "column": "active", "operator": "==", "value": True},
                    {"type": "select", "columns": ["name", "salary"]},
                ],
            },
        }
        result = svc.transform_pipeline(pipeline_data, transforms)
        assert "postgres" in result
        assert "mongo" in result
        assert len(result["postgres"]["employees"]) == 5  # 6 - Diana
        assert list(result["postgres"]["employees"][0].keys()) == ["name", "salary"]
        # Mongo passes through unchanged
        assert result["mongo"]["orders"] == pipeline_data["mongo"]["orders"]

    def test_no_transforms(self, svc, pipeline_data):
        result = svc.transform_pipeline(pipeline_data, {})
        assert result == pipeline_data


# ── Convenience function tests ───────────────────────────────────────


class TestConvenienceFunctions:
    def test_transform_table_single_shot(self, sample_records):
        ops = [{"type": "select", "columns": ["name"]}]
        result = transform_table(sample_records, ops)
        assert len(result) == 6
        assert list(result[0].keys()) == ["name"]

    def test_transform_collection_single_shot(self, sample_records):
        ops = {"data": [{"type": "limit", "value": 2}]}
        result = transform_collection({"data": sample_records}, ops)
        assert len(result["data"]) == 2
