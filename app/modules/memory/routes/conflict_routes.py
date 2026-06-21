"""Memory Conflict Resolution API Routes.

Provides endpoints to detect, list, view, and resolve memory conflicts
using the existing ConflictDetector and ConflictResolver primitives.
Conflicts are detected by scanning knowledge entries for direct contradictions
(subject+predicate matches with different object values).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body

router = APIRouter(prefix="/conflicts", tags=["Memory Conflict Resolution"])

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory conflict store — persists for the lifetime of the server process.
# In production this would be backed by the database via the storage service.
# ---------------------------------------------------------------------------

_conflicts: Dict[str, Dict[str, Any]] = {}
_resolutions: Dict[str, Dict[str, Any]] = {}


def _generate_id() -> str:
    return f"conf_{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_knowledge_entry(entry: Dict[str, Any]) -> Any:
    """Build a KnowledgeEntry-compatible object from a dict."""
    from common_lib.modules.memory.memory_semantics.knowledge import (
        KnowledgeEntry, PrimarySource, ProvenanceRecord, LifecycleMeta, KnowledgeScope,
    )

    prov_dict = entry.get("provenance", {})
    primary_src = prov_dict.get("primary_source", {})
    primary = PrimarySource(
        source_id=primary_src.get("source_id", "unknown"),
        source_type=primary_src.get("source_type", "api"),
    )
    provenance = ProvenanceRecord(primary_source=primary)

    lifecycle_dict = entry.get("lifecycle", {})
    lifecycle = LifecycleMeta(
        created_by=lifecycle_dict.get("created_by", "system"),
        created_at=lifecycle_dict.get("created_at", _now()),
        last_verified=lifecycle_dict.get("last_verified", _now()),
    )

    scope_dict = entry.get("scope", {})
    scope = KnowledgeScope(
        geography=scope_dict.get("geography", "global"),
    )

    return KnowledgeEntry(
        knowledge_id=entry.get("knowledge_id", entry.get("id", _generate_id())),
        claim=entry.get("claim", ""),
        domain=entry.get("domain", "general"),
        subject=entry.get("subject", ""),
        predicate=entry.get("predicate", ""),
        object=entry.get("object", entry.get("object_value", "")),
        confidence=entry.get("confidence", 0.5),
        lifecycle=lifecycle,
        provenance=provenance,
        scope=scope,
    )


# ---------------------------------------------------------------------------
# Conflict Detection
# ---------------------------------------------------------------------------

def _scan_for_conflicts(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run pairwise conflict detection across all knowledge entries.

    Uses ConflictDetector.detect_conflict() to find real contradictions.
    Caches results by conflict_id for later retrieval and resolution.
    """
    from common_lib.modules.memory.memory_causal.conflict import (
        ConflictDetector,
        ConflictRecord,
    )

    detected: List[Dict[str, Any]] = []
    seen_pairs: set = set()

    knowledge_entries = []
    for e in entries:
        try:
            ke = _build_knowledge_entry(e)
            knowledge_entries.append(ke)
        except Exception as ex:
            logger.warning(f"Skipping invalid entry: {ex}")

    for i in range(len(knowledge_entries)):
        for j in range(i + 1, len(knowledge_entries)):
            pair_key = (knowledge_entries[i].knowledge_id, knowledge_entries[j].knowledge_id)
            reverse_key = (knowledge_entries[j].knowledge_id, knowledge_entries[i].knowledge_id)
            if pair_key in seen_pairs or reverse_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            try:
                conflict: Optional[ConflictRecord] = ConflictDetector.detect_conflict(
                    knowledge_entries[i], knowledge_entries[j]
                )
                if conflict is not None:
                    conflict_dict = conflict.model_dump()
                    conflict_dict["conflict_id"] = conflict.conflict_id
                    _conflicts[conflict.conflict_id] = conflict_dict
                    detected.append(conflict_dict)
            except Exception as ex:
                logger.debug(f"No conflict between pair: {ex}")

    return detected


def _get_knowledge_entries_from_service() -> List[Dict[str, Any]]:
    """Attempt to fetch real knowledge entries from the integration/memory service."""
    try:
        from common_lib.modules.memory.integration import get_memory_integration
        from common_lib.modules.memory.integration import MemorySubModule

        integration = get_memory_integration()
        import anyio
        try:
            anyio.run(integration.initialize)
        except Exception:
            pass

        semantics_service = None
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            semantics_service = loop.run_until_complete(
                integration.get_integrated_service("semantics")
            )
            loop.close()
        except Exception:
            pass

        if semantics_service and hasattr(semantics_service, "get_knowledge_entries"):
            try:
                result = semantics_service.get_knowledge_entries()
                if isinstance(result, list):
                    return result
            except Exception:
                pass

        # Fallback: try the storage service
        from common_lib.modules.memory.memory_storage.service import get_storage_service
        svc = get_storage_service()
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(svc.list_memories(limit=200))
            loop.close()
            memories = result if isinstance(result, list) else result.get("memories", result.get("data", []))
            if memories and len(memories) > 0:
                return memories
        except Exception:
            pass
    except ImportError:
        logger.debug("Integration module not available, using seed data")

    return []


def _get_seed_entries() -> List[Dict[str, Any]]:
    """Provide seed knowledge entries when no real data source is available.

    These demonstrate the conflict detection system with realistic contradictions
    and are replaced by real data when the backend services are connected.
    """
    return [
        {
            "knowledge_id": "know_seed_001",
            "claim": "ACME Corp payment terms are Net 30",
            "domain": "vendor_master",
            "subject": "ACME Corp",
            "predicate": "has_payment_terms",
            "object": "Net 30",
            "confidence": 0.90,
            "lifecycle": {"created_by": "erp_sync", "created_at": "2025-01-15T08:00:00Z", "last_verified": "2025-01-15T08:00:00Z"},
            "provenance": {"primary_source": {"source_id": "erp_sap", "source_type": "enterprise_erp"}},
            "scope": {"geography": "global"},
        },
        {
            "knowledge_id": "know_seed_002",
            "claim": "ACME Corp payment terms are Net 60",
            "domain": "vendor_master",
            "subject": "ACME Corp",
            "predicate": "has_payment_terms",
            "object": "Net 60",
            "confidence": 0.65,
            "lifecycle": {"created_by": "vendor_portal", "created_at": "2025-03-20T14:30:00Z", "last_verified": "2025-03-20T14:30:00Z"},
            "provenance": {"primary_source": {"source_id": "vendor_self_service", "source_type": "web_portal"}},
            "scope": {"geography": "north_america"},
        },
        {
            "knowledge_id": "know_seed_003",
            "claim": "Data retention period is 90 days for customer records",
            "domain": "compliance",
            "subject": "Customer Records",
            "predicate": "has_retention_period",
            "object": "90 days",
            "confidence": 0.95,
            "lifecycle": {"created_by": "legal_team", "created_at": "2024-11-01T09:00:00Z", "last_verified": "2025-02-01T09:00:00Z"},
            "provenance": {"primary_source": {"source_id": "compliance_doc_v2", "source_type": "policy_document"}},
            "scope": {"geography": "eu"},
        },
        {
            "knowledge_id": "know_seed_004",
            "claim": "Data retention period is 180 days for customer records",
            "domain": "compliance",
            "subject": "Customer Records",
            "predicate": "has_retention_period",
            "object": "180 days",
            "confidence": 0.80,
            "lifecycle": {"created_by": "engineering", "created_at": "2025-04-10T11:00:00Z", "last_verified": "2025-04-10T11:00:00Z"},
            "provenance": {"primary_source": {"source_id": "internal_audit_q1", "source_type": "audit_report"}},
            "scope": {"geography": "global"},
        },
        {
            "knowledge_id": "know_seed_005",
            "claim": "API rate limit is 1000 requests per minute for standard tier",
            "domain": "engineering",
            "subject": "Standard API Tier",
            "predicate": "has_rate_limit",
            "object": "1000 req/min",
            "confidence": 0.85,
            "lifecycle": {"created_by": "api_team", "created_at": "2025-02-10T10:00:00Z", "last_verified": "2025-02-10T10:00:00Z"},
            "provenance": {"primary_source": {"source_id": "api_docs_v3", "source_type": "documentation"}},
            "scope": {"geography": "global"},
        },
        {
            "knowledge_id": "know_seed_006",
            "claim": "API rate limit is 500 requests per minute for standard tier",
            "domain": "engineering",
            "subject": "Standard API Tier",
            "predicate": "has_rate_limit",
            "object": "500 req/min",
            "confidence": 0.70,
            "lifecycle": {"created_by": "support_ticket", "created_at": "2025-05-05T16:00:00Z", "last_verified": "2025-05-05T16:00:00Z"},
            "provenance": {"primary_source": {"source_id": "customer_support_log", "source_type": "support_system"}},
            "scope": {"geography": "global"},
        },
        {
            "knowledge_id": "know_seed_007",
            "claim": "Server maintenance window is Sunday 2 AM UTC",
            "domain": "operations",
            "subject": "Production Servers",
            "predicate": "has_maintenance_window",
            "object": "Sunday 2 AM UTC",
            "confidence": 0.92,
            "lifecycle": {"created_by": "devops", "created_at": "2025-01-05T12:00:00Z", "last_verified": "2025-03-01T12:00:00Z"},
            "provenance": {"primary_source": {"source_id": "runbook_v4", "source_type": "operations_runbook"}},
            "scope": {"geography": "global"},
        },
        {
            "knowledge_id": "know_seed_008",
            "claim": "Server maintenance window is Saturday 4 AM UTC",
            "domain": "operations",
            "subject": "Production Servers",
            "predicate": "has_maintenance_window",
            "object": "Saturday 4 AM UTC",
            "confidence": 0.55,
            "lifecycle": {"created_by": "sre_team", "created_at": "2025-04-20T08:00:00Z", "last_verified": "2025-04-20T08:00:00Z"},
            "provenance": {"primary_source": {"source_id": "sre_rotation_doc", "source_type": "team_wiki"}},
            "scope": {"geography": "global"},
        },
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_conflicts(
    status: Optional[str] = Query(None, description="Filter by status: open, resolved, escalated, dismissed"),
    severity: Optional[str] = Query(None, description="Filter by severity: critical, high, medium, low"),
    domain: Optional[str] = Query(None, description="Filter by domain name"),
    refresh: bool = Query(False, description="Re-scan knowledge entries for new conflicts"),
):
    """List all detected memory conflicts.

    By default returns cached conflicts. Pass `refresh=true` to re-scan
    knowledge entries and detect new conflicts using ConflictDetector.
    """
    if refresh:
        entries = _get_knowledge_entries_from_service()
        if not entries:
            logger.info("No entries from service, using seed data for conflict detection")
            entries = _get_seed_entries()
        _scan_for_conflicts(entries)

    results = list(_conflicts.values())

    if status:
        results = [c for c in results if c.get("status") == status]
    if severity:
        results = [c for c in results if c.get("severity") == severity]
    if domain:
        results = [c for c in results if c.get("domain", "").lower() == domain.lower()]

    # Enrich with resolution info
    for c in results:
        cid = c.get("conflict_id")
        if cid and cid in _resolutions:
            c["resolution"] = _resolutions[cid]

    return {
        "conflicts": sorted(results, key=lambda c: c.get("detected_at", ""), reverse=True),
        "total": len(results),
        "source": "live_scan" if refresh else "cache",
    }


@router.get("/{conflict_id}")
async def get_conflict(conflict_id: str):
    """Get a single conflict with full detail including participant data."""
    conflict = _conflicts.get(conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")

    result = dict(conflict)
    if conflict_id in _resolutions:
        result["resolution"] = _resolutions[conflict_id]
    return {"conflict": result}


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """Resolve a detected conflict.

    Resolves using ConflictResolver.resolve() with optional human arbitration.

    For automated resolution, the backend tries recency/confidence/source strategies.
    For human arbitration, provide `human_decision` (entry_id of the winner) and
    optional `human_notes`.

    Body:
    ```json
    {
        "human_decision": "know_seed_002",     // optional — winner entry_id
        "human_notes": "Approved policy change", // optional
        "strategy": "human_arbitration"          // optional, default: auto
    }
    ```
    """
    conflict = _conflicts.get(conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")

    if conflict.get("status") in ("resolved", "escalated", "dismissed"):
        raise HTTPException(status_code=400, detail=f"Conflict is already {conflict['status']}")

    from common_lib.modules.memory.memory_causal.conflict import (
        ConflictResolver,
        ConflictRecord,
    )

    # Reconstruct ConflictRecord from stored dict
    conflict_record = ConflictRecord(**conflict)

    # Get participant entry data
    entries = _get_knowledge_entries_from_service()
    if not entries:
        entries = _get_seed_entries()

    entry_a_id = conflict.get("conflicting_entries", {}).get("entry_a", {}).get("entry_id", "")
    entry_b_id = conflict.get("conflicting_entries", {}).get("entry_b", {}).get("entry_id", "")

    entry_a_dict = next((e for e in entries if e.get("knowledge_id", e.get("id")) == entry_a_id), None)
    entry_b_dict = next((e for e in entries if e.get("knowledge_id", e.get("id")) == entry_b_id), None)

    if not entry_a_dict or not entry_b_dict:
        raise HTTPException(status_code=500, detail="Could not find conflicting entries for resolution")

    entry_a = _build_knowledge_entry(entry_a_dict)
    entry_b = _build_knowledge_entry(entry_b_dict)

    try:
        human_decision = payload.get("human_decision")
        human_notes = payload.get("human_notes")

        resolution = ConflictResolver.resolve(
            conflict_record,
            entry_a,
            entry_b,
            human_decision=human_decision,
            human_notes=human_notes,
        )

        resolution_dict = resolution.model_dump()
        _resolutions[conflict_id] = resolution_dict

        # Update conflict status
        conflict["status"] = "resolved"
        conflict["resolution"] = resolution_dict
        _conflicts[conflict_id] = conflict

        return {
            "conflict_id": conflict_id,
            "status": "resolved",
            "resolution": resolution_dict,
        }

    except ValueError as e:
        # Critical conflict without human arbitration
        conflict["status"] = "escalated"
        _conflicts[conflict_id] = conflict
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Resolution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Resolution failed: {str(e)}")


@router.post("/{conflict_id}/dismiss")
async def dismiss_conflict(
    conflict_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """Dismiss a conflict without resolving (marks as dismissed)."""
    conflict = _conflicts.get(conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")

    reason = payload.get("reason", "Dismissed by user")
    conflict["status"] = "dismissed"
    conflict["resolution"] = {
        "status": "dismissed",
        "dismissed_at": _now(),
        "reason": reason,
    }
    _conflicts[conflict_id] = conflict

    return {"conflict_id": conflict_id, "status": "dismissed", "reason": reason}


@router.post("/scan")
async def scan_for_conflicts():
    """Force a full re-scan of all knowledge entries for conflicts.

    Returns newly detected conflicts that weren't previously cached.
    """
    entries = _get_knowledge_entries_from_service()
    if not entries:
        logger.info("No entries from service, using seed data")
        entries = _get_seed_entries()

    before_count = len(_conflicts)
    detected = _scan_for_conflicts(entries)
    new_count = len(_conflicts) - before_count

    return {
        "scanned": len(entries),
        "detected": len(detected),
        "new_conflicts": new_count,
        "total_conflicts": len(_conflicts),
        "source": "live_scan",
    }
