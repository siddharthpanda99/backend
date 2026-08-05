"""Lazy Engine REST API routes — query building, pipeline execution, scanning, sink.

Thin routing layer over common_lib.modules.doc_processing.excel.core.lazy_engine
and common_lib.modules.doc_processing.excel.core.duckdb_engine.

Exposes:
  - GET    /lazy/engines          List available engines
  - GET    /lazy/formats          List supported source formats
  - POST   /lazy/scan             Scan a source file / records
  - POST   /lazy/query            Build and execute a QueryPlan pipeline
  - POST   /lazy/execute          Execute a pre-built plan (JSON)
  - POST   /lazy/sink             Execute and save to file
  - POST   /lazy/explain          Show execution plan without running
  - POST   /lazy/filter           Apply filter conditions
  - POST   /lazy/aggregate        Group and aggregate data
  - POST   /lazy/transform        Add computed columns
  - POST   /lazy/sort             Sort data
  - POST   /lazy/batch-scan       Batch-scan multiple sources
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================================
# Schemas
# =========================================================================


class ScanRequest(BaseModel):
    """Request to scan a source — file path or records."""
    source: Any  # str path or List[Dict] records
    source_type: Optional[str] = "csv"  # csv, parquet, json, etc.
    config: Dict[str, Any] = Field(default_factory=dict)  # extra scan kwargs


class FilterSpec(BaseModel):
    """A single filter condition."""
    column: str
    operator: str  # ==, !=, >, >=, <, <=, in, not_in, contains, starts_with, ends_with, is_null, is_not_null
    value: Any = None
    logical: str = "and"  # and, or


class TransformSpec(BaseModel):
    """A computed column expression."""
    expression: str  # SQL or Polars expression string
    alias: Optional[str] = None


class AggregationSpec(BaseModel):
    """An aggregation definition."""
    column: str
    function: str  # sum, mean, avg, min, max, count, n_unique, first, last, median, std, var
    alias: Optional[str] = None


class SortSpec(BaseModel):
    """A sort specification."""
    column: str
    direction: str = "ascending"  # ascending, descending


class JoinSpec(BaseModel):
    """A join configuration."""
    right_source: Any
    left_on: List[str]
    right_on: List[str]
    how: str = "left"  # left, inner, right, cross, semi, anti
    suffix: str = "_right"


class QueryPlanRequest(BaseModel):
    """Build and execute a query pipeline in one call."""
    source: Any  # str path or List[Dict]
    source_type: str = "csv"
    source_config: Dict[str, Any] = Field(default_factory=dict)
    engine: str = "polars"  # polars, duckdb
    filters: List[FilterSpec] = Field(default_factory=list)
    select_columns: Optional[List[str]] = None
    transforms: List[TransformSpec] = Field(default_factory=list)
    joins: List[JoinSpec] = Field(default_factory=list)
    group_by: Optional[List[str]] = None
    aggregations: List[AggregationSpec] = Field(default_factory=list)
    sort: List[SortSpec] = Field(default_factory=list)
    limit: Optional[int] = None
    offset: Optional[int] = None
    distinct: bool = False


class ExecutePlanRequest(BaseModel):
    """Execute a pre-built QueryPlan serialized as JSON."""
    plan_json: str  # JSON-serialized QueryPlan
    engine: str = "polars"


class SinkRequest(QueryPlanRequest):
    """Execute a pipeline and save to file."""
    output_path: str
    output_format: Optional[str] = None  # auto-detected from extension if not set


class ExplainRequest(QueryPlanRequest):
    """Show execution plan without running."""
    pass


class FilterRequest(BaseModel):
    """Apply filters to data."""
    source: Any
    source_type: str = "csv"
    source_config: Dict[str, Any] = Field(default_factory=dict)
    engine: str = "polars"
    filters: List[FilterSpec]


class AggregateRequest(BaseModel):
    """Group and aggregate data."""
    source: Any
    source_type: str = "csv"
    source_config: Dict[str, Any] = Field(default_factory=dict)
    engine: str = "polars"
    group_by: Optional[List[str]] = None
    aggregations: List[AggregationSpec]


class TransformRequest(BaseModel):
    """Add computed columns."""
    source: Any
    source_type: str = "csv"
    source_config: Dict[str, Any] = Field(default_factory=dict)
    engine: str = "polars"
    transforms: List[TransformSpec]


class SortRequest(BaseModel):
    """Sort data."""
    source: Any
    source_type: str = "csv"
    source_config: Dict[str, Any] = Field(default_factory=dict)
    engine: str = "polars"
    sort: List[SortSpec]


class BatchScanRequest(BaseModel):
    """Batch-scan multiple sources."""
    paths: List[str]
    source_type: Optional[str] = None
    engine: str = "polars"


# =========================================================================
# Helpers
# =========================================================================


def _get_engine(name: str = "polars"):
    """Lazy-import and return the requested engine."""
    from common_lib.modules.doc_processing.excel.core.lazy_engine import (
        get_engine as _engine_registry,
    )
    try:
        return _engine_registry(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _build_query_plan(req: QueryPlanRequest):
    """Build a QueryPlan from a QueryPlanRequest."""
    from common_lib.modules.doc_processing.excel.core.lazy_engine import (
        Aggregation,
        FilterCondition,
        JoinConfig,
        QueryPlan,
        SortConfig,
        TransformExpr,
    )
    return QueryPlan(
        source=req.source,
        source_type=req.source_type,
        source_config=req.source_config,
        filters=[FilterCondition(**f.model_dump()) for f in req.filters],
        select_columns=req.select_columns,
        transforms=[TransformExpr(**t.model_dump()) for t in req.transforms],
        joins=[
            JoinConfig(
                right_source=j.right_source,
                left_on=j.left_on,
                right_on=j.right_on,
                how=j.how,
                suffix=j.suffix,
            )
            for j in req.joins
        ],
        group_by=req.group_by,
        aggregations=[Aggregation(**a.model_dump()) for a in req.aggregations],
        sort=[SortConfig(**s.model_dump()) for s in req.sort],
        limit=req.limit,
        offset=req.offset,
        distinct=req.distinct,
    )


def _serialize_df(df) -> Dict[str, Any]:
    """Convert a DataFrame to a JSON-serializable dict."""
    try:
        return {
            "columns": df.columns,
            "rows": df.to_dicts() if hasattr(df, "to_dicts") else json.loads(df.write_json()),
            "shape": [len(df), len(df.columns)],
        }
    except Exception:
        try:
            return {
                "columns": list(df.columns),
                "rows": df.to_dict(orient="records") if hasattr(df, "to_dict") else str(df),
                "shape": [df.shape[0], df.shape[1]],
            }
        except Exception as e:
            return {"columns": [], "rows": [], "error": str(e)}


# =========================================================================
# Engine Management
# =========================================================================


@router.get("/lazy/engines", summary="List available engines")
async def list_engines() -> Dict[str, Any]:
    """List all available tabular engines (polars, duckdb)."""
    from common_lib.modules.doc_processing.excel.core.lazy_engine import (
        list_engines as _list_engines,
    )
    engines = _list_engines()
    return {
        "engines": engines,
        "count": len(engines),
        "default": "polars",
    }


@router.get("/lazy/formats", summary="List supported source formats")
async def list_formats() -> Dict[str, Any]:
    """List all supported source file formats."""
    return {
        "formats": {
            "csv": {"description": "Comma-separated values", "engine": "all"},
            "tsv": {"description": "Tab-separated values", "engine": "all"},
            "parquet": {"description": "Apache Parquet columnar storage", "engine": "all"},
            "json": {"description": "JSON records", "engine": "all"},
            "feather": {"description": "Apache Feather / IPC format", "engine": "all"},
            "xlsx": {"description": "Excel workbook (DuckDB requires spatial ext)", "engine": "duckdb"},
            "xlsm": {"description": "Excel macro-enabled workbook", "engine": "duckdb"},
        },
        "count": 7,
    }


# =========================================================================
# Scan
# =========================================================================


@router.post("/lazy/scan", summary="Scan a source and return schema")
async def scan_source(req: ScanRequest) -> Dict[str, Any]:
    """Scan a source file or records and return the schema with a preview."""
    try:
        engine = _get_engine("polars")
        q = engine.scan(req.source, source_type=req.source_type, **req.config)
        df = engine.head(q, 10)
        schema = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            schema.append({"name": col, "dtype": dtype})

        return {
            "success": True,
            "schema": schema,
            "preview": _serialize_df(df),
            "total_rows": engine.count(q),
            "engine": "polars",
        }
    except Exception as e:
        logger.error("Scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lazy/batch-scan", summary="Batch-scan multiple sources")
async def batch_scan(req: BatchScanRequest) -> Dict[str, Any]:
    """Scan multiple sources and union them.

    BatchScanner always returns Polars LazyFrame; hardcode polars engine.
    """
    try:
        from common_lib.modules.doc_processing.excel.core.scanners import (
            BatchScanner,
        )
        scanner = BatchScanner()
        for path in req.paths:
            scanner.add_path(path, source_type=req.source_type)
        lf = scanner.union_all()
        import polars as pl
        count = lf.select(pl.len()).collect()[0, 0] if isinstance(lf, pl.LazyFrame) else len(lf)
        preview_df = lf.limit(10).collect() if isinstance(lf, pl.LazyFrame) else lf.head(10)
        return {
            "success": True,
            "sources": req.paths,
            "count": len(req.paths),
            "total_rows": count,
            "preview": _serialize_df(preview_df),
            "engine": "polars",
        }
    except Exception as e:
        logger.error("Batch scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Query Pipeline — Full Pipeline
# =========================================================================


@router.post("/lazy/query", summary="Build and execute a query pipeline")
async def execute_query(req: QueryPlanRequest) -> Dict[str, Any]:
    """Build a QueryPlan from structured parameters and execute it.

    Supports filters, transforms, aggregations, joins, sort, and limit.
    Returns the result rows with schema.
    """
    try:
        plan = _build_query_plan(req)
        engine = _get_engine(req.engine)
        df = engine.execute(plan)
        serialized = _serialize_df(df)

        return {
            "success": True,
            "engine": req.engine,
            "source_type": req.source_type,
            "shape": serialized["shape"],
            "columns": serialized["columns"],
            "rows": serialized["rows"],
            "total_rows": serialized["shape"][0],
        }
    except Exception as e:
        logger.error("Query execution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lazy/execute", summary="Execute a pre-built QueryPlan (JSON)")
async def execute_plan(req: ExecutePlanRequest) -> Dict[str, Any]:
    """Execute a pre-serialized QueryPlan from JSON."""
    try:
        from common_lib.modules.doc_processing.excel.core.lazy_engine import (
            QueryPlan as _QueryPlan,
        )
        plan_data = json.loads(req.plan_json)
        plan = _QueryPlan.from_dict(plan_data) if isinstance(plan_data, dict) else plan_data

        engine = _get_engine(req.engine)
        df = engine.execute(plan)

        return {
            "success": True,
            "engine": req.engine,
            "shape": [len(df), len(df.columns)],
            "columns": list(df.columns),
        }
    except Exception as e:
        logger.error("Plan execute failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Sink
# =========================================================================


@router.post("/lazy/sink", summary="Execute pipeline and save to file")
async def sink_output(req: SinkRequest) -> Dict[str, Any]:
    """Execute a query pipeline and write the result directly to a file.

    Uses streaming COPY for DuckDB; collect+write for Polars.
    """
    try:
        plan = _build_query_plan(req)
        engine = _get_engine(req.engine)

        import os
        output_ext = os.path.splitext(req.output_path)[1].lower()
        sink_kwargs = {}
        if output_ext == ".csv":
            sink_kwargs["separator"] = req.source_config.get("separator", ",")
        elif output_ext == ".parquet":
            sink_kwargs["compression"] = req.source_config.get("compression", "snappy")

        result = engine.execute_to_sink(plan, req.output_path, **sink_kwargs)

        return {
            "success": True,
            "engine": req.engine,
            "output_path": req.output_path,
            "result": result,
        }
    except Exception as e:
        logger.error("Sink failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Explain
# =========================================================================


@router.post("/lazy/explain", summary="Show execution plan without running")
async def explain_plan(req: ExplainRequest) -> Dict[str, Any]:
    """Compile a QueryPlan into its execution plan string without materializing."""
    try:
        plan = _build_query_plan(req)
        engine = _get_engine(req.engine)
        query = engine.compile(plan)
        plan_str = engine.explain(query)

        return {
            "success": True,
            "engine": req.engine,
            "plan": plan_str,
            "plan_json": plan.to_dict(),
        }
    except Exception as e:
        logger.error("Explain failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Individual Operations
# =========================================================================


@router.post("/lazy/filter", summary="Apply filter conditions")
async def apply_filter(req: FilterRequest) -> Dict[str, Any]:
    """Scan a source and apply filter conditions."""
    try:
        from common_lib.modules.doc_processing.excel.core.lazy_engine import (
            FilterCondition,
        )
        engine = _get_engine(req.engine)
        q = engine.scan(req.source, source_type=req.source_type, **req.source_config)
        conditions = [FilterCondition(**f.model_dump()) for f in req.filters]
        q = engine.filter(q, conditions)
        df = engine.collect(q)
        serialized = _serialize_df(df)

        return {
            "success": True,
            "engine": req.engine,
            "shape": serialized["shape"],
            "rows": serialized["rows"],
            "total_rows": serialized["shape"][0],
        }
    except Exception as e:
        logger.error("Filter failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lazy/aggregate", summary="Group and aggregate data")
async def apply_aggregate(req: AggregateRequest) -> Dict[str, Any]:
    """Scan a source and apply group-by / aggregation."""
    try:
        from common_lib.modules.doc_processing.excel.core.lazy_engine import (
            Aggregation,
        )
        engine = _get_engine(req.engine)
        q = engine.scan(req.source, source_type=req.source_type, **req.source_config)
        aggs = [Aggregation(**a.model_dump()) for a in req.aggregations]
        q = engine.aggregate(q, group_by=req.group_by or [], aggregations=aggs)
        df = engine.collect(q)
        serialized = _serialize_df(df)

        return {
            "success": True,
            "engine": req.engine,
            "group_by": req.group_by,
            "shape": serialized["shape"],
            "rows": serialized["rows"],
        }
    except Exception as e:
        logger.error("Aggregate failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lazy/transform", summary="Add computed columns")
async def apply_transform(req: TransformRequest) -> Dict[str, Any]:
    """Scan a source and add computed columns."""
    try:
        from common_lib.modules.doc_processing.excel.core.lazy_engine import (
            TransformExpr,
        )
        engine = _get_engine(req.engine)
        q = engine.scan(req.source, source_type=req.source_type, **req.source_config)
        exprs = [TransformExpr(**t.model_dump()) for t in req.transforms]
        q = engine.transform(q, exprs)
        df = engine.collect(q)
        serialized = _serialize_df(df)

        return {
            "success": True,
            "engine": req.engine,
            "shape": serialized["shape"],
            "columns": serialized["columns"],
            "rows": serialized["rows"],
        }
    except Exception as e:
        logger.error("Transform failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lazy/sort", summary="Sort data")
async def apply_sort(req: SortRequest) -> Dict[str, Any]:
    """Scan a source and sort by columns."""
    try:
        from common_lib.modules.doc_processing.excel.core.lazy_engine import (
            SortConfig,
        )
        engine = _get_engine(req.engine)
        q = engine.scan(req.source, source_type=req.source_type, **req.source_config)
        sort_configs = [SortConfig(**s.model_dump()) for s in req.sort]
        q = engine.sort(q, sort_configs)
        df = engine.collect(q)
        serialized = _serialize_df(df)

        return {
            "success": True,
            "engine": req.engine,
            "sort": [s.column for s in sort_configs],
            "shape": serialized["shape"],
            "rows": serialized["rows"],
        }
    except Exception as e:
        logger.error("Sort failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
