"""E2E test for Multi-Source ETL pipelines (seed mode).

Tests all 5 use cases without requiring real database connections.
Data is extracted from the YAML seed files, merged, and validated.
"""

import os
import sys

sys.path.append(os.path.abspath("../Python Libs/common_lib/src"))

from common_lib.modules.multi_source_etl import (
    MultiSourceETLService,
    PipelineRunRequest,
)


def test_list_use_cases():
    svc = MultiSourceETLService()
    cases = svc.list_use_cases()
    assert len(cases) == 5, f"Expected 5 use cases, got {len(cases)}"
    ids = [c.id for c in cases]
    assert "ecommerce_360" in ids
    assert "healthcare_journey" in ids
    assert "fraud_detection" in ids
    assert "social_intelligence" in ids
    assert "iot_fleet" in ids
    print(f"[PASS] Found {len(cases)} use cases: {ids}")


def test_get_use_case():
    svc = MultiSourceETLService()
    info = svc.get_use_case("ecommerce_360")
    assert info is not None
    assert info.title == "Customer Lifetime Value & Personalization Engine"
    assert len(info.databases) == 5
    db_types = [d.type for d in info.databases]
    assert "postgres" in db_types
    assert "mongo" in db_types
    assert "redis" in db_types
    assert "cassandra" in db_types
    assert "elasticsearch" in db_types
    print(f"[PASS] ecommerce_360: {info.title} ({len(info.databases)} databases)")


def test_fraud_detection_schema():
    svc = MultiSourceETLService()
    info = svc.get_use_case("fraud_detection")
    assert info is not None
    assert "suspicious" in info.title.lower() or "sar" in info.title.lower()
    db_types = [d.type for d in info.databases]
    assert "mysql" in db_types
    assert "neo4j" in db_types
    found_pg = any("postgres" in d.type for d in info.databases)
    assert found_pg, "Expected a postgres database in fraud_detection"
    assert info.output_schema.get("case_id") or info.output_schema.get("transaction_id")
    print(f"[PASS] fraud_detection: {info.title}")


def test_healthcare_journey():
    svc = MultiSourceETLService()
    info = svc.get_use_case("healthcare_journey")
    assert info is not None
    db_types = [d.type for d in info.databases]
    assert "neo4j" in db_types, "Expected Neo4j for diagnosis graph"
    assert "influxdb" in db_types, "Expected InfluxDB for vitals time-series"
    print(f"[PASS] healthcare_journey: {info.title}")


def test_social_intelligence():
    svc = MultiSourceETLService()
    info = svc.get_use_case("social_intelligence")
    assert info is not None
    assert "content performance" in info.title.lower() or "trend" in info.title.lower()
    print(f"[PASS] social_intelligence: {info.title}")


def test_iot_fleet():
    svc = MultiSourceETLService()
    info = svc.get_use_case("iot_fleet")
    assert info is not None
    assert "fleet" in info.title.lower() and "maintenance" in info.title.lower()
    print(f"[PASS] iot_fleet: {info.title}")


def test_run_ecommerce_pipeline():
    svc = MultiSourceETLService()
    req = PipelineRunRequest(use_case="ecommerce_360", mode="seed")
    resp = svc.start_pipeline(req)
    assert resp.use_case == "ecommerce_360"
    assert resp.status.value == "pending"
    pipeline_id = resp.pipeline_id

    status = svc.run_pipeline(pipeline_id)
    assert status.status.value == "completed", f"Pipeline failed: {status.error}"
    assert len(status.steps) == 5, (
        f"Expected 5 DB extraction steps, got {len(status.steps)}"
    )
    for step in status.steps:
        assert step.status == "completed", f"Step {step.database} failed: {step.error}"
        assert step.rows_extracted > 0, f"Step {step.database} extracted 0 rows"

    result = svc.get_pipeline_result(pipeline_id)
    assert result is not None
    assert result.row_count > 0, "Expected at least 1 merged row"
    assert "customer_id" in result.columns or "user_id" in result.columns
    print(
        f"[PASS] ecommerce_360 pipeline: {result.row_count} rows, {len(result.columns)} columns"
    )


def test_run_all_pipelines():
    svc = MultiSourceETLService()
    use_cases = [
        "ecommerce_360",
        "healthcare_journey",
        "fraud_detection",
        "social_intelligence",
        "iot_fleet",
    ]
    for uc in use_cases:
        req = PipelineRunRequest(use_case=uc, mode="seed")
        resp = svc.start_pipeline(req)
        status = svc.run_pipeline(resp.pipeline_id)
        assert status.status.value == "completed", f"{uc} failed: {status.error}"
        result = svc.get_pipeline_result(resp.pipeline_id)
        assert result is not None
        assert result.row_count > 0, f"{uc}: 0 rows"
        print(f"[PASS] {uc}: {result.row_count} rows, {len(result.columns)} columns")


def test_unknown_use_case():
    svc = MultiSourceETLService()
    try:
        req = PipelineRunRequest(use_case="nonexistent", mode="seed")
        svc.start_pipeline(req)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown" in str(e) or "not found" in str(e)
        print(f"[PASS] Unknown use case correctly rejected: {e}")


def test_pipeline_not_found():
    svc = MultiSourceETLService()
    status = svc.get_pipeline_status("nonexistent_pipeline")
    assert status is None
    result = svc.get_pipeline_result("nonexistent_pipeline")
    assert result is None
    print("[PASS] Nonexistent pipeline returns None")


if __name__ == "__main__":
    test_list_use_cases()
    test_get_use_case()
    test_fraud_detection_schema()
    test_healthcare_journey()
    test_social_intelligence()
    test_iot_fleet()
    test_run_ecommerce_pipeline()
    test_run_all_pipelines()
    test_unknown_use_case()
    test_pipeline_not_found()
    print("\n=== All multi-source ETL tests passed ===")
