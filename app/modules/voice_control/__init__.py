"""app.modules.voice_control — Deprecated router shim (Phase 12 — PR 2).

.. deprecated::
    Mounted at ``/api/v1/voice-control/``. Use
    ``/api/v1/platform-controls/`` instead. See
    ``common_lib/modules/platform_controls/docs/11_migration_from_voice_control.md``
    §6 for the router-level shim contract and §11 for the 6-month BC
    timeline (Sunset: 2027-02-28).

This package contains no business logic. Every public route delegates
to the canonical :mod:`app.modules.platform_controls.routes` router.
The package is part of the BC window for the
``voice_control`` → ``platform_controls`` rename.
"""
