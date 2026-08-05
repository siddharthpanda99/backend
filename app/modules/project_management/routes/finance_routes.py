"""Finance, Budget, Cost & Procurement REST Routes — Domain 08."""
import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.finance.service import FinanceService
from common_lib.modules.project_management.schemas import (
    BudgetCreate, BudgetUpdate, CostEntryCreate, VendorCreate, PurchaseRequestCreate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Budgets ---
@router.post("/budgets", tags=["PM Finance"])
async def create_budget(data: BudgetCreate, _perm: None = require_permission("budget.create", "*", "budget")):
    return FinanceService.create_budget(data)


@router.get("/budgets", tags=["PM Finance"])
async def list_budgets(
    project_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("budget.read", "*", "budget"),
):
    return FinanceService.list_budgets(project_id=project_id, limit=limit, offset=offset)


@router.get("/budgets/{budget_id}", tags=["PM Finance"])
async def get_budget(budget_id: str, _perm: None = require_permission("budget.read", "*", "budget")):
    budget = FinanceService.get_budget(budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.patch("/budgets/{budget_id}", tags=["PM Finance"])
async def update_budget(budget_id: str, data: BudgetUpdate, _perm: None = require_permission("budget.update", "*", "budget")):
    budget = FinanceService.update_budget(budget_id, data)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.get("/budgets/summary/{project_id}", tags=["PM Finance"])
async def get_budget_summary(project_id: str, _perm: None = require_permission("budget.read", "*", "budget")):
    return FinanceService.get_budget_summary(project_id)


# --- Cost Tracking ---
@router.post("/costs", tags=["PM Finance"])
async def record_cost(data: CostEntryCreate, _perm: None = require_permission("cost.create", "*", "cost")):
    return FinanceService.record_cost(data)


@router.get("/costs/{project_id}", tags=["PM Finance"])
async def list_costs(
    project_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("cost.read", "*", "cost"),
):
    return FinanceService.list_costs(project_id, limit=limit, offset=offset)


@router.get("/costs/summary/{project_id}", tags=["PM Finance"])
async def get_cost_summary(project_id: str, _perm: None = require_permission("cost.read", "*", "cost")):
    return FinanceService.get_cost_summary(project_id)


# --- EVM ---
@router.get("/evm/compute/{project_id}", tags=["PM Finance"])
async def compute_evm(project_id: str, _perm: None = require_permission("evm.read", "*", "evm")):
    return FinanceService.compute_evm(project_id)


@router.get("/evm/history/{project_id}", tags=["PM Finance"])
async def list_evm_snapshots(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
    _perm: None = require_permission("evm.read", "*", "evm"),
):
    return FinanceService.list_evm_snapshots(project_id, limit=limit)


# --- Vendors ---
@router.post("/vendors", tags=["PM Finance"])
async def create_vendor(data: VendorCreate, _perm: None = require_permission("vendor.create", "*", "vendor")):
    return FinanceService.create_vendor(data)


@router.get("/vendors", tags=["PM Finance"])
async def list_vendors(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("vendor.read", "*", "vendor"),
):
    return FinanceService.list_vendors(status=status, limit=limit, offset=offset)


@router.delete("/vendors/{vendor_id}", tags=["PM Finance"])
async def delete_vendor(vendor_id: str, _perm: None = require_permission("vendor.delete", "*", "vendor")):
    if not FinanceService.delete_vendor(vendor_id):
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {"ok": True}


# --- Purchase Requests ---
@router.post("/purchase-requests", tags=["PM Finance"])
async def create_purchase_request(data: PurchaseRequestCreate, _perm: None = require_permission("purchase.create", "*", "purchase")):
    return FinanceService.create_purchase_request(data)


@router.get("/purchase-requests", tags=["PM Finance"])
async def list_purchase_requests(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("purchase.read", "*", "purchase"),
):
    return FinanceService.list_purchase_requests(project_id=project_id, status=status, limit=limit, offset=offset)


@router.post("/purchase-requests/{pr_id}/approve", tags=["PM Finance"])
async def approve_purchase_request(pr_id: str, approved_by: str = Query(...), _perm: None = require_permission("purchase.update", "*", "purchase")):
    pr = FinanceService.approve_purchase_request(pr_id, approved_by)
    if not pr:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    return pr


# --- Timesheets ---
@router.get("/timesheets/user", tags=["PM Finance"])
async def get_timesheet(
    user_id: str = Query(...),
    date_from: str = Query(...),
    date_to: str = Query(...),
    _perm: None = require_permission("timesheet.read", "*", "timesheet"),
):
    d_from = date.fromisoformat(date_from)
    d_to = date.fromisoformat(date_to)
    return FinanceService.get_timesheet(user_id, d_from, d_to)


@router.get("/timesheets/project/{project_id}", tags=["PM Finance"])
async def get_project_timesheet(
    project_id: str,
    date_from: str = Query(...),
    date_to: str = Query(...),
    _perm: None = require_permission("timesheet.read", "*", "timesheet"),
):
    d_from = date.fromisoformat(date_from)
    d_to = date.fromisoformat(date_to)
    return FinanceService.get_project_timesheet(project_id, d_from, d_to)
