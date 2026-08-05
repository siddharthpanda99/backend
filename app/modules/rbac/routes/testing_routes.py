"""FastAPI routes for RBAC Testing, Fuzzing, Verification — SSOT 32."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/testing", tags=["rbac-testing"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class FuzzRequest(BaseModel):
    count: int = 25
    strategy: str = "random"


class VerifyRequest(BaseModel):
    user_id: int
    permission_name: str
    resource_id: Optional[str] = None
    expected_result: bool = False


@router.post("/fuzz")
async def fuzz_permission_checks(request: FuzzRequest) -> Dict[str, Any]:
    """Generate and run random fuzz tests against the authorization engine."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.testing.service import PermissionFuzzer, AuthorizationVerifier, FuzzStrategy
        fuzzer = PermissionFuzzer(session)
        verifier = AuthorizationVerifier(session)
        strategy_enum = getattr(FuzzStrategy, request.strategy.upper(), FuzzStrategy.RANDOM)
        scenarios = fuzzer.generate_scenarios(strategy=strategy_enum, count=request.count)
        report = verifier.run_batch(scenarios)
        return {
            "total": report["total"],
            "passed": report["passed"],
            "failed": report["failed"],
            "pass_rate": report["pass_rate"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/verify")
async def run_verification_scenario(request: VerifyRequest) -> Dict[str, Any]:
    """Run a single structured verification scenario against the authorization engine."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.testing.service import AuthorizationVerifier, VerificationScenario
        verifier = AuthorizationVerifier(session)
        scenario = VerificationScenario(
            name=f"verify_{request.user_id}_{request.permission_name}",
            description=f"Verification: user={request.user_id}, perm={request.permission_name}",
            user_id=request.user_id,
            permission_name=request.permission_name,
            resource_id=request.resource_id,
            expected_result=request.expected_result,
        )
        result = verifier.run_scenario(scenario)
        return {
            "passed": result.passed,
            "expected": result.expected,
            "actual": result.actual,
            "error": result.error or "",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/coverage")
async def get_test_coverage() -> Dict[str, Any]:
    """Get a coverage report for RBAC authorization testing."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.testing.service import AuthorizationVerifier
        verifier = AuthorizationVerifier(session)
        return verifier.get_coverage_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
