"""Character Studio feature flags (additive).

Registers the ``character_studio`` namespace flag with the platform-wide
feature-flag store. The flag defaults ON — the fail-open behaviour the rest
of the platform uses — but operators can disable it explicitly; every
handler in this module checks it and answers 404 while disabled.

Mounted by ``app/core/routers.py`` behind ``CHARACTER_IDENTITY_ENABLED`` at
the registry level; this module is the per-handler companion check.
"""

from common_lib.modules.common.feature_flags import register_flags

register_flags({"character_studio": True})

__all__ = []
