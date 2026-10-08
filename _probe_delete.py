"""Probe: does the file_system.delete_file @node report success when the
service reports failure?

core_file_ops.delete_file discards the service's boolean and hardcodes
success=True; nodes.py's file_system_delete_file returns the real boolean.
Both publish the SAME node name, so which one an agent reaches depends on
registry scan order.
"""

import sys

sys.path.insert(
    0,
    "/home/siddharth/Documents/Dev/agentic-platform/Backend Monorepo/Python Libs/common_lib/src",
)

import common_lib.modules.file_system.nodes.core_file_ops as C
import common_lib.modules.file_system.nodes as _pkg
from common_lib.modules.file_system.nodes import core_file_ops


# Stub the service so delete_file reports failure (file does not exist).
class _Stub:
    def delete_file(self, file_id, permanent=False):
        return False  # the real service returns False when the row is absent


core_file_ops._get_service = lambda: _Stub()

print("core_file_ops.delete_file('does-not-exist') ->", C.delete_file("does-not-exist"))
print()
print(
    "nodes.py file_system_delete_file('does-not-exist') ->",
    N.file_system_delete_file("does-not-exist"),
)
print()
print("Both declare node name 'file_system.delete_file'.")
print("BUG: core_file_ops reports success=True for a file that does not exist;")
print("     nodes.py correctly reports success=False.")
