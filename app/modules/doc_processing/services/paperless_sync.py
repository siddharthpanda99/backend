"""Background synchronization service for Paperless-ngx post-consume pipeline (W5-L02).

Coordinates:
1. Paperless webhook ingestion event
2. Deep extraction via doc_processing.pdf_extractor.strategies.paperless_adapter
3. Tamper-evident provenance creation via rip.rip_documents.paperless_inventory
4. Semantic document inventory build for Nexus evidence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from common_lib.modules.doc_processing.config.flags import (
    PAPERLESS_DEEP_EXTRACTION_ENABLED,
    PAPERLESS_RIP_SYNC_ENABLED,
    is_enabled,
)
from common_lib.modules.doc_processing.paperless_client.events import (
    PaperlessPostConsumePayload,
)
from common_lib.modules.doc_processing.pdf_extractor.strategies.paperless_adapter import (
    extract_paperless_document,
)
from common_lib.modules.rip.rip_documents.paperless_inventory import (
    build_paperless_inventory,
    create_paperless_provenance,
)

logger = logging.getLogger(__name__)


async def handle_paperless_post_consume(
    payload: PaperlessPostConsumePayload,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute asynchronous post-consume processing workflow."""
    doc_id = payload.document_id
    checksum = payload.checksum
    logger.info("Starting post-consume background pipeline for Paperless doc %d", doc_id)

    results: Dict[str, Any] = {
        "document_id": doc_id,
        "checksum": checksum,
        "deep_extraction": None,
        "provenance": None,
        "inventory": None,
    }

    # 1. Deep Extraction Synergy
    if is_enabled(PAPERLESS_DEEP_EXTRACTION_ENABLED, tenant_id=tenant_id):
        try:
            extraction = extract_paperless_document(document_id=doc_id)
            results["deep_extraction"] = {
                "status": "COMPLETED",
                "blocks": extraction.get("block_count", 0),
                "confidence": extraction.get("confidence", 0.0),
            }
            extracted_text = extraction.get("text", "")
        except Exception as exc:
            logger.error("Deep extraction failed for Paperless doc %d: %s", doc_id, exc)
            results["deep_extraction"] = {"status": "FAILED", "error": str(exc)}
            extracted_text = ""
    else:
        extracted_text = ""

    # 2. RIP Provenance and Inventory Synchronization
    if is_enabled(PAPERLESS_RIP_SYNC_ENABLED, tenant_id=tenant_id):
        try:
            prov = create_paperless_provenance(
                document_id=doc_id,
                checksum=checksum,
                title=payload.file_name,
            )
            results["provenance"] = prov

            if extracted_text:
                inv = build_paperless_inventory(
                    document_id=doc_id,
                    text=extracted_text,
                    metadata={"file_name": payload.file_name, "checksum": checksum},
                )
                results["inventory"] = {
                    "status": "INDEXED",
                    "entity_count": inv.get("entity_count", 0),
                    "claim_count": inv.get("claim_count", 0),
                }
        except Exception as exc:
            logger.error("RIP sync failed for Paperless doc %d: %s", doc_id, exc)
            results["rip_sync_error"] = str(exc)

    return results
