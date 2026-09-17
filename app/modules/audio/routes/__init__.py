from app.modules.audio.routes.router import router as main_router
from app.modules.audio.routes.takes_routes import router as takes_router
from app.modules.audio.routes.library_router import router as library_router
from app.modules.audio.routes.voice_profiles import router as voice_profiles_router
from app.modules.audio.routes.effect_presets import router as effect_presets_router
from app.modules.audio.routes.nlp import router as nlp_router
from app.modules.audio.routes.dictation import router as dictation_router
from app.modules.audio.routes.translation import router as translation_router
from app.modules.audio.routes.dubbing import router as dubbing_router
from app.modules.audio.routes.batch import router as batch_router
from app.modules.audio.routes.openai_compat import router as openai_compat_router
from app.modules.audio.routes.tts_stream import router as tts_stream_router
from app.modules.audio.routes.system import router as system_router
from app.modules.audio.routes.voice_gallery import router as voice_gallery_router

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

# Merge NLP text-preprocessing routes under /nlp prefix (C013 — W1-L05)
_nlp_wrapper = APIRouter(prefix="/nlp")
for route in nlp_router.routes:
    _nlp_wrapper.routes.append(route)
for route in _nlp_wrapper.routes:
    main_router.routes.append(route)

# Merge dictation WS routes at root paths (C028 — W2-L07; paths are absolute
# /ws/... so no prefix wrapper — the platform stream path must not be nested)
for route in dictation_router.routes:
    main_router.routes.append(route)

# Merge translation routes under /translation prefix (C057 — W5-L04);
# /translate* stays unprefixed (the canonical verb paths)
_translation_wrapper = APIRouter(prefix="/translation")
for route in translation_router.routes:
    if not route.path.startswith("/translate"):
        _translation_wrapper.routes.append(route)
for route in _translation_wrapper.routes:
    main_router.routes.append(route)
for route in translation_router.routes:
    if route.path.startswith("/translate"):
        main_router.routes.append(route)

# Merge longform routes (C072 — W7-L04). Longform is flag-gated OFF by
# default and its import chain is still mid-build in a parallel session —
# a failure to import it must not take down the whole audio route surface
# (nlp/dictation/translation/dubbing). Resilient mount: on ImportError the
# feature is simply absent until its dependencies land.
try:
    from app.modules.audio.routes.longform import router as longform_router

    for route in longform_router.routes:
        main_router.routes.append(route)
except ImportError as _longform_import_error:  # pragma: no cover
    import logging as _logging

    _logging.getLogger(__name__).warning(
        "audio.longform routes not mounted (import failed: %s) — "
        "feature remains flag-gated OFF",
        _longform_import_error,
    )

# Merge dubbing routes under /dub prefix (C067/C068 — W6-L07);
# jobs CRUD stays at /dub/jobs, generate/abort/etc under /dub/*
_dubbing_wrapper = APIRouter(prefix="/dub")
for route in dubbing_router.routes:
    _dubbing_wrapper.routes.append(route)
for route in _dubbing_wrapper.routes:
    main_router.routes.append(route)

# Merge batch routes under /batch prefix (C078 — W8-L02)
for route in batch_router.routes:
    main_router.routes.append(route)

# Merge OpenAI compat routes at /openai prefix (C081 — W8-L05)
for route in openai_compat_router.routes:
    main_router.routes.append(route)

# Merge TTS streaming routes at /stream prefix (C082 — W8-L06)
for route in tts_stream_router.routes:
    main_router.routes.append(route)

# Merge system routes (convert/exports/tools/system/diagnose) at root (C091 — W8-L13)
# These are short verb paths: /voice/convert, /exports, /tools/*, /system/*
for route in system_router.routes:
    main_router.routes.append(route)

# Merge voice-gallery/bundle/describe/refinement routes at root (W4-L10 completion, 2026-09-15)
# Short verb paths: /voice/bundles/*, /gallery/*, /voice/describe, /refinement/run
# Services self-gate behind VOICE_GALLERY_ENABLED / OVSVOICE_ENABLED /
# VOICE_DESCRIBE_ENABLED / REFINEMENT_ENABLED (all default OFF).
for route in voice_gallery_router.routes:
    main_router.routes.append(route)

# Merge YuE music generation routes under /yue prefix
try:
    from app.modules.audio.routes.yue import router as yue_router

    for route in yue_router.routes:
        main_router.routes.append(route)
except ImportError as _yue_import_error:  # pragma: no cover
    import logging as _logging

    _logging.getLogger(__name__).warning(
        "audio.yue routes not mounted (import failed: %s)",
        _yue_import_error,
    )

# Merge audio workflows catalogue and execution routes under /workflows prefix
try:
    from app.modules.audio.routes.workflows import router as workflows_router

    for route in workflows_router.routes:
        main_router.routes.append(route)
except ImportError as _wf_import_error:  # pragma: no cover
    import logging as _logging

    _logging.getLogger(__name__).warning(
        "audio.workflows routes not mounted (import failed: %s)",
        _wf_import_error,
    )

__all__ = ["router"]

# Re-export main_router as router
router = main_router

