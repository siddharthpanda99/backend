"""
Release and Milestone API Routes.

Endpoints:
- CRUD for releases and milestones
- Status transitions (unreleased/released/archived)
- Issue linking (assign/unassign issues to releases)
- Readiness tracking and stats
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from common_lib.modules.project_management.releases.service import ReleaseService, TestCaseService, EngineeringMetricsService
from common_lib.modules.project_management.schemas import (
    ReleaseCreate, ReleaseUpdate, ReleaseRead,
    TestCaseCreate, TestCaseUpdate, TestCaseRead,
    TestRunCreate, TestRunExecute, TestRunRead, TestRunSummary,
    EngineeringMetrics, EngineeringMetricsSnapshotRead, CycleTimeMetrics,
    LeadTimeMetrics, ThroughputMetrics, DefectMetrics, WipMetrics,
)

from app.modules.project_management.field_security_deps import (
    filter_single_response,
    filter_list_response,
    check_field_editable,
    strip_field_security_metadata,
)
from app.modules.auth.dependencies import require_permission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/releases", tags=["project_management", "releases"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=ReleaseRead, status_code=201)
def create_release(
    data: ReleaseCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("release.create", "*", "release"),
):
    """Create a new release or milestone."""
    try:
        svc = ReleaseService(session)
        release = svc.create_release(data)
        return release
    except Exception as e:
        logger.error("create_release failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[ReleaseRead])
def list_releases(
    request: Request,
    project_id: str = Query(...),
    status: Optional[str] = Query(None),
    is_milestone: Optional[bool] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("release.read", "*", "release"),
):
    """List releases for a project."""
    svc = ReleaseService(session)
    releases = svc.list_releases(project_id=project_id, status=status, is_milestone=is_milestone)
    items = [r.model_dump() for r in releases]
    items = filter_list_response(request, session, "release", items, project_id=project_id)
    return [ReleaseRead.model_validate(i) for i in items]


@router.get("/{release_id}", response_model=ReleaseRead)
def get_release(
    request: Request,
    release_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("release.read", "*", "release"),
):
    """Get a single release by ID."""
    svc = ReleaseService(session)
    release = svc.get_release(release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    data = release.model_dump()
    data = filter_single_response(request, session, "release", data, project_id=release.project_id)
    return ReleaseRead.model_validate(strip_field_security_metadata(data))


@router.put("/{release_id}", response_model=ReleaseRead)
def update_release(
    request: Request,
    release_id: str,
    data: ReleaseUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("release.update", "*", "release"),
):
    """Update a release."""
    svc = ReleaseService(session)
    existing = svc.get_release(release_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Release not found")
    update_fields = data.model_dump(exclude_unset=True)
    for field_key in update_fields:
        if not check_field_editable(request, session, "release", field_key, project_id=existing.project_id):
            raise HTTPException(status_code=403, detail=f"Field '{field_key}' is not editable for your role")
    release = svc.update_release(release_id, data)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


@router.delete("/{release_id}", status_code=204)
def delete_release(
    release_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("release.delete", "*", "release"),
):
    """Delete a release (unlinks all associated issues)."""
    svc = ReleaseService(session)
    success = svc.delete_release(release_id)
    if not success:
        raise HTTPException(status_code=404, detail="Release not found")
    return None


# ---------------------------------------------------------------------------
# Status Transitions
# ---------------------------------------------------------------------------

@router.post("/{release_id}/release", response_model=ReleaseRead)
def mark_released(release_id: str, session: Session = Depends(_get_session)):
    """Mark a release as released (shipped)."""
    svc = ReleaseService(session)
    release = svc.mark_released(release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


@router.post("/{release_id}/archive", response_model=ReleaseRead)
def mark_archived(release_id: str, session: Session = Depends(_get_session)):
    """Archive a release."""
    svc = ReleaseService(session)
    release = svc.mark_archived(release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


@router.post("/{release_id}/unrelease", response_model=ReleaseRead)
def mark_unreleased(release_id: str, session: Session = Depends(_get_session)):
    """Move a release back to unreleased."""
    svc = ReleaseService(session)
    release = svc.mark_unreleased(release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


# ---------------------------------------------------------------------------
# Issue Linking
# ---------------------------------------------------------------------------

@router.post("/{release_id}/issues/{issue_id}", status_code=200)
def add_issue_to_release(release_id: str, issue_id: str, session: Session = Depends(_get_session)):
    """Assign an issue to a release."""
    svc = ReleaseService(session)
    success = svc.add_issue_to_release(release_id, issue_id)
    if not success:
        raise HTTPException(status_code=404, detail="Release or issue not found, or project mismatch")
    return {"success": True, "release_id": release_id, "issue_id": issue_id}


@router.delete("/issues/{issue_id}", status_code=200)
def remove_issue_from_release(issue_id: str, session: Session = Depends(_get_session)):
    """Unlink an issue from its release."""
    svc = ReleaseService(session)
    success = svc.remove_issue_from_release(issue_id)
    if not success:
        raise HTTPException(status_code=404, detail="Issue not found or not linked to a release")
    return {"success": True, "issue_id": issue_id}


@router.get("/{release_id}/issues")
def list_release_issues(release_id: str, session: Session = Depends(_get_session)):
    """List all issues assigned to a release."""
    svc = ReleaseService(session)
    issues = svc.list_release_issues(release_id)
    return {
        "release_id": release_id,
        "issues": [i.model_dump() for i in issues],
        "total": len(issues),
    }


# ---------------------------------------------------------------------------
# Readiness Tracking
# ---------------------------------------------------------------------------

@router.get("/{release_id}/readiness")
def get_release_readiness(release_id: str, session: Session = Depends(_get_session)):
    """Get release readiness report with completion %, blockers, days remaining."""
    svc = ReleaseService(session)
    readiness = svc.get_release_readiness(release_id)
    if not readiness:
        raise HTTPException(status_code=404, detail="Release not found")
    return readiness


@router.post("/{release_id}/refresh-counters", response_model=ReleaseRead)
def refresh_release_counters(release_id: str, session: Session = Depends(_get_session)):
    """Recalculate all readiness counters from current issue state."""
    svc = ReleaseService(session)
    release = svc.refresh_release_counters(release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


# ---------------------------------------------------------------------------
# Aggregate Stats
# ---------------------------------------------------------------------------

@router.get("/stats/{project_id}")
def get_release_stats(project_id: str, session: Session = Depends(_get_session)):
    """Get aggregated release stats for a project."""
    svc = ReleaseService(session)
    return svc.get_release_stats(project_id)


# ===========================================================================
# Test Case Routes — Domain 21.06
# ===========================================================================


@router.post("/test-cases", response_model=TestCaseRead, status_code=201, tags=["test-cases"])
def create_test_case(data: TestCaseCreate, session: Session = Depends(_get_session)):
    """Create a new test case."""
    svc = TestCaseService(session)
    tc = svc.create_test_case(data.model_dump())
    return tc


@router.get("/test-cases", tags=["test-cases"])
def list_test_cases(
    project_id: str = Query(...),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    component_id: Optional[str] = Query(None),
    is_automated: Optional[bool] = Query(None),
    session: Session = Depends(_get_session),
):
    """List test cases with optional filters."""
    svc = TestCaseService(session)
    cases = svc.list_test_cases(
        project_id=project_id, status=status, priority=priority,
        component_id=component_id, is_automated=is_automated,
    )
    return {"items": [c.model_dump() for c in cases], "total": len(cases)}


@router.get("/test-cases/{test_case_id}", response_model=TestCaseRead, tags=["test-cases"])
def get_test_case(test_case_id: str, session: Session = Depends(_get_session)):
    """Get a single test case by ID."""
    svc = TestCaseService(session)
    tc = svc.get_test_case(test_case_id)
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    return tc


@router.put("/test-cases/{test_case_id}", response_model=TestCaseRead, tags=["test-cases"])
def update_test_case(test_case_id: str, data: TestCaseUpdate, session: Session = Depends(_get_session)):
    """Update a test case."""
    svc = TestCaseService(session)
    tc = svc.update_test_case(test_case_id, data.model_dump(exclude_unset=True))
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    return tc


@router.delete("/test-cases/{test_case_id}", status_code=204, tags=["test-cases"])
def delete_test_case(test_case_id: str, session: Session = Depends(_get_session)):
    """Delete a test case."""
    svc = TestCaseService(session)
    success = svc.delete_test_case(test_case_id)
    if not success:
        raise HTTPException(status_code=404, detail="Test case not found")
    return None


@router.get("/test-cases/folders/{project_id}", tags=["test-cases"])
def get_test_case_folders(project_id: str, session: Session = Depends(_get_session)):
    """Get distinct folder paths for a project's test cases."""
    svc = TestCaseService(session)
    return {"folders": svc.get_test_case_folders(project_id)}


# ── Test Run Endpoints ────────────────────────────────────────────────────────


@router.post("/test-runs", response_model=TestRunRead, status_code=201, tags=["test-runs"])
def create_test_run(data: TestRunCreate, session: Session = Depends(_get_session)):
    """Create a new test run (schedule a test case for execution)."""
    svc = TestCaseService(session)
    tr = svc.create_test_run(data.model_dump())
    return tr


@router.post("/test-runs/{test_run_id}/execute", response_model=TestRunRead, tags=["test-runs"])
def execute_test_run(test_run_id: str, data: TestRunExecute, session: Session = Depends(_get_session)):
    """Execute a test run and record the result."""
    svc = TestCaseService(session)
    tr = svc.execute_test_run(
        test_run_id=test_run_id,
        status=data.status,
        actual_result=data.actual_result,
        notes=data.notes,
        evidence_urls=data.evidence_urls,
        duration_minutes=data.duration_minutes,
        executed_by=data.executed_by,
    )
    if not tr:
        raise HTTPException(status_code=404, detail="Test run not found")
    return tr


@router.get("/test-runs", tags=["test-runs"])
def list_test_runs(
    test_case_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    release_id: Optional[str] = Query(None),
    sprint_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
):
    """List test runs with optional filters."""
    svc = TestCaseService(session)
    runs = svc.list_test_runs(
        test_case_id=test_case_id, project_id=project_id,
        release_id=release_id, sprint_id=sprint_id, status=status,
    )
    return {"items": [r.model_dump() for r in runs], "total": len(runs)}


@router.get("/test-runs/summary/{project_id}", response_model=TestRunSummary, tags=["test-runs"])
def get_test_run_summary(project_id: str, session: Session = Depends(_get_session)):
    """Get test run summary statistics for a project."""
    svc = TestCaseService(session)
    return svc.get_test_run_summary(project_id)


# ===========================================================================
# Engineering Metrics Routes — Domain 21.05
# ===========================================================================


@router.get("/metrics/cycle-time/{project_id}", response_model=CycleTimeMetrics, tags=["engineering-metrics"])
def get_cycle_time(project_id: str, days_back: int = Query(30, ge=1, le=365), session: Session = Depends(_get_session)):
    """Calculate cycle time for recently completed issues."""
    svc = EngineeringMetricsService(session)
    return svc.get_cycle_time(project_id, days_back)


@router.get("/metrics/lead-time/{project_id}", response_model=LeadTimeMetrics, tags=["engineering-metrics"])
def get_lead_time(project_id: str, days_back: int = Query(30, ge=1, le=365), session: Session = Depends(_get_session)):
    """Calculate lead time from creation to completion."""
    svc = EngineeringMetricsService(session)
    return svc.get_lead_time(project_id, days_back)


@router.get("/metrics/throughput/{project_id}", response_model=ThroughputMetrics, tags=["engineering-metrics"])
def get_throughput(project_id: str, days_back: int = Query(30, ge=1, le=365), session: Session = Depends(_get_session)):
    """Calculate throughput — issues completed per day."""
    svc = EngineeringMetricsService(session)
    return svc.get_throughput(project_id, days_back)


@router.get("/metrics/defects/{project_id}", response_model=DefectMetrics, tags=["engineering-metrics"])
def get_defect_metrics(project_id: str, days_back: int = Query(30, ge=1, le=365), session: Session = Depends(_get_session)):
    """Calculate defect/quality metrics."""
    svc = EngineeringMetricsService(session)
    return svc.get_defect_metrics(project_id, days_back)


@router.get("/metrics/wip/{project_id}", response_model=WipMetrics, tags=["engineering-metrics"])
def get_wip_metrics(project_id: str, session: Session = Depends(_get_session)):
    """Get work-in-progress metrics."""
    svc = EngineeringMetricsService(session)
    return svc.get_wip_metrics(project_id)


@router.get("/metrics/all/{project_id}", response_model=EngineeringMetrics, tags=["engineering-metrics"])
def get_all_metrics(project_id: str, days_back: int = Query(30, ge=1, le=365), session: Session = Depends(_get_session)):
    """Get all engineering metrics at once."""
    svc = EngineeringMetricsService(session)
    return svc.get_all_metrics(project_id, days_back)


@router.post("/metrics/snapshot/{project_id}", tags=["engineering-metrics"])
def snapshot_metrics(project_id: str, session: Session = Depends(_get_session)):
    """Take a metrics snapshot for trend analysis."""
    svc = EngineeringMetricsService(session)
    snap = svc.snapshot_metrics(project_id)
    return {"id": snap.id, "project_id": snap.project_id, "snap_date": snap.snap_date.isoformat()}


@router.get("/metrics/snapshots/{project_id}", tags=["engineering-metrics"])
def get_metrics_snapshots(project_id: str, days_back: int = Query(90, ge=1, le=365), session: Session = Depends(_get_session)):
    """Get historical metrics snapshots for trend charts."""
    svc = EngineeringMetricsService(session)
    snaps = svc.get_metrics_snapshots(project_id, days_back)
    return {"items": [s.model_dump() for s in snaps], "total": len(snaps)}
