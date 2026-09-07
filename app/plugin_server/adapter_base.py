"""Plugin Server — Adapter base class (re-export from SDK).

The actual BaseAdapter class lives in the SDK at
``common_lib.modules.plugin_sdk.runtime.adapter_base``. This file
exists for backward compatibility with code that imports from
``app.plugin_server.adapter_base``.

3rd-party authors should import from the SDK::

    from common_lib.modules.plugin_sdk import BaseAdapter
    # or
    from common_lib.modules.plugin_sdk.runtime import BaseAdapter
"""

from common_lib.modules.plugin_sdk.runtime.adapter_base import BaseAdapter

__all__ = ["BaseAdapter"]
