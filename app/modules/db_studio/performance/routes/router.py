"""Thin backend route wrappers for Performance Profiler & Query Optimizer (UDS Module 11)."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.performance import (
    PerformanceProfilerService,
    ProfileRequest, ProfileOut, ProfileListOut,
    ExplainRequest, ExplainOut, ExplainCompareRequest, ExplainCompareOut,
    OptimizeRequest, OptimizationOut, RecommendationUpdate,
    IndexAdvisorRequest, IndexAdviceOut,
    SnapshotCreate, SnapshotOut, SnapshotCompareOut,
    DashboardOut,
    CapacityRequest, CapacityOut, CapacityForecastOut,
    PerformanceHistoryOut,
)

service = PerformanceProfilerService()


def get_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/performance", tags=["Performance Profiler"])

    @router.get("/dashboard", response_model=DashboardOut)
    async def get_dashboard(connection_id: str = None):
        return service.get_dashboard(connection_id)

    # ── Profiling ─────────────────────────────────────────────────────

    @router.post("/profile", response_model=ProfileOut)
    async def profile_query(req: ProfileRequest):
        return service.profile_query(req)

    @router.get("/profile/{profile_id}", response_model=ProfileOut)
    async def get_profile(profile_id: str):
        result = service.get_profile(profile_id)
        if not result:
            raise HTTPException(status_code=404, detail="Profile not found")
        return result

    @router.get("/profiles", response_model=ProfileListOut)
    async def list_profiles(connection_id: str = None, limit: int = 50):
        return service.list_profiles(connection_id, limit)

    # ── Explain Plans ─────────────────────────────────────────────────

    @router.post("/explain", response_model=ExplainOut)
    async def explain_query(req: ExplainRequest):
        return service.explain_query(req)

    @router.post("/explain/compare", response_model=ExplainCompareOut)
    async def compare_plans(req: ExplainCompareRequest):
        return service.compare_plans(req.plan_a_id, req.plan_b_id)

    # ── Optimization ──────────────────────────────────────────────────

    @router.post("/optimize", response_model=list[OptimizationOut])
    async def optimize_query(req: OptimizeRequest):
        return service.optimize_query(req)

    @router.get("/recommendations", response_model=list[OptimizationOut])
    async def list_recommendations(
        connection_id: str = None,
        rec_type: str = None,
        status: str = None,
        limit: int = 50,
    ):
        return service.list_recommendations(connection_id, rec_type, status, limit)

    @router.patch("/recommendations/{rec_id}", response_model=OptimizationOut)
    async def update_recommendation(rec_id: str, req: RecommendationUpdate):
        result = service.update_recommendation(rec_id, req)
        if not result:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        return result

    # ── Index Advisor ─────────────────────────────────────────────────

    @router.post("/index-advisor", response_model=list[IndexAdviceOut])
    async def analyze_indexes(req: IndexAdvisorRequest):
        return service.analyze_indexes(req)

    @router.get("/index-reports", response_model=list[IndexAdviceOut])
    async def list_index_reports(
        connection_id: str = None,
        table_name: str = None,
        rec_type: str = None,
        limit: int = 50,
    ):
        return service.list_index_reports(connection_id, table_name, rec_type, limit)

    # ── Snapshots ─────────────────────────────────────────────────────

    @router.post("/snapshots", response_model=SnapshotOut)
    async def create_snapshot(req: SnapshotCreate):
        return service.create_snapshot(req)

    @router.get("/snapshots", response_model=list[SnapshotOut])
    async def list_snapshots(
        connection_id: str = None,
        snapshot_type: str = None,
        limit: int = 50,
    ):
        return service.list_snapshots(connection_id, snapshot_type, limit)

    @router.get("/snapshots/compare", response_model=SnapshotCompareOut)
    async def compare_snapshots(baseline_id: str, current_id: str):
        return service.compare_snapshots(baseline_id, current_id)

    # ── Capacity ──────────────────────────────────────────────────────

    @router.post("/capacity", response_model=CapacityForecastOut)
    async def get_capacity(req: CapacityRequest):
        return service.get_capacity_metrics(req)

    @router.get("/capacity/metrics", response_model=list[CapacityOut])
    async def list_capacity_metrics(
        connection_id: str = None,
        metric_type: str = None,
        limit: int = 50,
    ):
        return service.list_capacity_metrics(connection_id, metric_type, limit)

    # ── History ───────────────────────────────────────────────────────

    @router.get("/history", response_model=PerformanceHistoryOut)
    async def get_history(connection_id: str = None, days: int = 7):
        return service.get_history(connection_id, days)

    return router
