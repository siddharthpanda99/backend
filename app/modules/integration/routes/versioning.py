"""Shared API version resolution — constants, validation, and FastAPI dependency
for ``Accept-Version`` header / ``?version=`` query param negotiation.

Any API module can import the dependency::

    from app.modules.integration.routes.versioning import resolve_api_version

    @router.get("/my-endpoint")
    async def handler(api_version: str = Depends(resolve_api_version)):
        ...
"""

from __future__ import annotations

from typing import Optional
from fastapi import HTTPException, Query, Header


__all__ = [
    "VERSION_HELP",
    "VALID_VERSIONS",
    "validate_version",
    "resolve_api_version",
]


VERSION_HELP = (
    'API version: v1, v2, latest, or semver such as "1.0.0" (default: v1)'
)

# Compute valid versions from the spec generator's API_VERSION_MAP so the
# validation stays in sync automatically when new versions are added.
from common_lib.modules.integration.docs.api_docs import API_VERSION_MAP as _version_map  # type: ignore[import]
VALID_VERSIONS = frozenset(
    list(_version_map.keys()) + ["latest"] + list(_version_map.values())
)


def validate_version(version: str) -> None:
    """Validate a version string is recognised.

    Raises ``HTTPException(400)`` with a descriptive message listing the
    valid values if the version is not recognised.
    """
    if version not in VALID_VERSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unrecognised version: {version!r}. "
                f"Valid values: {', '.join(sorted(VALID_VERSIONS))}"
            ),
        )


async def resolve_api_version(
    version: str = Query("v1", description=VERSION_HELP),
    accept_version: Optional[str] = Header(
        None,
        alias="Accept-Version",
        description=VERSION_HELP,
    ),
) -> str:
    """Resolve the API version from query param or ``Accept-Version`` header.

    Evaluation priority
    -------------------
    1. ``Accept-Version`` header
    2. ``?version=`` query parameter
    3. ``"v1"`` (default)

    Validates the value via :func:`validate_version` and resolves the
    ``"latest"`` alias to ``"v1"``.

    Use as a FastAPI dependency::

        @router.get("/endpoint")
        async def handler(api_version: str = Depends(resolve_api_version)):
            ...
    """
    resolved = accept_version or version
    validate_version(resolved)
    if resolved == "latest":
        resolved = "v1"
    return resolved
