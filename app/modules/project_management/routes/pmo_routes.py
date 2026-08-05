"""
PMO, PPM, Strategy — REST Routes for Domain 03.

Endpoints:
- Demand Management: GET/POST /demands, GET/PUT/DELETE /demands/{id}, POST /demands/{id}/review
- Investment Proposals: GET/POST /proposals, GET/PUT/DELETE /proposals/{id}, POST /proposals/{id}/approve, POST /proposals/{id}/reject
- Strategic Initiatives: GET/POST /initiatives, GET/PUT/DELETE /initiatives/{id}
- Scenarios: GET/POST /scenarios, GET/PUT/DELETE /scenarios/{id}
- Benefits: GET/POST /benefits, GET/PUT/DELETE /benefits/{id}
- Analytics: GET /demands/analytics, GET /portfolios/{id}/analytics
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission

def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pmo", tags=["project_management", "pmo", "strategy"])


# ===========================================================================
# Helper: Instantiate PmoService lazily
# ===========================================================================

def _get_pmo_service(session: Session):
    from common_lib.modules.project_management.pmo.service import PmoService
    return PmoService(session=session)


# ===========================================================================
# Demand Management
# ===========================================================================

@router.get("/demands")
def list_demands(
    workspace_id: str = Query(..., description="Workspace ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, description="Max results"),
    offset: int = Query(0, description="Pagination offset"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("demand.read", "*", "demand"),
):
    """List demand items with filters."""
    svc = _get_pmo_service(session)
    return svc.list_demands(
        workspace_id=workspace_id, status=status,
        priority=priority, category=category,
        limit=limit, offset=offset,
    )


@router.get("/demands/{demand_id}")
def get_demand(demand_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("demand.read", "*", "demand")):
    """Get a demand item by ID."""
    svc = _get_pmo_service(session)
    item = svc.get_demand(demand_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Demand {demand_id} not found")
    return item.model_dump()


@router.post("/demands", status_code=201)
def create_demand(
    workspace_id: str = Query(...),
    title: str = Query(...),
    description: Optional[str] = Query(None),
    priority: str = Query("medium"),
    category: str = Query("general"),
    business_value: Optional[int] = Query(None),
    created_by: str = Query("system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("demand.create", "*", "demand"),
):
    """Submit a new demand item."""
    svc = _get_pmo_service(session)
    data = {
        "workspace_id": workspace_id, "title": title,
        "description": description, "priority": priority,
        "category": category, "business_value": business_value,
    }
    item = svc.create_demand(data, created_by=created_by)
    return item.model_dump()


@router.put("/demands/{demand_id}")
def update_demand(
    demand_id: str,
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    business_value: Optional[int] = Query(None),
    effort_estimate: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("demand.update", "*", "demand"),
):
    """Update a demand item."""
    svc = _get_pmo_service(session)
    data = {}
    if title is not None:
        data["title"] = title
    if description is not None:
        data["description"] = description
    if priority is not None:
        data["priority"] = priority
    if category is not None:
        data["category"] = category
    if business_value is not None:
        data["business_value"] = business_value
    if effort_estimate is not None:
        data["effort_estimate"] = effort_estimate

    item = svc.update_demand(demand_id, data)
    if not item:
        raise HTTPException(status_code=404, detail=f"Demand {demand_id} not found")
    return item.model_dump()


@router.delete("/demands/{demand_id}")
def delete_demand(demand_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("demand.delete", "*", "demand")):
    """Delete a demand item."""
    svc = _get_pmo_service(session)
    if not svc.delete_demand(demand_id):
        raise HTTPException(status_code=404, detail=f"Demand {demand_id} not found")
    return {"success": True, "demand_id": demand_id}


@router.post("/demands/{demand_id}/review")
def review_demand(
    demand_id: str,
    status: str = Query(..., description="Review status: approved, declined, on_hold"),
    reviewed_by: str = Query("system"),
    review_notes: Optional[str] = Query(None),
    linked_project_id: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("demand.update", "*", "demand"),
):
    """Review and approve/decline a demand item."""
    svc = _get_pmo_service(session)
    item = svc.review_demand(demand_id, status=status, reviewed_by=reviewed_by,
                             review_notes=review_notes, linked_project_id=linked_project_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Demand {demand_id} not found")
    return item.model_dump()


# ===========================================================================
# Investment Proposals
# ===========================================================================

@router.get("/proposals")
def list_proposals(
    workspace_id: str = Query(...),
    status: Optional[str] = Query(None, description="Filter by status"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("proposal.read", "*", "proposal"),
):
    """List investment proposals with filters."""
    svc = _get_pmo_service(session)
    return svc.list_proposals(workspace_id=workspace_id, status=status,
                              risk_level=risk_level, limit=limit, offset=offset)


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("proposal.read", "*", "proposal")):
    """Get an investment proposal by ID."""
    svc = _get_pmo_service(session)
    item = svc.get_proposal(proposal_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return item.model_dump()


@router.post("/proposals", status_code=201)
def create_proposal(
    workspace_id: str = Query(...),
    name: str = Query(...),
    description: Optional[str] = Query(None),
    proposed_budget: float = Query(0.0),
    expected_roi_pct: Optional[float] = Query(None),
    risk_level: str = Query("medium"),
    sponsor_id: str = Query("system"),
    business_case_summary: Optional[str] = Query(None),
    created_by: str = Query("system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("proposal.create", "*", "proposal"),
):
    """Create a new investment proposal."""
    svc = _get_pmo_service(session)
    data = {
        "workspace_id": workspace_id, "name": name,
        "description": description, "proposed_budget": proposed_budget,
        "expected_roi_pct": expected_roi_pct, "risk_level": risk_level,
        "sponsor_id": sponsor_id, "business_case_summary": business_case_summary,
    }
    item = svc.create_proposal(data, created_by=created_by)
    return item.model_dump()


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(
    proposal_id: str,
    approved_budget: Optional[float] = Query(None),
    reviewer: str = Query("system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("proposal.update", "*", "proposal"),
):
    """Approve an investment proposal."""
    svc = _get_pmo_service(session)
    item = svc.approve_proposal(proposal_id, approved_budget=approved_budget, reviewer=reviewer)
    if not item:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return item.model_dump()


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: str,
    reason: Optional[str] = Query(None),
    reviewer: str = Query("system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("proposal.update", "*", "proposal"),
):
    """Reject an investment proposal."""
    svc = _get_pmo_service(session)
    item = svc.reject_proposal(proposal_id, reason=reason or "", reviewer=reviewer)
    if not item:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return item.model_dump()


@router.delete("/proposals/{proposal_id}")
def delete_proposal(proposal_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("proposal.delete", "*", "proposal")):
    """Delete an investment proposal."""
    svc = _get_pmo_service(session)
    if not svc.delete_proposal(proposal_id):
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return {"success": True, "proposal_id": proposal_id}


# ===========================================================================
# Strategic Initiatives
# ===========================================================================

@router.get("/initiatives")
def list_initiatives(
    workspace_id: str = Query(...),
    status: Optional[str] = Query(None),
    pillar: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("initiative.read", "*", "initiative"),
):
    """List strategic initiatives."""
    svc = _get_pmo_service(session)
    return svc.list_initiatives(workspace_id=workspace_id, status=status,
                                pillar=pillar, limit=limit, offset=offset)


@router.get("/initiatives/{initiative_id}")
def get_initiative(initiative_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("initiative.read", "*", "initiative")):
    """Get a strategic initiative by ID."""
    svc = _get_pmo_service(session)
    item = svc.get_initiative(initiative_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Initiative {initiative_id} not found")
    return item.model_dump()


@router.post("/initiatives", status_code=201)
def create_initiative(
    workspace_id: str = Query(...),
    name: str = Query(...),
    description: Optional[str] = Query(None),
    strategic_pillar: str = Query("growth"),
    timeframe: Optional[str] = Query(None),
    portfolio_id: Optional[str] = Query(None),
    linked_goal_id: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    created_by: str = Query("system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("initiative.create", "*", "initiative"),
):
    """Create a new strategic initiative."""
    svc = _get_pmo_service(session)
    data = {
        "workspace_id": workspace_id, "name": name,
        "description": description, "strategic_pillar": strategic_pillar,
        "timeframe": timeframe, "portfolio_id": portfolio_id,
        "linked_goal_id": linked_goal_id, "owner_id": owner_id,
    }
    item = svc.create_initiative(data, created_by=created_by)
    return item.model_dump()


@router.put("/initiatives/{initiative_id}")
def update_initiative(
    initiative_id: str,
    name: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    progress_pct: Optional[float] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("initiative.update", "*", "initiative"),
):
    """Update a strategic initiative."""
    svc = _get_pmo_service(session)
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if status is not None:
        data["status"] = status
    if progress_pct is not None:
        data["progress_pct"] = progress_pct

    item = svc.update_initiative(initiative_id, data)
    if not item:
        raise HTTPException(status_code=404, detail=f"Initiative {initiative_id} not found")
    return item.model_dump()


@router.delete("/initiatives/{initiative_id}")
def delete_initiative(initiative_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("initiative.delete", "*", "initiative")):
    """Delete a strategic initiative."""
    svc = _get_pmo_service(session)
    if not svc.delete_initiative(initiative_id):
        raise HTTPException(status_code=404, detail=f"Initiative {initiative_id} not found")
    return {"success": True, "initiative_id": initiative_id}


# ===========================================================================
# Scenarios
# ===========================================================================

@router.get("/scenarios")
def list_scenarios(
    workspace_id: str = Query(...),
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("scenario.read", "*", "scenario"),
):
    """List what-if scenarios."""
    svc = _get_pmo_service(session)
    return svc.list_scenarios(workspace_id=workspace_id, status=status, limit=limit, offset=offset)


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("scenario.read", "*", "scenario")):
    """Get a scenario by ID."""
    svc = _get_pmo_service(session)
    item = svc.get_scenario(scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return item.model_dump()


@router.post("/scenarios", status_code=201)
def create_scenario(
    workspace_id: str = Query(...),
    name: str = Query(...),
    description: Optional[str] = Query(None),
    created_by: str = Query("system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("scenario.create", "*", "scenario"),
):
    """Create a new what-if scenario."""
    svc = _get_pmo_service(session)
    data = {
        "workspace_id": workspace_id, "name": name,
        "description": description,
    }
    item = svc.create_scenario(data, created_by=created_by)
    return item.model_dump()


@router.put("/scenarios/{scenario_id}")
def update_scenario(
    scenario_id: str,
    name: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("scenario.update", "*", "scenario"),
):
    """Update a scenario."""
    svc = _get_pmo_service(session)
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if status is not None:
        data["status"] = status
    item = svc.update_scenario(scenario_id, data)
    if not item:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return item.model_dump()


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("scenario.delete", "*", "scenario")):
    """Delete a scenario."""
    svc = _get_pmo_service(session)
    if not svc.delete_scenario(scenario_id):
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return {"success": True, "scenario_id": scenario_id}


# ===========================================================================
# Benefits Tracking
# ===========================================================================

@router.get("/benefits")
def list_benefits(
    workspace_id: str = Query(...),
    status: Optional[str] = Query(None),
    benefit_type: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("benefit.read", "*", "benefit"),
):
    """List benefits with filters."""
    svc = _get_pmo_service(session)
    return svc.list_benefits(workspace_id=workspace_id, status=status,
                             benefit_type=benefit_type, limit=limit, offset=offset)


@router.get("/benefits/{benefit_id}")
def get_benefit(benefit_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("benefit.read", "*", "benefit")):
    """Get a benefit by ID."""
    svc = _get_pmo_service(session)
    item = svc.get_benefit(benefit_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Benefit {benefit_id} not found")
    return item.model_dump()


@router.post("/benefits", status_code=201)
def create_benefit(
    workspace_id: str = Query(...),
    name: str = Query(...),
    description: Optional[str] = Query(None),
    benefit_type: str = Query("financial"),
    target_value: Optional[float] = Query(None),
    currency: str = Query("USD"),
    linked_project_id: Optional[str] = Query(None),
    linked_initiative_id: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    created_by: str = Query("system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("benefit.create", "*", "benefit"),
):
    """Create a new benefit tracking entry."""
    svc = _get_pmo_service(session)
    data = {
        "workspace_id": workspace_id, "name": name,
        "description": description, "benefit_type": benefit_type,
        "target_value": target_value, "currency": currency,
        "linked_project_id": linked_project_id,
        "linked_initiative_id": linked_initiative_id,
        "owner_id": owner_id,
    }
    item = svc.create_benefit(data, created_by=created_by)
    return item.model_dump()


@router.put("/benefits/{benefit_id}")
def update_benefit(
    benefit_id: str,
    name: Optional[str] = Query(None),
    target_value: Optional[float] = Query(None),
    actual_value: Optional[float] = Query(None),
    status: Optional[str] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("benefit.update", "*", "benefit"),
):
    """Update a benefit."""
    svc = _get_pmo_service(session)
    data = {}
    if name is not None:
        data["name"] = name
    if target_value is not None:
        data["target_value"] = target_value
    if actual_value is not None:
        data["actual_value"] = actual_value
    if status is not None:
        data["status"] = status
    item = svc.update_benefit(benefit_id, data)
    if not item:
        raise HTTPException(status_code=404, detail=f"Benefit {benefit_id} not found")
    return item.model_dump()


@router.delete("/benefits/{benefit_id}")
def delete_benefit(benefit_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("benefit.delete", "*", "benefit")):
    """Delete a benefit."""
    svc = _get_pmo_service(session)
    if not svc.delete_benefit(benefit_id):
        raise HTTPException(status_code=404, detail=f"Benefit {benefit_id} not found")
    return {"success": True, "benefit_id": benefit_id}


# ===========================================================================
# PMO Analytics
# ===========================================================================

@router.get("/demands/analytics")
def demand_analytics(
    workspace_id: str = Query(...),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("demand.read", "*", "demand"),
):
    """Get demand pipeline analytics."""
    svc = _get_pmo_service(session)
    return svc.get_demand_analytics(workspace_id)


@router.get("/portfolios/{portfolio_id}/analytics")
def portfolio_analytics(
    portfolio_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.read", "*", "portfolio"),
):
    """Get portfolio-level analytics with benefit realization."""
    svc = _get_pmo_service(session)
    return svc.get_portfolio_analytics(portfolio_id)


# ===========================================================================
# Capacity Planning — Domain 03.04
# ===========================================================================


@router.post("/capacity-plans", status_code=201)
def create_capacity_plan(
    workspace_id: str = Query(...),
    name: str = Query(...),
    description: Optional[str] = Query(None),
    plan_type: str = Query("project"),
    start_date: str = Query(...),
    end_date: str = Query(...),
    total_capacity_hours: float = Query(0.0),
    headcount: int = Query(0),
    period_type: str = Query("weekly"),
    created_by: str = Query("system"),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("capacity.create", "*", "capacity"),
):
    """Create a long-term capacity plan."""
    from datetime import date
    svc = _get_pmo_service(session)
    data = {
        "workspace_id": workspace_id, "name": name,
        "description": description, "plan_type": plan_type,
        "start_date": date.fromisoformat(start_date) if start_date else None,
        "end_date": date.fromisoformat(end_date) if end_date else None,
        "total_capacity_hours": total_capacity_hours,
        "headcount": headcount, "period_type": period_type,
    }
    plan = svc.create_capacity_plan(data, created_by=created_by)
    return plan.model_dump()


@router.get("/capacity-plans")
def list_capacity_plans(
    workspace_id: str = Query(...),
    plan_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("capacity.read", "*", "capacity"),
):
    """List capacity plans for a workspace."""
    svc = _get_pmo_service(session)
    return svc.list_capacity_plans(
        workspace_id=workspace_id, plan_type=plan_type,
        status=status, limit=limit, offset=offset,
    )


@router.get("/capacity-plans/{plan_id}")
def get_capacity_plan(plan_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("capacity.read", "*", "capacity")):
    """Get a single capacity plan by ID."""
    svc = _get_pmo_service(session)
    plan = svc.get_capacity_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Capacity plan {plan_id} not found")
    return plan.model_dump()


@router.put("/capacity-plans/{plan_id}")
def update_capacity_plan(
    plan_id: str,
    name: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    total_capacity_hours: Optional[float] = Query(None),
    planned_allocation_hours: Optional[float] = Query(None),
    actual_allocation_hours: Optional[float] = Query(None),
    headcount: Optional[int] = Query(None),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("capacity.update", "*", "capacity"),
):
    """Update a capacity plan."""
    svc = _get_pmo_service(session)
    data = {k: v for k, v in {
        "name": name, "description": description, "status": status,
        "total_capacity_hours": total_capacity_hours,
        "planned_allocation_hours": planned_allocation_hours,
        "actual_allocation_hours": actual_allocation_hours,
        "headcount": headcount,
    }.items() if v is not None}
    plan = svc.update_capacity_plan(plan_id, data)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Capacity plan {plan_id} not found")
    return plan.model_dump()


@router.delete("/capacity-plans/{plan_id}")
def delete_capacity_plan(plan_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("capacity.delete", "*", "capacity")):
    """Delete a capacity plan."""
    svc = _get_pmo_service(session)
    if not svc.delete_capacity_plan(plan_id):
        raise HTTPException(status_code=404, detail=f"Capacity plan {plan_id} not found")
    return {"success": True, "plan_id": plan_id}


@router.get("/capacity-utilization/{workspace_id}")
def get_capacity_utilization(workspace_id: str, session: Session = Depends(_get_session), _perm: None = require_permission("capacity.read", "*", "capacity")):
    """Get capacity utilization across all active plans."""
    svc = _get_pmo_service(session)
    return svc.get_capacity_utilization(workspace_id)
