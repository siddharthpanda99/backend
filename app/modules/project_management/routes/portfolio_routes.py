"""
PM Portfolio Routes — Thin API layer.

Registered at: /api/v1/jira/portfolios/

RBAC permissions: portfolio.read, portfolio.create, portfolio.update, portfolio.delete
"""
from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from app.modules.project_management.field_security_deps import (
    filter_single_response,
    filter_list_response,
    strip_field_security_metadata,
)


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)

from common_lib.modules.project_management.portfolio.service import PortfolioService
from common_lib.modules.project_management.schemas import (
    PortfolioCreate, PortfolioUpdate, PortfolioRead, PortfolioHealthRead,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[PortfolioRead])
def list_portfolios(
    request: Request,
    organization_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.read", "*", "portfolio"),
):
    """List all portfolios with optional org/status filter."""
    svc = PortfolioService(session)
    portfolios = svc.list_portfolios(
        organization_id=organization_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [p.model_dump() for p in portfolios]
    items = filter_list_response(request, session, "portfolio", items)
    return items


@router.post("/", response_model=PortfolioRead, status_code=201)
def create_portfolio(
    data: PortfolioCreate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.create", "*", "portfolio"),
):
    """Create a new portfolio."""
    svc = PortfolioService(session)
    try:
        return svc.create_portfolio(data)
    except Exception as e:
        logger.exception("Failed to create portfolio")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{portfolio_id}", response_model=PortfolioRead)
def get_portfolio(
    request: Request,
    portfolio_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.read", "*", "portfolio"),
):
    """Get a portfolio by ID."""
    svc = PortfolioService(session)
    portfolio = svc.get_portfolio(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    data = portfolio.model_dump()
    data = filter_single_response(request, session, "portfolio", data)
    return PortfolioRead.model_validate(strip_field_security_metadata(data))


@router.patch("/{portfolio_id}", response_model=PortfolioRead)
def update_portfolio(
    portfolio_id: str,
    data: PortfolioUpdate,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.update", "*", "portfolio"),
):
    """Update a portfolio."""
    svc = PortfolioService(session)
    portfolio = svc.update_portfolio(portfolio_id, data)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.delete("/{portfolio_id}", status_code=204)
def delete_portfolio(
    portfolio_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.delete", "*", "portfolio"),
):
    """Delete a portfolio."""
    svc = PortfolioService(session)
    if not svc.delete_portfolio(portfolio_id):
        raise HTTPException(status_code=404, detail="Portfolio not found")


@router.post("/{portfolio_id}/add-project", response_model=PortfolioRead)
def add_project_to_portfolio(
    portfolio_id: str,
    project_id: str = Query(...),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.update", "*", "portfolio"),
):
    """Add a project to a portfolio."""
    svc = PortfolioService(session)
    success = svc.add_project_to_portfolio(portfolio_id, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    portfolio = svc.get_portfolio(portfolio_id)
    return portfolio


@router.post("/{portfolio_id}/remove-project", response_model=PortfolioRead)
def remove_project_from_portfolio(
    portfolio_id: str,
    project_id: str = Query(...),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.update", "*", "portfolio"),
):
    """Remove a project from a portfolio."""
    svc = PortfolioService(session)
    success = svc.remove_project_from_portfolio(portfolio_id, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    portfolio = svc.get_portfolio(portfolio_id)
    return portfolio


@router.get("/{portfolio_id}/health", response_model=PortfolioHealthRead)
def get_portfolio_health(
    portfolio_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("portfolio.read", "*", "portfolio"),
):
    """Get health snapshot across all projects in a portfolio."""
    svc = PortfolioService(session)
    health = svc.get_portfolio_health(portfolio_id)
    if not health:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return health
