"""PM Test Management REST Routes — test cases & test runs (Domain 32.x)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.modules.project_management.deps import get_pm_session
from app.modules.auth.dependencies import require_permission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/test-management", tags=["PM Test Management"])


class TestCaseCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None
    issue_id: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    expected_result: Optional[str] = None
    component_id: Optional[str] = None
    priority: str = "medium"


class TestRunCreate(BaseModel):
    project_id: str
    name: str
    test_case_ids: List[str] = []
    environment: Optional[str] = None


class TestRunExecute(BaseModel):
    status: str = "passed"
    actual_result: Optional[str] = None


def _svc(session: Session):
    from common_lib.modules.project_management.test_management.service import TestManagementService

    return TestManagementService(session=session)


@router.get("/test-cases")
def list_test_cases(project_id: Optional[str] = None, status: Optional[str] = None, component_id: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), session: Session = Depends(get_pm_session), _perm: None = require_permission("test.read", "*", "test")):
    """List test cases."""
    cases = _svc(session).list_test_cases(project_id=project_id, status=status, component_id=component_id, limit=limit, offset=offset)
    return {"test_cases": cases, "total": len(cases)}


@router.get("/test-cases/{test_case_id}")
def get_test_case(test_case_id: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("test.read", "*", "test")):
    """Get a single test case."""
    case = _svc(session).get_test_case(test_case_id=test_case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    return case


@router.post("/test-cases")
def create_test_case(req: TestCaseCreate, session: Session = Depends(get_pm_session), _perm: None = require_permission("test.write", "*", "test")):
    """Create a test case."""
    case = _svc(session).create_test_case(data=req.model_dump(exclude_none=True))
    return {"id": getattr(case, "id", None), "title": getattr(case, "title", req.title)}


@router.get("/test-runs")
def list_test_runs(project_id: Optional[str] = None, test_case_id: Optional[str] = None, status: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), session: Session = Depends(get_pm_session), _perm: None = require_permission("test.read", "*", "test")):
    """List test runs."""
    runs = _svc(session).list_test_runs(project_id=project_id, test_case_id=test_case_id, status=status, limit=limit, offset=offset)
    return {"test_runs": runs, "total": len(runs)}


@router.get("/test-runs/{run_id}")
def get_test_run(run_id: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("test.read", "*", "test")):
    """Get a single test run."""
    run = _svc(session).get_test_run(run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


@router.post("/test-runs")
def create_test_run(req: TestRunCreate, session: Session = Depends(get_pm_session), _perm: None = require_permission("test.write", "*", "test")):
    """Create a test run."""
    run = _svc(session).create_test_run(data=req.model_dump(exclude_none=True))
    return {"id": getattr(run, "id", None), "name": getattr(run, "name", req.name)}


@router.post("/test-runs/{run_id}/execute")
def execute_test_run(run_id: str, req: TestRunExecute, session: Session = Depends(get_pm_session), _perm: None = require_permission("test.write", "*", "test")):
    """Execute a test run."""
    run = _svc(session).execute_test_run(run_id=run_id, status=req.status, actual_result=req.actual_result)
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return {"id": getattr(run, "id", None), "status": getattr(run, "status", req.status)}


@router.get("/coverage/{project_id}")
def test_coverage(project_id: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("test.read", "*", "test")):
    """Get test coverage summary for a project."""
    return _svc(session).get_test_coverage(project_id=project_id)


@router.get("/summary/{project_id}")
def test_summary(project_id: str, session: Session = Depends(get_pm_session), _perm: None = require_permission("test.read", "*", "test")):
    """Get test run summary for a project."""
    return _svc(session).get_test_run_summary(project_id=project_id)
