"""Skill lifecycle API routes (NEX-P5-001).

Thin routes (G1): all logic in common_lib.modules.skills.service.
Mutations are gated behind ``skills.lifecycle.enabled`` (default OFF, G9) —
flag-off answers 404, identical to "route does not exist". Reads
(list/detail/versions/evaluations/search/select) and the flags endpoint are
ungated by design (read-only; empty DB ⇒ empty results).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/skills", tags=["Skills"])


# ── Request/Response Models (wire shapes; domain models live in common_lib) ─


class SkillVersionCreateBody(BaseModel):
    version: str
    display_name: str = ""
    description: str = ""
    owner: str = ""
    input_schema_ref: str = ""
    output_schema_ref: str = ""
    allowed_capabilities: list[str] = []
    allowed_scopes: list[str] = []
    risk_class: str = "medium"
    time_budget_ms: int = 300000
    max_steps: int = 10
    token_budget: dict[str, Any] = {}
    eval_dataset_ref: str = ""
    min_pass_rate: float = 0.0
    compatibility: dict[str, Any] = {}
    change_summary: str = ""


class SkillEvaluateBody(BaseModel):
    dataset_ref: str = ""
    pass_rate: float
    metrics: dict[str, Any] = {}


class SkillPublishBody(BaseModel):
    version: str
    published_by: str = ""


class SkillApproveBody(BaseModel):
    version: str
    approver: str
    approved: bool = True


class SkillTransitionBody(BaseModel):
    to: str
    actor: str = ""


class SkillSelectionCandidateBody(BaseModel):
    skill_id: str
    version: str
    intent_fit: float | None = None
    policy_pass: bool = True
    quality: float = 0.0
    cost: float = 0.0
    usage_count: float | None = None
    frequency: float | None = None


class SkillSelectionBody(BaseModel):
    candidates: list[SkillSelectionCandidateBody]
    max_cost: float = 0.0
    top_k: int = 5


_LIFECYCLE_FLAG = "skills.lifecycle.enabled"


def _require_lifecycle_feature() -> None:
    """Refuse mutation routes with 404 while the flag is OFF.

    404 (not 403) because the route does not exist from the client's point
    of view until the feature is enabled. Mirrors the capabilities batch
    pattern.
    """
    try:
        from common_lib.modules.skills.flags import is_enabled as _skills_enabled
    except ImportError:
        raise HTTPException(status_code=404, detail="Skill lifecycle unavailable")
    if _skills_enabled(_LIFECYCLE_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "Skill lifecycle writes are gated behind the feature flag "
            f"'{_LIFECYCLE_FLAG}', which is currently OFF. Enable "
            "SKILLS_LIFECYCLE_ENABLED=true and restart."
        ),
    )


def _service():
    from common_lib.modules.skills.service import get_skill_service

    return get_skill_service()


# ── Reads (ungated) ───────────────────────────────────────────────────────


@router.get("/lifecycle/flags")
async def lifecycle_flags():
    """Skills feature-flag state. Ungated by design (diagnostics)."""
    try:
        from common_lib.modules.skills.flags import describe_flags

        return {"flags": describe_flags()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_skills(status: str | None = None, owner: str = ""):
    """List skill head rows, optionally filtered by lifecycle status/owner."""
    try:
        from common_lib.modules.skills.models import SkillStatus
        from common_lib.modules.skills.service import skill_to_dict

        wanted = SkillStatus(status) if status else None
        return {"skills": [skill_to_dict(s) for s in _service().list_skills(status=wanted, owner=owner or "")]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_skills(query: str = "", status: str | None = None, owner: str = "", limit: int = 20):
    """Substring search over skill manifests (read-only)."""
    try:
        from common_lib.modules.skills.models import SkillStatus
        from common_lib.modules.skills.service import skill_to_dict

        wanted = SkillStatus(status) if status else None
        rows = _service().search(query, owner=owner or "", status=wanted, limit=limit)
        return {"skills": [skill_to_dict(r) for r in rows]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/select")
async def select_skills(body: SkillSelectionBody):
    """Rank PUBLISHED versions by intent fit + policy + quality + cost.

    Read-only. Frequency-only candidate sets are refused (400) — selection
    is never frequency-alone.
    """
    try:
        from common_lib.modules.skills.models import SelectionCandidate, SelectionRequest

        request = SelectionRequest(
            candidates=[SelectionCandidate(**c.model_dump()) for c in body.candidates],
            max_cost=body.max_cost,
            top_k=body.top_k,
        )
        return {"selection": [r.model_dump() for r in _service().select(request)]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """Get one skill head row with lifecycle status."""
    try:
        from common_lib.modules.skills.service import skill_to_dict

        skill = _service().get(skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return skill_to_dict(skill)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}/versions")
async def list_skill_versions(skill_id: str):
    """List immutable versions (version history), newest first."""
    try:
        from common_lib.modules.skills.service import version_to_dict

        rows = _service().list_versions(skill_id)
        if not rows and _service().get(skill_id) is None:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return {"versions": [version_to_dict(r) for r in rows]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}/versions/{version}")
async def get_skill_version(skill_id: str, version: str):
    """Get one immutable version manifest."""
    try:
        from common_lib.modules.skills.service import version_to_dict

        row = _service().get_version(skill_id, version)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Skill version not found: {skill_id}@{version}")
        return version_to_dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}/evaluations")
async def list_skill_evaluations(skill_id: str, version: str = ""):
    """List eval evidence bound to a skill (optionally one version)."""
    try:
        from common_lib.modules.skills.service import eval_run_to_dict

        if _service().get(skill_id) is None:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return {"evaluations": [eval_run_to_dict(r) for r in _service().list_evaluations(skill_id, version)]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Mutations (flag-gated) ────────────────────────────────────────────────


@router.post("/{skill_id}/versions")
async def create_skill_version(skill_id: str, body: SkillVersionCreateBody):
    """Create one immutable version (flag-gated). Auto-registers the head."""
    _require_lifecycle_feature()
    try:
        from common_lib.modules.skills.models import SkillRiskClass, SkillVersionCreate
        from common_lib.modules.skills.service import version_to_dict

        payload = SkillVersionCreate(**{**body.model_dump(), "risk_class": SkillRiskClass(body.risk_class)})
        row = _service().create_version(skill_id, payload, created_by="api")
        return version_to_dict(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/versions/{version}/evaluate")
async def evaluate_skill_version(skill_id: str, version: str, body: SkillEvaluateBody):
    """Append eval evidence bound to one immutable version (flag-gated)."""
    _require_lifecycle_feature()
    try:
        from common_lib.modules.skills.models import SkillEvaluate
        from common_lib.modules.skills.service import eval_run_to_dict

        run = _service().record_evaluation(
            skill_id, version, SkillEvaluate(**body.model_dump()), created_by="api"
        )
        return eval_run_to_dict(run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/approve")
async def approve_skill_version(skill_id: str, body: SkillApproveBody):
    """Record an approval decision for one version (flag-gated)."""
    _require_lifecycle_feature()
    try:
        from common_lib.modules.skills.service import version_to_dict

        row = _service().approve_version(skill_id, body.version, body.approver, body.approved)
        return version_to_dict(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/transition")
async def transition_skill(skill_id: str, body: SkillTransitionBody):
    """Move the head along a legal lifecycle edge (flag-gated)."""
    _require_lifecycle_feature()
    try:
        from common_lib.modules.skills.models import SkillStatus
        from common_lib.modules.skills.service import skill_to_dict

        skill = _service().transition(skill_id, SkillStatus(body.to), body.actor or "api")
        return skill_to_dict(skill)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/publish")
async def publish_skill(skill_id: str, body: SkillPublishBody):
    """Publish one version: reviewed → published, eval + approval gated (flag-gated)."""
    _require_lifecycle_feature()
    try:
        from common_lib.modules.skills.service import skill_to_dict

        skill = _service().publish(skill_id, body.version, body.published_by or "api")
        return skill_to_dict(skill)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/deprecate")
async def deprecate_skill(skill_id: str):
    """Deprecate a published skill (flag-gated)."""
    _require_lifecycle_feature()
    try:
        from common_lib.modules.skills.service import skill_to_dict

        return skill_to_dict(_service().deprecate(skill_id, actor="api"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
