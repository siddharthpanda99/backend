"""Abstract base class for all connector providers."""

import base64
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

import httpx

from common_lib.modules.plugins.connectors.exceptions import ExecutionError
from common_lib.modules.plugins.connectors.models.connection import Connection

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")
logger = __import__("logging").getLogger(__name__)


def substitute_path_params(
    path: str,
    params: Dict[str, Any],
    form_data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Replace {param} placeholders from params or form_data."""
    remaining = dict(params)

    def _replacer(m: re.Match) -> str:
        key = m.group(1)
        val = remaining.pop(key, None) or form_data.get(key)
        if val is None:
            raise ExecutionError(f"Missing required path parameter: '{key}'")
        return str(val)

    resolved = _PATH_PARAM_RE.sub(_replacer, path)
    return resolved, remaining


class BaseConnectorProvider(ABC):
    """Abstract provider that all connector providers must implement.

    Each provider handles the complete execution lifecycle for its connector:
    endpoint lookup, base URL resolution, auth, body construction, and HTTP dispatch.
    """

    provider_id: str = ""

    def __init__(self, key_manager: Any, timeout: int = 30):
        self._key_manager = key_manager
        self._timeout = timeout

    @abstractmethod
    def execute(
        self,
        tool_id: str,
        params: Dict[str, Any],
        connection: Connection,
        form_data: Dict[str, Any],
    ) -> Any: ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_key(self, connection: Connection) -> str:
        return self._key_manager.resolve(connection)

    def _request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        query_params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    params=query_params,
                    json=json_body,
                    headers=headers,
                )
                response.raise_for_status()
                if response.content:
                    return response.json()
                return {"status": "ok"}
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text[:500]
            raise ExecutionError(
                f"HTTP {e.response.status_code} on {method} {url}: {detail}"
            ) from e
        except httpx.RequestError as e:
            raise ExecutionError(f"Request failed for {method} {url}: {e}") from e

    @staticmethod
    def _build_basic_auth(username: str, password: str) -> str:
        raw = base64.b64encode(f"{username}:{password}".encode()).decode()
        return f"Basic {raw}"


class RESTProvider(BaseConnectorProvider):
    """Convenience base for simple REST-based connectors.

    Subclasses declare:
        endpoints: dict mapping tool_id -> (http_method, url_path_template)
        base_url: str (or override get_base_url())

    Default auth uses Bearer token. Override build_auth_headers() for custom auth.
    """

    endpoints: Dict[str, Tuple[str, str]] = {}
    base_url: str = ""

    def get_base_url(self, form_data: Dict[str, Any]) -> str:
        return self.base_url

    def build_auth_headers(
        self,
        auth_scheme: str,
        key_value: str,
        form_data: Dict[str, Any],
    ) -> Dict[str, str]:
        if auth_scheme == "bearer_token":
            return {"Authorization": f"Bearer {key_value}"}
        if auth_scheme == "basic_auth":
            token = base64.b64encode(f"{key_value}:".encode()).decode()
            return {"Authorization": f"Basic {token}"}
        return {"Authorization": f"Bearer {key_value}"}

    def build_body(
        self,
        tool_id: str,
        method: str,
        params: Dict[str, Any],
        form_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if method in ("POST", "PUT", "PATCH"):
            return params if params else None
        return None

    def execute(
        self,
        tool_id: str,
        params: Dict[str, Any],
        connection: Connection,
        form_data: Dict[str, Any],
    ) -> Any:
        endpoint = self.endpoints.get(tool_id)
        if not endpoint:
            raise ExecutionError(
                f"No endpoint mapping for tool '{tool_id}' in provider '{self.provider_id}'"
            )

        method, path_template = endpoint
        base_url = self.get_base_url(form_data)
        if not base_url:
            raise ExecutionError(
                f"Could not resolve base URL for provider '{self.provider_id}'"
            )

        path, remaining = substitute_path_params(path_template, params, form_data)
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"

        key_value = self._resolve_key(connection)
        headers = self.build_auth_headers(connection.auth_scheme, key_value, form_data)
        headers.setdefault("Accept", "application/json")

        is_json_body = method in ("POST", "PUT", "PATCH")
        query_params = remaining if not is_json_body else None
        json_body = (
            self.build_body(tool_id, method, remaining, form_data)
            if is_json_body
            else None
        )

        return self._request(method, url, headers, query_params, json_body)


__all__ = [
    "BaseConnectorProvider",
    "RESTProvider",
    "substitute_path_params",
]
