"""Shared helpers + lazy service accessors for the reporting route submodules."""

from __future__ import annotations

import base64
from typing import Any, Dict


def _templates():
    from common_lib.modules.reporting.services.template_service import TemplateService

    return TemplateService()


def _rendering():
    from common_lib.modules.reporting.services.render_service import RenderingService

    return RenderingService()


def _commands():
    from common_lib.modules.reporting.services.agent_commands import ReportCommands

    return ReportCommands()


def _workflow():
    from common_lib.modules.reporting.services.workflow_integration import (
        ReportWorkflowIntegration,
    )

    return ReportWorkflowIntegration()


def _marketplace():
    from common_lib.modules.reporting.services.marketplace_service import (
        ReportMarketplace,
    )

    return ReportMarketplace()


def _editing():
    from common_lib.modules.reporting.services.editing_service import EditingService

    return EditingService()


def _assets():
    from common_lib.modules.reporting.services.asset_service import AssetManager

    return AssetManager()


def _brand_kits():
    from common_lib.modules.reporting.services.asset_service import BrandKitService

    return BrandKitService()


def _audit():
    from common_lib.modules.reporting.services.audit_service import AuditService

    return AuditService()


def _docs():
    from common_lib.modules.reporting.services.document_store import (
        GeneratedDocumentStore,
    )

    return GeneratedDocumentStore()


def _b64(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Base64-encode binary outputs for JSON transport."""
    for output in payload.get("outputs", []):
        content = output.get("content")
        if isinstance(content, bytes):
            output["content"] = base64.b64encode(content).decode()
            output["encoding"] = "base64"
    return payload
