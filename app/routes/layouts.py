"""Main backend — Layout Preset + Profile REST API.

Endpoints (under /api/v1/layouts):

  # Layout presets
  GET    /api/v1/layouts                  list (built-in + user)
  GET    /api/v1/layouts/{layout_id}      get one
  POST   /api/v1/layouts                  create custom
  PUT    /api/v1/layouts/{layout_id}      update custom
  DELETE /api/v1/layouts/{layout_id}      delete custom (built-ins protected)
  POST   /api/v1/layouts/{layout_id}/apply   return the preset for callers
  POST   /api/v1/layouts/render-cli          render preset as Rich CLI

  # Layout profiles (multi-page configs)
  GET    /api/v1/layouts/profiles/all      list (built-in + user)
  GET    /api/v1/layouts/profiles/{id}     get one
  POST   /api/v1/layouts/profiles          create custom
  PUT    /api/v1/layouts/profiles/{id}     update custom
  DELETE /api/v1/layouts/profiles/{id}     delete custom
  POST   /api/v1/layouts/profiles/{id}/apply   return the profile + first layout

Custom layouts/profiles are persisted to the data_storage DB
(tables: agentic_layout_presets, agentic_layout_profiles) so
they survive server restarts. Built-ins are always returned from
in-memory BUILTIN_PRESETS / BUILTIN_PROFILES.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from common_lib.modules.layout import (
    BUILTIN_PRESETS,
    BUILTIN_PROFILES,
    LayoutPreset,
    LayoutProfile,
    ProfilePage,
    ensure_layout_tables,
    serialise,
    deserialise,
)
from common_lib.modules.layout.preferences import (
    UserPreference,
    ensure_user_preferences_table,
    get_preference,
    set_preference,
)
from common_lib.modules.layout.storage import (
    LayoutPresetRecord,
    LayoutProfileRecord,
    LayoutVersionRecord,
)
from common_lib.modules.layout.versioning import (
    diff_dicts,
    diff_summary,
    diff_to_human,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/layouts", tags=["layouts"])


# ── Auth stub ──────────────────────────────────────────────────


def _current_user_id(request: Request) -> str:
    """Stub: read user id from headers, default to 'default-user'."""
    return request.headers.get("x-user-id", "default-user")


# ── Ensure DB tables exist on first call ───────────────────────

_tables_ready = False


def _ensure_tables_once() -> None:
    global _tables_ready
    if _tables_ready:
        return
    try:
        ensure_layout_tables()
        _tables_ready = True
    except Exception as e:
        logger.warning(f"layout tables not ready: {e}")


# ── DB helpers ──────────────────────────────────────────────────


def _db_session():
    """Return a context manager that yields a SQLModel Session.

    Falls back to None (in-memory mode) if the data_storage port
    is unavailable.
    """
    try:
        from common_lib.modules.integration.ports.data_storage_port import (
            get_data_storage_session,
        )
        from contextlib import contextmanager
        from sqlmodel import Session

        session_factory = get_data_storage_session()
        if session_factory is None:
            return None

        @contextmanager
        def _cm():
            s = session_factory()
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise
            finally:
                s.close()

        return _cm()
    except Exception as e:
        logger.debug(f"_db_session: failed to get data_storage: {e}")
        return None


def _load_user_layout(user_id: str, layout_id: str) -> LayoutPreset | None:
    cm = _db_session()
    if cm is None:
        return None
    with cm as s:
        rec = s.get(LayoutPresetRecord, layout_id)
        if rec is None or rec.owner_id != user_id:
            return None
        try:
            return deserialise(rec.preset_json, LayoutPreset)
        except Exception as e:
            logger.warning(f"_load_user_layout: {layout_id} deserialise failed: {e}")
            return None


def _save_user_layout(user_id: str, layout: LayoutPreset) -> bool:
    """Save (or update) a layout. If updating, snapshot the old
    version into LayoutVersionRecord for history/diff."""
    cm = _db_session()
    if cm is None:
        return False
    with cm as s:
        rec = s.get(LayoutPresetRecord, layout.id)
        now = datetime.utcnow()
        if rec is None:
            rec = LayoutPresetRecord(
                id=layout.id,
                name=layout.name,
                description=layout.description or "",
                category=layout.category or "general",
                icon=layout.icon,
                owner_id=user_id,
                preset_json=serialise(layout),
                created_at=now,
                updated_at=now,
            )
            s.add(rec)
        else:
            # Snapshot the OLD version into the history table
            # before we overwrite. This is what powers /history and
            # /diff/{a}/{b}.
            from sqlmodel import select as _select

            latest_v_stmt = (
                _select(LayoutVersionRecord)
                .where(LayoutVersionRecord.layout_id == layout.id)
                .order_by(LayoutVersionRecord.version_number.desc())
            )
            latest_v = s.exec(latest_v_stmt).first()
            next_version = (latest_v.version_number + 1) if latest_v else 1
            # Compute change summary
            try:
                before_dict = deserialise(rec.preset_json, LayoutPreset).model_dump()
                after_dict = layout.model_dump()
                changes = diff_dicts(before_dict, after_dict)
                summary = diff_summary(changes)
                change_summary = (
                    f"+{summary['added']} ~{summary['changed']} -{summary['removed']}"
                )
            except Exception:
                change_summary = "updated"
            version_rec = LayoutVersionRecord(
                layout_id=layout.id,
                version_number=next_version,
                preset_json=rec.preset_json,
                change_summary=change_summary,
                created_by=user_id,
                created_at=now,
            )
            s.add(version_rec)
            rec.name = layout.name
            rec.description = layout.description or ""
            rec.category = layout.category or "general"
            rec.icon = layout.icon
            rec.preset_json = serialise(layout)
            rec.updated_at = now
        return True


def _delete_user_layout(user_id: str, layout_id: str) -> bool:
    cm = _db_session()
    if cm is None:
        return False
    with cm as s:
        rec = s.get(LayoutPresetRecord, layout_id)
        if rec is None or rec.owner_id != user_id:
            return False
        s.delete(rec)
        return True


def _list_user_layouts(user_id: str) -> list[LayoutPreset]:
    cm = _db_session()
    if cm is None:
        return []
    with cm as s:
        from sqlmodel import select

        stmt = select(LayoutPresetRecord).where(LayoutPresetRecord.owner_id == user_id)
        records = s.exec(stmt).all()
    out: list[LayoutPreset] = []
    for r in records:
        try:
            out.append(deserialise(r.preset_json, LayoutPreset))
        except Exception:
            pass
    return out


def _load_user_profile(user_id: str, profile_id: str) -> LayoutProfile | None:
    cm = _db_session()
    if cm is None:
        return None
    with cm as s:
        rec = s.get(LayoutProfileRecord, profile_id)
        if rec is None or rec.owner_id != user_id:
            return None
        try:
            return deserialise(rec.profile_json, LayoutProfile)
        except Exception:
            return None


def _save_user_profile(user_id: str, profile: LayoutProfile) -> bool:
    cm = _db_session()
    if cm is None:
        return False
    with cm as s:
        rec = s.get(LayoutProfileRecord, profile.id)
        now = datetime.utcnow()
        if rec is None:
            rec = LayoutProfileRecord(
                id=profile.id,
                name=profile.name,
                description=profile.description or "",
                icon=profile.icon,
                owner_id=user_id,
                profile_json=serialise(profile),
                created_at=now,
                updated_at=now,
            )
            s.add(rec)
        else:
            rec.name = profile.name
            rec.description = profile.description or ""
            rec.icon = profile.icon
            rec.profile_json = serialise(profile)
            rec.updated_at = now
        return True


def _delete_user_profile(user_id: str, profile_id: str) -> bool:
    cm = _db_session()
    if cm is None:
        return False
    with cm as s:
        rec = s.get(LayoutProfileRecord, profile_id)
        if rec is None or rec.owner_id != user_id:
            return False
        s.delete(rec)
        return True


def _list_user_profiles(user_id: str) -> list[LayoutProfile]:
    cm = _db_session()
    if cm is None:
        return []
    with cm as s:
        from sqlmodel import select

        stmt = select(LayoutProfileRecord).where(
            LayoutProfileRecord.owner_id == user_id
        )
        records = s.exec(stmt).all()
    out: list[LayoutProfile] = []
    for r in records:
        try:
            out.append(deserialise(r.profile_json, LayoutProfile))
        except Exception:
            pass
    return out


def _is_builtin_layout(layout_id: str) -> bool:
    return any(p.id == layout_id for p in BUILTIN_PRESETS)


def _is_builtin_profile(profile_id: str) -> bool:
    return any(p.id == profile_id for p in BUILTIN_PROFILES)


# ── Request/response models ────────────────────────────────────

from pydantic import BaseModel, Field


class CreateLayoutRequest(BaseModel):
    id: str | None = Field(None, description="Optional id; auto-generated if missing")
    name: str
    description: str = ""
    category: str = "general"
    icon: str | None = None
    tabs: list[dict[str, Any]] = Field(default_factory=list)
    dock_tree: dict[str, Any] | None = None
    theme: dict[str, Any] = Field(default_factory=dict)


class UpdateLayoutRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    tabs: list[dict[str, Any]] | None = None
    dock_tree: dict[str, Any] | None = None
    theme: dict[str, Any] | None = None


class CreateProfileRequest(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    icon: str | None = None
    pages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {id, label, icon?, layout_id} dicts",
    )
    active_page_id: str | None = None


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    pages: list[dict[str, Any]] | None = None
    active_page_id: str | None = None


class RenderCliRequest(BaseModel):
    layout_id: str
    width: int | None = None
    height: int | None = None


# ═══════════════════════════════════════════════════════════════════
#  Layout Preset Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.on_event("startup")
async def _on_startup():
    _ensure_tables_once()


@router.get("")
async def list_layouts(
    request: Request,
    category: str | None = None,
) -> dict[str, Any]:
    user_id = _current_user_id(request)
    _ensure_tables_once()
    presets = list(BUILTIN_PRESETS) + _list_user_layouts(user_id)
    if category:
        presets = [p for p in presets if p.category == category]
    return {
        "presets": [p.model_dump() for p in presets],
        "categories": sorted(
            {p.category for p in (list(BUILTIN_PRESETS) + _list_user_layouts(user_id))}
        ),
    }


@router.get("/{layout_id}")
async def get_layout(request: Request, layout_id: str) -> dict[str, Any]:
    for p in BUILTIN_PRESETS:
        if p.id == layout_id:
            return p.model_dump()
    user_id = _current_user_id(request)
    p = _load_user_layout(user_id, layout_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"layout '{layout_id}' not found")
    return p.model_dump()


@router.post("")
async def create_layout(request: Request, body: CreateLayoutRequest) -> dict[str, Any]:
    _ensure_tables_once()
    user_id = _current_user_id(request)
    new_id = body.id or f"layout-{uuid.uuid4().hex[:8]}"
    if _is_builtin_layout(new_id):
        raise HTTPException(
            status_code=409, detail=f"'{new_id}' is a built-in layout id"
        )
    # Check uniqueness in user's collection
    if _load_user_layout(user_id, new_id) is not None:
        raise HTTPException(status_code=409, detail=f"layout '{new_id}' already exists")
    preset = LayoutPreset(
        id=new_id,
        name=body.name,
        description=body.description,
        category=body.category,
        icon=body.icon,
        tabs=body.tabs,
        dock_tree=body.dock_tree,
        theme=body.theme,
        is_built_in=False,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        author=user_id,
    )
    if not _save_user_layout(user_id, preset):
        # Fall back to in-memory if DB is unavailable
        logger.warning("create_layout: DB unavailable, falling back to in-memory only")
    return preset.model_dump()


@router.put("/{layout_id}")
async def update_layout(
    request: Request, layout_id: str, body: UpdateLayoutRequest
) -> dict[str, Any]:
    if _is_builtin_layout(layout_id):
        raise HTTPException(
            status_code=403,
            detail=f"'{layout_id}' is a built-in; clone it first",
        )
    user_id = _current_user_id(request)
    existing = _load_user_layout(user_id, layout_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"layout '{layout_id}' not found")
    data = existing.model_dump()
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            data[k] = v
    data["updated_at"] = datetime.utcnow().isoformat()
    new_preset = LayoutPreset(**data)
    _save_user_layout(user_id, new_preset)
    return new_preset.model_dump()


@router.delete("/{layout_id}")
async def delete_layout(request: Request, layout_id: str) -> dict[str, Any]:
    if _is_builtin_layout(layout_id):
        raise HTTPException(
            status_code=403, detail=f"'{layout_id}' is built-in; cannot delete"
        )
    user_id = _current_user_id(request)
    if not _delete_user_layout(user_id, layout_id):
        raise HTTPException(status_code=404, detail=f"layout '{layout_id}' not found")
    return {"ok": True, "layout_id": layout_id}


@router.post("/{layout_id}/apply")
async def apply_layout(request: Request, layout_id: str) -> dict[str, Any]:
    return await get_layout(request, layout_id)


@router.post("/render-cli")
async def render_cli(request: Request, body: RenderCliRequest) -> dict[str, Any]:
    from common_lib.modules.layout.cli_renderer import render_layout_preset

    user_id = _current_user_id(request)
    preset: LayoutPreset | None = None
    for p in BUILTIN_PRESETS:
        if p.id == body.layout_id:
            preset = p
            break
    if preset is None:
        preset = _load_user_layout(user_id, body.layout_id)
    if preset is None:
        raise HTTPException(
            status_code=404, detail=f"layout '{body.layout_id}' not found"
        )
    rendered = render_layout_preset(preset, width=body.width, height=body.height)
    return {
        "layout_id": preset.id,
        "name": preset.name,
        "rendered": rendered,
    }


# ═══════════════════════════════════════════════════════════════════
#  Layout Profile Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/profiles/all")
async def list_profiles(request: Request) -> dict[str, Any]:
    user_id = _current_user_id(request)
    _ensure_tables_once()
    profiles = list(BUILTIN_PROFILES) + _list_user_profiles(user_id)
    return {"profiles": [p.model_dump() for p in profiles]}


@router.get("/profiles/{profile_id}")
async def get_profile(request: Request, profile_id: str) -> dict[str, Any]:
    for p in BUILTIN_PROFILES:
        if p.id == profile_id:
            return p.model_dump()
    user_id = _current_user_id(request)
    p = _load_user_profile(user_id, profile_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"profile '{profile_id}' not found")
    return p.model_dump()


@router.post("/profiles")
async def create_profile(
    request: Request, body: CreateProfileRequest
) -> dict[str, Any]:
    _ensure_tables_once()
    user_id = _current_user_id(request)
    new_id = body.id or f"profile-{uuid.uuid4().hex[:8]}"
    if _is_builtin_profile(new_id):
        raise HTTPException(
            status_code=409, detail=f"'{new_id}' is a built-in profile id"
        )
    if _load_user_profile(user_id, new_id) is not None:
        raise HTTPException(
            status_code=409, detail=f"profile '{new_id}' already exists"
        )
    pages = [ProfilePage(**p) for p in body.pages]
    profile = LayoutProfile(
        id=new_id,
        name=body.name,
        description=body.description,
        icon=body.icon,
        pages=pages,
        active_page_id=body.active_page_id or (pages[0].id if pages else None),
        is_built_in=False,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        author=user_id,
    )
    _save_user_profile(user_id, profile)
    return profile.model_dump()


@router.put("/profiles/{profile_id}")
async def update_profile(
    request: Request, profile_id: str, body: UpdateProfileRequest
) -> dict[str, Any]:
    if _is_builtin_profile(profile_id):
        raise HTTPException(
            status_code=403, detail=f"'{profile_id}' is built-in; clone it first"
        )
    user_id = _current_user_id(request)
    existing = _load_user_profile(user_id, profile_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"profile '{profile_id}' not found")
    data = existing.model_dump()
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            data[k] = v
    data["updated_at"] = datetime.utcnow().isoformat()
    new_profile = LayoutProfile(**data)
    _save_user_profile(user_id, new_profile)
    return new_profile.model_dump()


@router.delete("/profiles/{profile_id}")
async def delete_profile(request: Request, profile_id: str) -> dict[str, Any]:
    if _is_builtin_profile(profile_id):
        raise HTTPException(
            status_code=403, detail=f"'{profile_id}' is built-in; cannot delete"
        )
    user_id = _current_user_id(request)
    if not _delete_user_profile(user_id, profile_id):
        raise HTTPException(status_code=404, detail=f"profile '{profile_id}' not found")
    return {"ok": True, "profile_id": profile_id}


@router.post("/profiles/{profile_id}/apply")
async def apply_profile(request: Request, profile_id: str) -> dict[str, Any]:
    """Apply a profile. Returns the profile + the active layout.

    The active layout is determined by ``active_page_id``; if
    unset, the first page is used.
    """
    profile_data = await get_profile(request, profile_id)
    profile = LayoutProfile(**profile_data)
    # Determine active page
    active_page = None
    if profile.active_page_id:
        for p in profile.pages:
            if p.id == profile.active_page_id:
                active_page = p
                break
    if active_page is None and profile.pages:
        active_page = profile.pages[0]
    if active_page is None:
        raise HTTPException(
            status_code=409,
            detail=f"profile '{profile_id}' has no pages",
        )
    # Look up the active layout
    layout_data = await get_layout(request, active_page.layout_id)
    return {
        "profile": profile_data,
        "active_page": active_page.model_dump(),
        "layout": layout_data,
    }


# ═══════════════════════════════════════════════════════════════════
#  Per-user default profile
# ═══════════════════════════════════════════════════════════════════


class SetDefaultProfileRequest(BaseModel):
    profile_id: str = Field(..., description="Profile id (built-in or user)")


@router.on_event("startup")
async def _on_startup_prefs():
    try:
        ensure_user_preferences_table()
    except Exception as e:
        logger.warning(f"Could not ensure user_preferences table: {e}")


@router.get("/me/default-profile")
async def get_my_default_profile(request: Request) -> dict[str, Any]:
    """Return the current user's default profile id (or empty)."""
    user_id = _current_user_id(request)
    profile_id = get_preference(user_id, "default_profile_id", "")
    return {
        "user_id": user_id,
        "default_profile_id": profile_id or "",
    }


@router.put("/me/default-profile")
async def set_my_default_profile(
    request: Request, body: SetDefaultProfileRequest
) -> dict[str, Any]:
    """Set the current user's default profile.

    Once set, ChatView will automatically pick this profile up
    on every mount. Users can change it at any time.
    """
    user_id = _current_user_id(request)
    # Verify the profile exists
    profile_found = False
    for p in BUILTIN_PROFILES:
        if p.id == body.profile_id:
            profile_found = True
            break
    if not profile_found:
        profile_found = _load_user_profile(user_id, body.profile_id) is not None
    if not profile_found:
        raise HTTPException(
            status_code=404,
            detail=f"profile '{body.profile_id}' not found",
        )
    set_preference(user_id, "default_profile_id", body.profile_id)
    return {
        "user_id": user_id,
        "default_profile_id": body.profile_id,
    }


@router.delete("/me/default-profile")
async def clear_my_default_profile(request: Request) -> dict[str, Any]:
    """Clear the current user's default profile."""
    user_id = _current_user_id(request)
    set_preference(user_id, "default_profile_id", "")
    return {"user_id": user_id, "default_profile_id": ""}


@router.get("/{layout_id}/history")
async def get_layout_history(request: Request, layout_id: str) -> dict[str, Any]:
    """Return the version history of a layout.

    Newest first. Each entry is a snapshot of the layout at that
    point in time plus a short change summary.
    """
    # Built-ins don't have history
    if _is_builtin_layout(layout_id):
        return {
            "layout_id": layout_id,
            "history": [],
            "note": "built-in layouts are versioned with the platform",
        }
    cm = _db_session()
    if cm is None:
        return {"layout_id": layout_id, "history": []}
    try:
        with cm as s:
            from sqlmodel import select as _select

            stmt = (
                _select(LayoutVersionRecord)
                .where(LayoutVersionRecord.layout_id == layout_id)
                .order_by(LayoutVersionRecord.version_number.desc())
            )
            records = s.exec(stmt).all()
        return {
            "layout_id": layout_id,
            "history": [
                {
                    "version": r.version_number,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "created_by": r.created_by,
                    "change_summary": r.change_summary,
                }
                for r in records
            ],
        }
    except Exception as e:
        return {"layout_id": layout_id, "history": [], "error": str(e)}


@router.get("/{layout_id}/diff")
async def diff_layout_versions(
    request: Request,
    layout_id: str,
    from_version: int = Query(..., description="Older version number"),
    to_version: int = Query(..., description="Newer version number"),
    format: str = Query("json", description="json | human"),
) -> dict[str, Any]:
    """Diff between two versions of a layout.

    Returns either structured JSON changes (default) or a
    human-readable text format.
    """
    cm = _db_session()
    if cm is None:
        raise HTTPException(status_code=503, detail="version history requires DB")
    with cm as s:
        v_from = s.get(LayoutVersionRecord, (from_version, layout_id))
        v_to = s.get(LayoutVersionRecord, (to_version, layout_id))
        if v_from is None or v_to is None:
            raise HTTPException(
                status_code=404,
                detail=f"versions {from_version}/{to_version} not found",
            )
        before = deserialise(v_from.preset_json, LayoutPreset)
        after = deserialise(v_to.preset_json, LayoutPreset)
    changes = diff_dicts(before.model_dump(), after.model_dump())
    summary = diff_summary(changes)
    if format == "human":
        return {
            "layout_id": layout_id,
            "from_version": from_version,
            "to_version": to_version,
            "summary": summary,
            "human": diff_to_human(changes),
        }
    return {
        "layout_id": layout_id,
        "from_version": from_version,
        "to_version": to_version,
        "summary": summary,
        "changes": [
            {
                "path": c.path,
                "before": c.before,
                "after": c.after,
                "op": c.op,
            }
            for c in changes
        ],
    }


@router.post("/{layout_id}/rollback")
async def rollback_layout(
    request: Request, layout_id: str, body: dict
) -> dict[str, Any]:
    """Roll back to a specific version.

    Reads the snapshot at ``body.version``, re-applies it, and
    creates a new version entry recording the rollback.
    """
    version = body.get("version")
    if version is None:
        raise HTTPException(status_code=400, detail="'version' is required in body")
    if _is_builtin_layout(layout_id):
        raise HTTPException(status_code=403, detail="built-in layouts are read-only")
    user_id = _current_user_id(request)
    cm = _db_session()
    if cm is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    with cm as s:
        v = s.get(LayoutVersionRecord, (version, layout_id))
        if v is None:
            raise HTTPException(status_code=404, detail=f"version {version} not found")
        snapshot = deserialise(v.preset_json, LayoutPreset)
    # Apply via the normal save path (which also creates a new version)
    if not _save_user_layout(user_id, snapshot):
        raise HTTPException(status_code=500, detail="save failed")
    return {
        "ok": True,
        "layout_id": layout_id,
        "rolled_back_to": version,
    }


__all__ = ["router"]
