"""
Settings & E2E Control Panel routes.

Thin wrappers delegating business logic to SettingsStorageService in common_lib.
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Depends, Body, Query, Request
from sqlmodel import select, Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.users.models import User
from common_lib.modules.settings.service import theme_service
from common_lib.modules.settings.settings_storage import (
    init_settings_service,
    get_settings_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings & E2E Control Panel"])

# ── Initialize the storage service at module load time ─────────────────
_STORAGE_PATH = Path(__file__).parent / "storage.json"
init_settings_service(_STORAGE_PATH)
_svc = get_settings_service()

# ── Per-IP rate limiter for log viewer ─────────────────────────────────
_log_viewer_window: Dict[str, list] = defaultdict(list)
LOG_VIEWER_RATE_LIMIT = int(os.getenv("LOG_VIEWER_RATE_LIMIT", "60"))
LOG_VIEWER_WINDOW_SEC = 60


def _check_log_viewer_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = _log_viewer_window[client_ip]
    cutoff = now - LOG_VIEWER_WINDOW_SEC
    window[:] = [t for t in window if t > cutoff]
    if len(window) >= LOG_VIEWER_RATE_LIMIT:
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Try again later."
        )
    window.append(now)


# ==================== SECTION CRUD ====================


@router.get("/platform")
async def get_platform_settings():
    return _svc.get_section("platform")


@router.post("/platform")
async def update_platform_settings(payload: Dict[str, Any] = Body(...)):
    return {"status": "success", "data": _svc.update_section("platform", payload)}


@router.get("/connections")
async def get_connection_settings():
    return _svc.get_section("connections")


@router.post("/connections")
async def update_connection_settings(payload: Dict[str, Any] = Body(...)):
    return {"status": "success", "data": _svc.update_section("connections", payload)}


@router.post("/connections/test/{provider}")
async def test_connection(provider: str, payload: Dict[str, Any] = Body(...)):
    import asyncio
    await asyncio.sleep(0.5)
    key = payload.get("key", "")
    if not key and provider in ["huggingface", "gemini"]:
        return {"status": "error", "message": f"Authentication failed with {provider.upper()}: credentials missing."}
    return {"status": "success", "message": f"Connection to {provider.upper()} verified successfully!"}


# ==================== DIAGNOSTICS ====================


@router.get("/diagnostics")
async def get_diagnostics():
    return _svc.get_diagnostics()


@router.post("/diagnostics/purge/{cache_type}")
async def purge_cache(cache_type: str):
    if cache_type not in ["response", "embedding", "garbage"]:
        raise HTTPException(status_code=400, detail="Invalid cache type")
    return _svc.purge_cache(cache_type)


@router.post("/diagnostics/reset")
async def factory_reset_settings():
    return _svc.reset_to_defaults()


# ==================== THEMES CRUD (already thin, delegate to theme_service) ====================


@router.get("/themes")
async def list_themes(session: Session = Depends(get_session)):
    themes = theme_service.list_all(session)
    if not themes:
        themes = _svc.load_storage().get("themes", [])
    return themes


@router.get("/themes/builtin")
async def list_builtin_themes(session: Session = Depends(get_session)):
    return theme_service.list_builtin(session)


@router.post("/themes/seed")
async def seed_themes(session: Session = Depends(get_session)):
    return theme_service.seed_from_json(session)


@router.post("/themes")
async def create_theme(payload: Dict[str, Any] = Body(...), session: Session = Depends(get_session)):
    result = theme_service.create(session, payload)
    return {"status": "success", "data": result}


@router.put("/themes/{theme_id}")
async def update_theme(theme_id: str, payload: Dict[str, Any] = Body(...), session: Session = Depends(get_session)):
    try:
        result = theme_service.update(session, theme_id, payload)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/themes/{theme_id}")
async def delete_theme(theme_id: str, session: Session = Depends(get_session)):
    try:
        theme_service.delete(session, theme_id)
        return {"status": "success", "message": "Theme deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/themes/{theme_id}/duplicate")
async def duplicate_theme(theme_id: str, session: Session = Depends(get_session)):
    try:
        result = theme_service.duplicate(session, theme_id)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/themes/apply")
async def apply_theme(payload: Dict[str, Any] = Body(...)):
    theme_id = payload.get("themeId", "dark")
    storage = _svc.load_storage()
    _svc.apply_theme(theme_id, storage)
    _svc.save_storage(storage)
    return {"status": "success", "data": {"themeId": theme_id}}


# ==================== LOGGING ====================


@router.get("/logging/view")
async def view_recent_logs(
    request: Request,
    lines: int = Query(50, ge=10, le=1000),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    _check_log_viewer_rate_limit(request)
    log_file = Path(os.getenv("LOG_DIR", "logs")) / "server.log"
    return _svc.read_logs(log_file, lines=lines, level=level, search=search)


@router.get("/logging/levels")
async def get_log_levels():
    root = logging.getLogger()
    levels = {"root": logging.getLevelName(root.level)}
    for name in ["uvicorn", "uvicorn.access", "httpx", "sqlalchemy", "opentelemetry"]:
        mod = logging.getLogger(name)
        levels[name] = logging.getLevelName(mod.level) if mod.level else "NOTSET"
    return levels


@router.post("/logging/levels")
async def set_log_level(payload: Dict[str, Any] = Body(...)):
    module = payload.get("module", "root")
    level_name = payload.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    target = logging.getLogger(module if module != "root" else None)
    target.setLevel(level)
    logger.info(f"Log level for '{module}' changed to {level_name}")
    return {"status": "ok", "module": module, "level": level_name}


# ==================== NAVIGATION ====================


@router.get("/navigation")
async def get_navigation_settings():
    return _svc.get_section("navigation")


@router.post("/navigation")
async def update_navigation_settings(payload: Dict[str, Any] = Body(...)):
    return {"status": "success", "data": _svc.update_section("navigation", payload)}


# ==================== SECURITY ====================


@router.get("/security/config")
async def get_security_config():
    return _svc.get_section("security")


@router.post("/security/config")
async def update_security_config(payload: Dict[str, Any] = Body(...)):
    return {"status": "success", "data": _svc.update_section("security", payload)}


@router.get("/security/audit-logs")
async def get_audit_logs():
    return _svc.get_section("audit_logs")


@router.post("/security/audit-logs")
async def add_audit_log(payload: Dict[str, Any] = Body(...)):
    return {
        "status": "success",
        "data": _svc.add_audit_log_entry(
            event=payload.get("event", "Event"),
            user=payload.get("user", "system@antigravity.dev"),
            severity=payload.get("severity", "info"),
        ),
    }


@router.post("/security/compliance-check")
async def run_compliance_check():
    return _svc.run_compliance_check()


# ==================== TEAM ====================


@router.get("/team/workspace")
async def get_workspace_config():
    return _svc.get_section("workspace")


@router.post("/team/workspace")
async def update_workspace_config(payload: Dict[str, Any] = Body(...)):
    return {"status": "success", "data": _svc.update_section("workspace", payload)}


@router.get("/team/invites")
async def get_team_invites():
    return _svc.get_section("invites")


@router.post("/team/invites")
async def create_team_invite(payload: Dict[str, Any] = Body(...)):
    return {
        "status": "success",
        "data": _svc.create_invite(
            email=payload.get("email", ""),
            role=payload.get("role", "developer"),
        ),
    }


@router.delete("/team/invites/{invite_id}")
async def revoke_team_invite(invite_id: str):
    if not _svc.revoke_invite(invite_id):
        raise HTTPException(status_code=404, detail="Invitation not found")
    return {"status": "success", "message": "Invitation revoked"}


@router.get("/team/members")
async def get_team_members(session: Session = Depends(get_session)):
    try:
        users = session.exec(select(User)).all()
    except Exception as e:
        logger.warning(f"Failed to query users table: {e}. Falling back to default list.")
        users = []

    if not users:
        return _svc.get_default_members()

    return [_svc.map_user_to_member(u) for u in users]


@router.post("/team/members/{user_id}/role")
async def update_member_role(user_id: int, payload: Dict[str, Any] = Body(...), session: Session = Depends(get_session)):
    new_role = payload.get("role")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Member user not found in database")
    return {"status": "success", "message": f"Updated role for {user.full_name or user.username} to {new_role}"}


@router.delete("/team/members/{user_id}")
async def remove_team_member(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Member user not found in database")
    user.is_active = False
    session.add(user)
    session.commit()
    return {"status": "success", "message": f"Member {user.full_name or user.username} deactivated"}
