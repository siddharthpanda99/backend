"""Fixture for test_instance_registry: proves laziness across a real import.

Declares an instance source at class-definition time and records whether the
factory ran during import. Kept in its own file so the measurement spans a real
module import rather than an in-test definition.
"""

CONSTRUCTED_AT_IMPORT: list = []


def _factory():
    CONSTRUCTED_AT_IMPORT.append("constructed")
    return Lazy(session="LAZY")


class Lazy:
    __node_instance_source__ = "_eager_probe:_factory"

    def __init__(self, session):
        self.session = session

    def go(self, name: str) -> dict:
        return {"ok": name}
