"""Connector provider registry.

Each connector has its own sub-package under providers/ with a provider.py
that exports a single Provider class. This module auto-discovers all providers
and maintains a registry mapping connector_id -> Provider class.
"""

import importlib
import logging
import pkgutil
from typing import Dict, Optional, Type

from .base import BaseConnectorProvider

logger = logging.getLogger(__name__)

_registry: Dict[str, Type[BaseConnectorProvider]] = {}


def discover_providers() -> None:
    """Scan the providers package and register all found providers."""
    package_path = __path__[0] if __path__ else __path__

    for _, module_name, is_pkg in pkgutil.iter_modules([package_path]):
        if not is_pkg or module_name.startswith("_"):
            continue
        try:
            provider_pkg = importlib.import_module(f"{__name__}.{module_name}.provider")
            provider_cls = getattr(provider_pkg, "Provider", None)
            if provider_cls is None:
                logger.debug(
                    "No Provider class found in %s.%s.provider", __name__, module_name
                )
                continue
            pid = getattr(provider_cls, "provider_id", None)
            if not pid:
                pid = module_name
            _registry[pid] = provider_cls
            logger.debug("Registered provider: %s -> %s", pid, provider_cls.__name__)
        except Exception as exc:
            logger.warning("Failed to load provider %s: %s", module_name, exc)


def get_provider(connector_id: str) -> Optional[Type[BaseConnectorProvider]]:
    """Look up a provider class by connector_id."""
    if connector_id not in _registry:
        discover_providers()
    return _registry.get(connector_id)


def get_registered_ids() -> set:
    return set(_registry.keys())


# Auto-discover on import
discover_providers()
