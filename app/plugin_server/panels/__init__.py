"""Plugin Server — Harness Panel + Universal Plugin Lifecycle (re-exports).

The actual classes live in the SDK at
``common_lib.modules.plugin_sdk.panels``. This file re-exports
them so existing code (and IDE autocomplete) can find them via
``app.plugin_server.panels``.

3rd-party panel authors should import from the SDK::

    from common_lib.modules.plugin_sdk import (
        BasePanel,
        PluginLifecycle,
        PluginPhase,
        PluginCapability,
        LifecyclePhase,
    )
"""

from common_lib.modules.plugin_sdk.panels import BasePanel
from common_lib.modules.plugin_sdk.panels.lifecycle import (
    LifecyclePhase,
    PluginPhase,
    PluginCapability,
    PluginLifecycle,
)

__all__ = [
    "BasePanel",
    "LifecyclePhase",
    "PluginPhase",
    "PluginCapability",
    "PluginLifecycle",
]
