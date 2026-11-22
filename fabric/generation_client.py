"""Thin HTTP client for the Runtime Fabric generation endpoint.

Transport only: proxies :mod:`fabric`'s control plane
``POST /generate`` (and ``GET /health``) over loopback HTTP. All heavy lifting
happens inside the fabric; this module carries no engine logic and imports no
FastAPI symbols.

Feature flag ``RUNTIME_FABRIC_GENERATION_PROXY_ENABLED`` gates the proxy at the
transport boundary. Resolution order: explicit env override (``1/true/on`` →
on, ``0/false/off`` → off) wins; otherwise the environment default applies —
OFF in production, ON everywhere else.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class GenerationProxyError(Exception):
    """Error raised when the runtime fabric proxy fails.

    ``status_code`` is an HTTP status suitable for the transport layer
    (``502`` when the fabric is unreachable or its reply violates the
    contract, ``4xx``/``5xx`` echoed from the fabric error body when
    parseable). ``detail`` is a single-line, human-readable explanation.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _env_flag(name: str) -> Optional[bool]:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip().lower() not in ("", "0", "false", "no", "off")


def _is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "").strip().lower() == "production"


@dataclass(frozen=True)
class FeatureFlag:
    """Minimal typed feature flag with per-environment defaults."""

    name: str
    description: str
    default_production: bool
    default_staging: bool

    def is_enabled(self) -> bool:
        """Resolve the flag: explicit env override wins, else the environment default."""
        forced = _env_flag(self.name)
        if forced is not None:
            return forced
        if _is_production():
            return self.default_production
        return self.default_staging


RUNTIME_FABRIC_GENERATION_PROXY_ENABLED = FeatureFlag(
    name="RUNTIME_FABRIC_GENERATION_PROXY_ENABLED",
    description=(
        "Master switch for the backend -> runtime fabric generation proxy "
        "(POST /api/v1/ai/generate, GET /api/v1/ai/health)."
    ),
    default_production=False,
    default_staging=True,
)


def generation_proxy_enabled() -> bool:
    """True when the runtime fabric generation proxy is enabled."""
    return RUNTIME_FABRIC_GENERATION_PROXY_ENABLED.is_enabled()


try:  # Register in platform-wide store (best effort).
    from common_lib.modules.common.feature_flags import register_flags

    # Prune-metadata only. Actual behaviour is resolved by
    # ``RUNTIME_FABRIC_GENERATION_PROXY_ENABLED.is_enabled()`` above
    # (ENVIRONMENT-driven), so this registration does not switch the proxy.
    register_flags({"runtime_fabric.generation_proxy": True})
except Exception:
    logger.debug("runtime_fabric generation proxy: platform flag store unavailable", exc_info=True)


class RuntimeFabricGenerationClient:
    """HTTP client for the runtime fabric generation API."""

    def __init__(self) -> None:
        self.base_url = os.environ.get("RUNTIME_FABRIC_URL", "http://127.0.0.1:8001").rstrip("/")
        raw_timeout = os.environ.get("RUNTIME_FABRIC_PROXY_TIMEOUT")
        if raw_timeout:
            try:
                self.timeout: Optional[float] = float(raw_timeout)
            except (TypeError, ValueError):
                self.timeout = None
        else:
            self.timeout = None

    async def generate(self, payload: dict) -> dict:
        """POST ``{base}/generate`` with ``payload`` and return the parsed JSON body.

        Raises :class:`GenerationProxyError` on non-200 responses or network
        failures.
        """
        url = f"{self.base_url}/generate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise GenerationProxyError(
                502, f"runtime fabric unreachable at {self.base_url}: {exc}"
            ) from exc

        if response.status_code != 200:
            detail = self._error_detail(response)
            raise GenerationProxyError(response.status_code, detail)

        try:
            body = response.json()
        except ValueError as exc:
            raise GenerationProxyError(
                502, f"runtime fabric returned non-JSON body: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise GenerationProxyError(502, "runtime fabric returned a non-object JSON body")
        return body

    async def health(self) -> dict:
        """GET ``{base}/health`` (5s timeout). Never raises."""
        url = f"{self.base_url}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
            if response.status_code != 200:
                return {"reachable": False, "url": self.base_url}
            parsed = response.json()
            if not isinstance(parsed, dict):
                parsed = {"raw": parsed}
            return {"reachable": True, "url": self.base_url, **parsed}
        except Exception as exc:
            logger.debug("runtime fabric health check failed (%s): %s", url, exc)
            return {"reachable": False, "url": self.base_url}

    def artifact_payload(self, response: dict) -> dict:
        """Inline the first artifact referenced by ``response`` as base64.

        Checks, in order: ``response["image_path"]``, ``response["images"][0]``,
        ``response["audio_path"]``, ``response["video_path"]``. The first path
        that exists on the local filesystem is inlined under ``image`` /
        ``audio`` / ``video`` (``{mime, base64, filename, size_bytes}``) and the
        original path is reported under ``artifact_path``. A set path whose file
        is missing raises :class:`GenerationProxyError(502)`. Text/chat/embedding
        responses (no artifact path) are returned unchanged.
        """
        artifact = self._first_artifact(response)
        if artifact is None:
            return response
        kind, original_path = artifact

        path = Path(original_path)
        if not path.is_file():
            raise GenerationProxyError(
                502,
                f"fabric returned path but file missing on this host: {original_path}",
            )
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise GenerationProxyError(
                502,
                f"fabric artifact not readable on this host ({original_path}): {exc}",
            ) from exc

        mime, _ = mimetypes.guess_type(str(path))
        if not mime:
            mime = "application/octet-stream"

        artifact_blob = {
            "mime": mime,
            "base64": base64.b64encode(data).decode("ascii"),
            "filename": path.name,
            "size_bytes": len(data),
        }
        return {
            **response,
            kind: artifact_blob,
            "artifact_path": original_path,
        }

    @staticmethod
    def _first_artifact(response: dict) -> Optional[tuple[str, str]]:
        """Return the first ``(kind, path)`` artifact field set in ``response``."""

        def _as_path(value: Any) -> Optional[str]:
            return value.strip() if isinstance(value, str) and value.strip() else None

        candidate = _as_path(response.get("image_path"))
        if candidate:
            return "image", candidate
        images = response.get("images")
        if isinstance(images, list) and images:
            candidate = _as_path(images[0])
            if candidate:
                return "image", candidate
        candidate = _as_path(response.get("audio_path"))
        if candidate:
            return "audio", candidate
        candidate = _as_path(response.get("video_path"))
        if candidate:
            return "video", candidate
        return None

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        """Best-effort parse of the fabric error body; fall back to raw text."""
        try:
            body = response.json()
            if isinstance(body, dict):
                for key in ("detail", "error", "message"):
                    value = body.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
                return str(body)
            return str(body)
        except ValueError:
            text = response.text or ""
            return text.strip() or f"fabric returned HTTP {response.status_code}"


__all__ = [
    "GenerationProxyError",
    "RuntimeFabricGenerationClient",
    "RUNTIME_FABRIC_GENERATION_PROXY_ENABLED",
    "generation_proxy_enabled",
]
