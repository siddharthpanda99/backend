from app.modules.audio.routes.router import router as main_router
from app.modules.audio.routes.takes_routes import router as takes_router
from app.modules.audio.routes.library_router import router as library_router
from app.modules.audio.routes.voice_profiles import router as voice_profiles_router
from app.modules.audio.routes.effect_presets import router as effect_presets_router

# Merge takes routes into the main audio router under the same prefix
# The takes_router has sub-path /generate, /takes/*, etc.
for route in takes_router.routes:
    main_router.routes.append(route)

# Merge library routes under /library prefix
# library_router defines routes like /overview, /scan, /assets, /collections etc.
# We need them prefixed with /library so the frontend calls to /api/v1/audio/library/* match.
from fastapi import APIRouter
_library_wrapper = APIRouter(prefix="/library")
for route in library_router.routes:
    _library_wrapper.routes.append(route)

for route in _library_wrapper.routes:
    main_router.routes.append(route)

# Merge voice profiles routes under /profiles prefix
_voice_profiles_wrapper = APIRouter(prefix="/profiles")
for route in voice_profiles_router.routes:
    _voice_profiles_wrapper.routes.append(route)
for route in _voice_profiles_wrapper.routes:
    main_router.routes.append(route)

# Merge effect presets routes under /effects prefix
_effect_presets_wrapper = APIRouter(prefix="/effects")
for route in effect_presets_router.routes:
    _effect_presets_wrapper.routes.append(route)
for route in _effect_presets_wrapper.routes:
    main_router.routes.append(route)

__all__ = ["router"]

# Re-export main_router as router
router = main_router
