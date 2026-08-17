"""Reporting — benchmark suite (SSOT §19.3, Phase 47).

Submodule of the reporting router. Mounted at ``/api/v1/reporting`` with the
``/benchmarks/run`` endpoint — render-time, throughput (documents/hour for
office_source merge) and memory/CPU footprint per renderer.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

router = APIRouter(tags=["Reporting — Benchmarks"])


@router.post("/benchmarks/run", summary="Run the URP benchmark suite")
def run_benchmarks(payload: Dict[str, Any] = Body(default={})):
    from common_lib.modules.reporting.services.benchmark_service import BenchmarkService

    return BenchmarkService().run_all(
        formats=payload.get("formats"),
        office_iterations=int(payload.get("office_iterations", 25)),
    )
