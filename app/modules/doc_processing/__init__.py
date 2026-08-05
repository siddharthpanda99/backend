"""Doc Processing module — PDF extraction + Excel/spreadsheet + universal document ops.

Combines routes from:
  - routes/router.py (PDF extraction)
  - routes/general_router.py (DocProcessingService universal ops)
  - excel/routes.py (Excel/spreadsheet operations)
  - lazy_routes.py (Lazy Engine query pipeline)

Usage in routers.py:
    from app.modules.doc_processing import doc_processing_router
    ROUTER_DEFINITIONS.append({"router": doc_processing_router, ...})
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.doc_processing.routes.router import router as pdf_router
from app.modules.doc_processing.routes.general_router import router as general_router
from app.modules.doc_processing.excel.routes import router as excel_router
from app.modules.doc_processing.lazy_routes import router as lazy_router

doc_processing_router = APIRouter()

# Merge PDF routes
for route in pdf_router.routes:
    doc_processing_router.routes.append(route)

# Merge General DocProcessingService routes
for route in general_router.routes:
    doc_processing_router.routes.append(route)

# Merge Excel routes
for route in excel_router.routes:
    doc_processing_router.routes.append(route)

# Merge Lazy Engine routes
for route in lazy_router.routes:
    doc_processing_router.routes.append(route)

router = doc_processing_router

__all__ = ["router"]
