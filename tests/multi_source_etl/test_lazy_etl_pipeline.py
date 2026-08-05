"""Integration test for the full ETL pipeline using the lazy execution engine.

Demonstrates the complete flow described in POLARS_LAZY_EXECUTION_MODEL_GUIDE.md:

    Source → Lazy Scan → Transform Pipeline → Aggregate → Sort → Sink

This connects the TabularTransformService (ETL intermediate step) with the
PolarsEngine (lazy execution layer) to prove the full pipeline works end-to-end.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List

import polars as pl
import pytest

from common_lib.modules.doc_processing.excel.core.lazy_engine import (
    Aggregation,
    FilterCondition,
    PolarsEngine,
    QueryPlan,
    SortConfig,
    TransformExpr,
    build_pipeline,
    get_engine,
)
from common_lib.modules.doc_processing.excel.core.scanners import (
    SourceScanner,
)
from common_lib.modules.doc_processing.excel.core.sinks import (
    FileSink,
    DataFrameSink,
    DictListSink,
    MultiSink,
)
from common_lib.modules.multi_source_etl.tabular_transform.service import (
    TabularTransformService,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def sample_csv_path() -> str:
    """Create a realistic sales CSV for ETL pipeline testing."""
    import csv

    rows = [
        {"order_id": 1, "region": "North", "product": "Widget A", "year": 2026,
         "status": "completed", "revenue": 250.0, "qty": 10, "cost": 150.0},
        {"order_id": 2, "region": "South", "product": "Widget B", "year": 2026,
         "status": "completed", "revenue": 500.0, "qty": 5, "cost": 300.0},
        {"order_id": 3, "region": "North", "product": "Widget A", "year": 2025,
         "status": "cancelled", "revenue": 100.0, "qty": 4, "cost": 60.0},
        {"order_id": 4, "region": "East", "product": "Widget C", "year": 2026,
         "status": "completed", "revenue": 300.0, "qty": 7, "cost": 200.0},
        {"order_id": 5, "region": "North", "product": "Widget B", "year": 2026,
         "status": "completed", "revenue": 600.0, "qty": 12, "cost": 350.0},
        {"order_id": 6, "region": "South", "product": "Widget A", "year": 2025,
         "status": "completed", "revenue": 200.0, "qty": 8, "cost": 100.0},
        {"order_id": 7, "region": "East", "product": "Widget C", "year": 2026,
         "status": "pending", "revenue": 150.0, "qty": 3, "cost": 90.0},
        {"order_id": 8, "region": "West", "product": "Widget B", "year": 2026,
         "status": "completed", "revenue": 450.0, "qty": 9, "cost": 275.0},
        {"order_id": 9, "region": "North", "product": "Widget A", "year": 2026,
         "status": "completed", "revenue": 800.0, "qty": 15, "cost": 500.0},
        {"order_id": 10, "region": "South", "product": "Widget C", "year": 2026,
         "status": "pending", "revenue": 350.0, "qty": 6, "cost": 200.0},
    ]
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    yield path
    os.unlink(path)


@pytest.fixture
def engine() -> PolarsEngine:
    return PolarsEngine()


# ═══════════════════════════════════════════════════════════════════
# Test: Full ETL Pipeline — SourceScanner → Build → Transform → Sink
# ═══════════════════════════════════════════════════════════════════


class TestFullETLPipeline:
    """End-to-end ETL pipeline matching the guide's §17 complex ETL example."""

    def test_etl_scan_transform_sink(self, sample_csv_path: str, engine: PolarsEngine):
        """
        Full ETL flow:
        1. SourceScanner detects format
        2. Build a lazy query plan (filter → transform → aggregate → sort → limit)
        3. Execute via PolarsEngine
        4. Sink result to Parquet
        """
        # Step 1: SourceScanner auto-detects the CSV
        info = SourceScanner.detect(sample_csv_path)
        assert info.format_type == "csv"
        assert info.size_bytes > 0
        assert info.column_count == 8

        # Step 2: Build a QueryPlan matching §17 of the guide:
        #   "load sales data, remove cancelled transactions, keep records from 2026,
        #    calculate revenue, aggregate by region, sort by revenue, top 3"
        plan = build_pipeline(
            sample_csv_path,
            filters=[
                FilterCondition(column="status", operator="!=", value="cancelled"),
                FilterCondition(column="year", operator="==", value=2026),
            ],
            transforms=[
                TransformExpr(
                    expression="pl.col('revenue') - pl.col('cost')",
                    alias="profit",
                ),
            ],
            group_by=["region"],
            aggregations=[
                Aggregation(column="revenue", function="sum", alias="total_revenue"),
                Aggregation(column="profit", function="sum", alias="total_profit"),
                Aggregation(column="qty", function="count", alias="order_count"),
            ],
            sort=[SortConfig(column="total_revenue", direction="descending")],
            limit=3,
        )

        # Step 3: Execute via PolarsEngine
        lf = engine.compile(plan)
        engine.explain(lf)  # Verify plan inspection works (§9)

        # Collect and verify shape
        df = engine.collect(lf)
        assert len(df) == 3  # Top 3 regions (limit=3)
        assert set(df.columns) == {"region", "total_revenue", "total_profit", "order_count"}

        # North: revenue = 250+600+800=1650, profit = 100+250+300=650, orders = 3
        north = df.filter(pl.col("region") == "North")
        assert north["total_revenue"][0] == 1650.0
        assert north["total_profit"][0] == 650.0
        assert north["order_count"][0] == 3

        # Step 4: Sink to Parquet (§21 streaming output)
        fd, out_path = tempfile.mkstemp(suffix=".parquet")
        os.close(fd)
        try:
            sink_result = engine.sink(lf, out_path)
            assert sink_result["saved"] is True
            assert os.path.getsize(out_path) > 0
            # Verify we can read it back
            back = pl.read_parquet(out_path)
            assert len(back) == 3
        finally:
            os.unlink(out_path)

    def test_etl_sink_to_multiple_formats(self, sample_csv_path: str, engine: PolarsEngine):
        """Write the same lazy result to multiple formats using MultiSink."""
        plan = build_pipeline(
            sample_csv_path,
            filters=[FilterCondition(column="region", operator="in", value=["North", "South"])],
            select_columns=["order_id", "region", "revenue", "status"],
        )

        lf = engine.compile(plan)

        fd_csv, csv_path = tempfile.mkstemp(suffix=".csv")
        fd_parquet, parquet_path = tempfile.mkstemp(suffix=".parquet")
        os.close(fd_csv)
        os.close(fd_parquet)

        try:
            multi = MultiSink([
                FileSink(csv_path),
                FileSink(parquet_path),
            ])
            result = multi.write(lf)
            assert result.success is True
            assert os.path.getsize(csv_path) > 0
            assert os.path.getsize(parquet_path) > 0
        finally:
            os.unlink(csv_path)
            os.unlink(parquet_path)

    def test_etl_dataframe_sink(self, sample_csv_path: str, engine: PolarsEngine):
        """Collect into in-memory DataFrame for API consumption."""
        plan = build_pipeline(
            sample_csv_path,
            filters=[FilterCondition(column="status", operator="==", value="completed")],
            select_columns=["order_id", "region", "revenue"],
            sort=[SortConfig(column="revenue", direction="descending")],
        )
        lf = engine.compile(plan)
        sink = DataFrameSink()
        result = sink.write(lf)
        assert result.success
        assert result.rows == 7  # 7 completed orders (1,2,4,5,6,8,9)

    def test_etl_dict_list_sink(self, sample_csv_path: str, engine: PolarsEngine):
        """Collect into Python-native dict list for downstream processing."""
        plan = build_pipeline(sample_csv_path, limit=3)
        lf = engine.compile(plan)
        sink = DictListSink()
        result = sink.write(lf)
        assert result.success
        assert isinstance(sink.result, list)
        assert len(sink.result) == 3
        assert isinstance(sink.result[0], dict)

    def test_etl_full_plan_json_roundtrip(self, sample_csv_path: str):
        """Serialize the pipeline plan to JSON (§22 IR format) and restore it."""
        plan = build_pipeline(
            sample_csv_path,
            filters=[FilterCondition(column="status", operator="==", value="completed")],
            group_by=["region"],
            aggregations=[Aggregation("revenue", "sum", alias="total")],
            sort=[SortConfig("total", "descending")],
            limit=5,
        )
        # Serialize
        d = plan.to_dict()
        assert "source" in d
        assert "operations" in d
        assert len(d["operations"]) == 4  # filter + group_by + sort + limit

        # Deserialize
        restored = QueryPlan.from_dict(d)
        assert len(restored.filters) == 1
        assert restored.group_by == ["region"]
        assert restored.limit == 5

        # Execute restored plan
        engine = get_engine("polars")
        df = engine.execute(restored)
        assert len(df) <= 5

    def test_etl_duckdb_alternative_engine(self, sample_csv_path: str):
        """Same pipeline with DuckDBEngine instead of PolarsEngine."""
        plan = build_pipeline(
            sample_csv_path,
            filters=[FilterCondition("year", "==", 2026)],
            select_columns=["region", "revenue"],
        )
        engine = get_engine("duckdb")
        df = engine.execute(plan)
        assert len(df) == 8  # 8 rows in 2026 (1,2,4,5,7,8,9,10)
        assert set(df.columns) == {"region", "revenue"}


# ═══════════════════════════════════════════════════════════════════
# Test: TabularTransformService → Lazy Engine integration
# ═══════════════════════════════════════════════════════════════════


class TestTabularTransformWithEngine:
    """Tests connecting TabularTransformService (ETL) with the lazy engine."""

    @pytest.fixture
    def sample_records(self) -> List[Dict[str, Any]]:
        return [
            {"name": "Alice", "dept": "Engineering", "salary": 120000, "active": True, "bonus": 10000},
            {"name": "Bob", "dept": "Engineering", "salary": 95000, "active": True, "bonus": 5000},
            {"name": "Charlie", "dept": "Marketing", "salary": 85000, "active": True, "bonus": 3000},
            {"name": "Diana", "dept": "Marketing", "salary": 92000, "active": False, "bonus": 0},
            {"name": "Eve", "dept": "Engineering", "salary": 110000, "active": True, "bonus": 8000},
            {"name": "Frank", "dept": "Sales", "salary": None, "active": True, "bonus": 2000},
        ]

    def test_transform_with_computed_column_and_drop(self, sample_records):
        """Filter → compute → drop temp columns → sort — via TabularTransformService."""
        svc = TabularTransformService()
        ops = [
            {"type": "filter", "column": "active", "operator": "==", "value": True},
            {"type": "transform", "expression": "pl.col('salary') + pl.col('bonus')", "alias": "total_comp"},
            {"type": "drop", "columns": ["bonus"]},
            {"type": "sort", "columns": [{"column": "total_comp", "direction": "descending"}]},
        ]
        result = svc.transform_table(sample_records, ops)
        # 5 active employees
        assert len(result) == 5
        assert "bonus" not in result[0]  # Dropped
        assert "total_comp" in result[0]  # Computed
        assert "salary" in result[0]      # Kept
        # Alice has highest total: 120000 + 10000 = 130000. Frank's is null.
        # Sort puts nulls last in descending order, so Alice should be first.
        alice = [r for r in result if r["name"] == "Alice"]
        assert len(alice) == 1
        assert alice[0]["total_comp"] == 130000.0

    def test_transform_with_drop_and_select(self, sample_records):
        """Drop columns then select — verify drop happens before select in compile()."""
        svc = TabularTransformService()
        ops = [
            {"type": "drop", "columns": ["bonus", "salary"]},
            {"type": "select", "columns": ["name", "dept", "active"]},
        ]
        result = svc.transform_table(sample_records, ops)
        assert len(result) == 6
        assert list(result[0].keys()) == ["name", "dept", "active"]

    def test_transform_pipeline_with_drop(self, sample_records):
        """Full pipeline transform with drop — via transform_pipeline()."""
        svc = TabularTransformService()
        pipeline_data = {
            "postgres": {
                "employees": sample_records,
                "departments": [
                    {"id": 1, "name": "Engineering", "budget": 500000, "temp_flag": True},
                ],
            },
        }
        transforms = {
            "postgres": {
                "employees": [
                    {"type": "filter", "column": "active", "operator": "==", "value": True},
                    {"type": "drop", "columns": ["bonus"]},
                    {"type": "select", "columns": ["name", "dept", "salary"]},
                ],
                "departments": [
                    {"type": "drop", "columns": ["temp_flag"]},
                ],
            },
        }
        result = svc.transform_pipeline(pipeline_data, transforms)
        assert len(result["postgres"]["employees"]) == 5
        assert "bonus" not in result["postgres"]["employees"][0]
        assert list(result["postgres"]["employees"][0].keys()) == ["name", "dept", "salary"]
        assert "temp_flag" not in result["postgres"]["departments"][0]
        assert list(result["postgres"]["departments"][0].keys()) == ["id", "name", "budget"]
