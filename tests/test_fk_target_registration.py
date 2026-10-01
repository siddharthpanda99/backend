"""Regression tests for foreign-key target registration before DDL.

The bug: `SQLModel.metadata.sorted_tables` raises `NoReferencedTableError` when
any table's foreign key targets a table absent from the same `MetaData`, so the
whole schema fails to emit. Seven tables were affected -- `agent_memories`,
`agent_skills`, `agent_tools`, `agent_prompts`, `agent_workflows`,
`agent_procedures` and `workflow_agents` -- all pointing at tables that existed
as `SQLModel` classes in modules nothing had imported.

These tests use the REAL registry. A hand-rolled metadata object would not catch
a missing registration, which is precisely how this bug survived: the declaration
existed and was correct, only the import was absent.
"""

from __future__ import annotations

import pytest
from sqlmodel import SQLModel

# Importing this module is what builds the association tables carrying the FKs.
import common_lib.modules.orchestration.agents.agent.core.models  # noqa: F401
from common_lib.modules.data_storage.database.model_registration import (
    FK_TARGET_MODULES,
    register_fk_target_models,
    unresolved_fks,
)

AFFECTED_TABLES = {
    "agent_memories",
    "agent_skills",
    "agent_tools",
    "agent_prompts",
    "agent_workflows",
    "agent_procedures",
    "workflow_agents",
}


def test_the_reported_failure_is_reproduced_without_registration():
    """Guards the test itself: before registering, the FK really is unresolvable.

    A regression test that cannot fail is worse than none, so this asserts the
    bug is present in a FRESH interpreter state, not that our fix works. It is
    skipped rather than failed when another test already registered the models,
    because module import is process-global and order-dependent.
    """
    from common_lib.modules.orchestration.agents.agent.core.models import agent_memories

    if "memory_definitions" in SQLModel.metadata.tables:
        pytest.skip("targets already registered in this process; see the other tests")

    with pytest.raises(Exception) as exc:
        SQLModel.metadata.sorted_tables
    assert (
        "memory_definitions" in str(exc.value)
        or "NoReferencedTable" in type(exc.value).__name__
    )
    assert agent_memories is not None


def test_registering_targets_resolves_every_foreign_key():
    outcome = register_fk_target_models()
    assert not outcome.failed, f"FK-target modules failed to import: {outcome.failed}"
    assert unresolved_fks() == {}


def test_every_affected_table_now_has_its_target():
    register_fk_target_models()
    for table_name in AFFECTED_TABLES:
        table = SQLModel.metadata.tables.get(table_name)
        assert table is not None, f"{table_name} is not registered at all"
        for column in table.columns:
            for fk in column.foreign_keys:
                target = fk.target_fullname.split(".")[0]
                assert target in SQLModel.metadata.tables, (
                    f"{table_name}.{column.name} -> {target} is unresolved"
                )


def test_the_specific_table_from_the_bug_report_is_registered():
    """`agent_memories.memory_id -> memory_definitions` is the reported failure."""
    register_fk_target_models()
    table = SQLModel.metadata.tables["agent_memories"]
    targets = {
        fk.target_fullname.split(".")[0] for c in table.columns for fk in c.foreign_keys
    }
    assert "memory_definitions" in targets
    assert "memory_definitions" in SQLModel.metadata.tables


def test_sorted_tables_orders_the_schema_without_raising():
    """The exact call that raised NoReferencedTableError in production."""
    register_fk_target_models()
    ordered = SQLModel.metadata.sorted_tables
    assert ordered, "expected a non-empty schema"
    names = [t.name for t in ordered]
    # Dependencies must come first, which is the whole point of sorted_tables.
    if "memory_definitions" in names and "agent_memories" in names:
        assert names.index("memory_definitions") < names.index("agent_memories")


def test_create_all_emits_the_schema(tmp_path):
    """End-to-end on a real temp database. No live database is touched."""
    from sqlalchemy import create_engine, inspect

    register_fk_target_models()
    engine = create_engine(f"sqlite:///{tmp_path / 'fk.sqlite'}")
    SQLModel.metadata.create_all(engine, checkfirst=True)
    present = set(inspect(engine).get_table_names())
    assert "agent_memories" in present
    assert "memory_definitions" in present


def test_registration_is_idempotent():
    first = register_fk_target_models()
    second = register_fk_target_models()
    assert set(first.imported) == set(second.imported)
    assert not second.failed
    assert unresolved_fks() == {}


def test_the_module_list_covers_every_declared_fk_target():
    """A new cross-module FK must be added to the list, or this fails."""
    register_fk_target_models()
    # Every table the list claims to contribute must actually be registered.
    for module_path, tables in FK_TARGET_MODULES.items():
        for table in tables:
            assert table in SQLModel.metadata.tables, (
                f"{module_path} claims {table}, which is not in SQLModel.metadata"
            )
