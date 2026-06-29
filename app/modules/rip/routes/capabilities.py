"""RIP Capabilities route — returns all valid option sets for enum fields.

Provides the frontend RIP Builder with the complete list of valid values
for every predefined/enum field, so dropdowns are backed by the backend
source of truth rather than hardcoded frontend strings.

GET /api/v1/knowledge/rip/capabilities
"""

from fastapi import APIRouter
from common_lib.modules.rip.rip_capabilities import (
    CapabilitiesResponse,
    get_capabilities,
)

router = APIRouter(prefix="/rip/capabilities", tags=["RIP — Capabilities"])


@router.get("", response_model=CapabilitiesResponse)
async def get_capabilities_endpoint():
    """Return all valid option sets for enum/predefined fields in the RIP Builder."""
    return get_capabilities()
