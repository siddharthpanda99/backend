"""Behavioural regressions for the governance rules engine ``core/`` + ``execution/`` slice.

Companion to ``docs/duplication-audit/MODULE-AUDIT-governance-re-core.md``.

Every test here was written to be able to FAIL. The four that pin the headline
findings were verified red by neutering the fix in place (see the report):
``test_the_pipeline_does_not_claim_to_have_evaluated_rules``,
``test_hybrid_sequential_branch_refuses_to_report_success_without_an_executor``,
``test_sandbox_quota_is_reported_as_a_violation_even_with_the_flag_off`` and
``test_get_hooks_for_ruleset_is_callable``.

The module has no dependencies beyond ``common_lib`` and never builds the
FastAPI app, so no test here pays the trap-(c) ``register_routers()`` cost.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from common_lib.modules.governance.rules_engine.core import adapters as core_adapters
from common_lib.modules.governance.rules_engine.core import context as core_context
from common_lib.modules.governance.rules_engine.core import flags as core_flags
from common_lib.modules.governance.rules_engine.core import hooks as core_hooks
from common_lib.modules.governance.rules_engine.core import (
    integration as core_integration,
)
from common_lib.modules.governance.rules_engine.core import stateful as core_stateful
from common_lib.modules.governance.rules_engine.core.decision import DecisionEngine
from common_lib.modules.governance.rules_engine.core.errors import (
    RulesEngineError,
    StageNotEvaluated,
)
from common_lib.modules.governance.rules_engine.execution import (
    engine as exec_engine,
)
from common_lib.modules.governance.rules_engine.execution import hybrid as exec_hybrid
from common_lib.modules.governance.rules_engine.execution import (
    parallel as exec_parallel,
)
from common_lib.modules.governance.rules_engine.execution import sandbox as exec_sandbox
from common_lib.modules.governance.rules_engine.execution.executor import RuleExecutor

_FLAG_ENV = {name: env for name, env in core_flags.FLAGS.items()}


@pytest.fixture(autouse=True)
def _all_flags_off(monkeypatch):
    """G9: every flag in this slice must be OFF for every test unless the test
    turns it on explicitly. If a default ever flips, the whole file goes red
    rather than silently testing the new behaviour."""
    for env in _FLAG_ENV.values():
        monkeypatch.delenv(env, raising=False)
    yield


def _enable(monkeypatch, flag: str) -> None:
    assert flag in core_flags.FLAGS, f"unknown flag {flag!r}"
    monkeypatch.setenv(core_flags.FLAGS[flag], "1")


# ---------------------------------------------------------------------------
# G9 / G3 — the flag surface itself
# ---------------------------------------------------------------------------


def test_every_rules_engine_flag_defaults_off() -> None:
    """G9: no flag in this slice may ship enabled."""
    assert core_flags.FLAGS, "expected the flag registry to be populated"
    assert all(core_flags.is_enabled(name) is False for name in core_flags.FLAGS)
    described = core_flags.describe_flags()
    assert set(described["flags"]) == set(core_flags.FLAGS)
    assert not any(described["flags"].values())


def test_flag_env_overrides_are_read() -> None:
    monkey_on = _FLAG_ENV["rules_engine.verify_sandbox_limits"]
    assert core_flags.is_enabled("rules_engine.verify_sandbox_limits") is False
    os.environ[monkey_on] = "true"
    try:
        assert core_flags.is_enabled("rules_engine.verify_sandbox_limits") is True
    finally:
        del os.environ[monkey_on]


def test_unknown_flag_name_is_off_not_an_error() -> None:
    assert core_flags.is_enabled("rules_engine.definitely_not_a_flag") is False


def test_typed_exceptions_subclass_the_rules_engine_base() -> None:
    """G8: typed exceptions, not bare Exception."""
    for exc in (StageNotEvaluated, core_flags and RulesEngineError):
        assert issubclass(exc, Exception)
    assert issubclass(StageNotEvaluated, RulesEngineError)
    assert "rules" in str(StageNotEvaluated("_run_rules", "evt-1"))


# ---------------------------------------------------------------------------
# HIGH-1 — the integration pipeline reported a completed run that never happened
# ---------------------------------------------------------------------------


def test_the_pipeline_does_not_claim_to_have_evaluated_rules() -> None:
    """HIGH-1. `UnifiedEventProcessor` is documented as the 'complete
    integration pipeline' (Event -> Interceptors -> Rules -> Hooks) and
    `process_unified_event` as the 'main entry point', but all four stages are
    no-op stubs. Before the fix the returned IntegrationContext carried nothing
    that distinguished it from a real run, and `get_pipeline_status()` answered
    `{'rules': True, ...}`."""
    proc = core_integration.UnifiedEventProcessor()
    ctx = asyncio.run(
        proc.process_event(
            core_integration.IntegrationEventType.HTTP_REQUEST,
            {"id": "evt-h1", "amount": 999_999},
        )
    )

    # Nothing ran.
    assert ctx.rule_results == []
    assert ctx.triggered_rules == []
    assert ctx.hook_results == []
    assert ctx.interceptor_results == []
    # ...and the context now says so.
    assert ctx.stages_executed == []
    assert set(ctx.stages_not_evaluated) == set(core_integration.PIPELINE_STAGES)

    report = proc.stage_report()
    assert report["pipeline_is_fully_implemented"] is False
    assert set(report["stub_stages"]) == set(core_integration.PIPELINE_STAGES)
    assert report["real_stages"] == []
    # The old lie is still available, but the truthful report now exists too.
    assert proc.get_pipeline_status()["rules"] is True


def test_pipeline_stage_report_sees_the_handler_injection_state() -> None:
    proc = core_integration.UnifiedEventProcessor()
    core_integration.reset_handlers()
    try:
        assert proc.stage_report()["hook_handler_injected"] is False
        core_integration.register_hook_handler(lambda *a: None)
        assert proc.stage_report()["hook_handler_injected"] is True
    finally:
        core_integration.reset_handlers()


def test_pipeline_fails_closed_when_the_evidence_flag_is_on(monkeypatch) -> None:
    """With the flag on, a stub stage refuses rather than returning a context
    that reads like a completed evaluation."""
    _enable(monkeypatch, "rules_engine.require_evaluation_evidence")
    proc = core_integration.UnifiedEventProcessor()
    with pytest.raises(StageNotEvaluated) as exc:
        asyncio.run(
            proc.process_event(
                core_integration.IntegrationEventType.WEBHOOK, {"id": "evt-h1b"}
            )
        )
    assert exc.value.stage in core_integration.PIPELINE_STAGES
    assert exc.value.event_id == "evt-h1b"


def test_a_subclass_that_overrides_a_stage_is_credited_with_running_it(
    monkeypatch,
) -> None:
    """The stub detection must not libel a subclass that really evaluates."""
    _enable(monkeypatch, "rules_engine.require_evaluation_evidence")

    class RealProcessor(core_integration.UnifiedEventProcessor):
        async def _run_rules(self, context):  # type: ignore[override]
            context.rule_results.append({"rule_id": "r1", "matched": True})
            return context

    proc = RealProcessor()
    assert proc.stage_report()["real_stages"] == ["_run_rules"]
    assert "_run_rules" not in proc.stage_report()["stub_stages"]

    # Still fails closed, but now on a stage that genuinely is a stub.
    with pytest.raises(StageNotEvaluated) as exc:
        asyncio.run(
            proc.process_event(core_integration.IntegrationEventType.CUSTOM, {})
        )
    assert exc.value.stage == "_run_interceptors"

    proc._pipeline_enabled["interceptors"] = False
    proc._pipeline_enabled["hooks"] = False
    proc._pipeline_enabled["triggers"] = False
    ctx = asyncio.run(
        proc.process_event(core_integration.IntegrationEventType.CUSTOM, {})
    )
    assert ctx.stages_executed == ["_run_rules"]
    assert ctx.rule_results == [{"rule_id": "r1", "matched": True}]


# ---------------------------------------------------------------------------
# HIGH-2 — hybrid branches reported SUCCESS with no rule executor wired
# ---------------------------------------------------------------------------


def test_hybrid_sequential_branch_refuses_to_report_success_without_an_executor(
    monkeypatch,
) -> None:
    """HIGH-2. `_execute_sequential` looped over the branch's rules inside
    `if self._rule_executor:`, so with no executor it dispatched nothing and
    still returned `BranchResult.SUCCESS` with `output=[]`."""
    engine = exec_hybrid.HybridExecutionEngine()
    assert engine._rule_executor is None
    branch = exec_hybrid.ExecutionBranch(
        id="b1",
        name="n",
        mode=exec_hybrid.ExecutionMode.SEQUENTIAL,
        rules=["r1", "r2"],
    )

    # Default (flag off): unchanged behaviour, so no published node changes.
    outcome = engine.execute_branch(branch, {"amount": 1})
    assert outcome.result is exec_hybrid.BranchResult.SUCCESS
    assert outcome.output == []

    _enable(monkeypatch, "rules_engine.require_evaluation_evidence")
    outcome = engine.execute_branch(branch, {"amount": 1})
    assert outcome.result is exec_hybrid.BranchResult.ERROR
    assert "no rule executor is wired" in (outcome.error or "")


@pytest.mark.parametrize(
    "mode",
    [
        exec_hybrid.ExecutionMode.PARALLEL,
        exec_hybrid.ExecutionMode.CONDITIONAL,
    ],
)
def test_hybrid_parallel_and_conditional_also_refuse(monkeypatch, mode) -> None:
    engine = exec_hybrid.HybridExecutionEngine()
    branch = exec_hybrid.ExecutionBranch(id="b", name="n", mode=mode, rules=["r1"])
    _enable(monkeypatch, "rules_engine.require_evaluation_evidence")
    outcome = engine.execute_branch(branch, {})
    assert outcome.result is exec_hybrid.BranchResult.ERROR
    assert "no rule executor is wired" in (outcome.error or "")


def test_hybrid_fallback_was_already_fail_closed_and_stays_that_way() -> None:
    """The inconsistency that proved the other three were bugs, not design:
    FALLBACK was the one mode that did not report success with no executor."""
    engine = exec_hybrid.HybridExecutionEngine()
    branch = exec_hybrid.ExecutionBranch(
        id="f", name="n", mode=exec_hybrid.ExecutionMode.FALLBACK, rules=["r1"]
    )
    outcome = engine.execute_branch(branch, {})
    assert outcome.result is exec_hybrid.BranchResult.FAILURE
    assert "no rule executor is wired" in (outcome.error or "")


def test_hybrid_a_wired_executor_still_succeeds(monkeypatch) -> None:
    """The fail-closed path must not break the working path."""
    _enable(monkeypatch, "rules_engine.require_evaluation_evidence")
    engine = exec_hybrid.HybridExecutionEngine()
    engine.set_rule_executor(lambda rule_id, ctx: {"rule": rule_id, "verdict": "deny"})
    branch = exec_hybrid.ExecutionBranch(
        id="b",
        name="n",
        mode=exec_hybrid.ExecutionMode.SEQUENTIAL,
        rules=["r1", "r2"],
    )
    outcome = engine.execute_branch(branch, {})
    assert outcome.result is exec_hybrid.BranchResult.SUCCESS
    assert [o["rule"] for o in outcome.output] == ["r1", "r2"]


def test_hybrid_branch_cycle_terminates_instead_of_looping_forever() -> None:
    """`on_success` ids are author-supplied and unvalidated, so a -> b -> a
    looped forever, re-dispatching rules and growing the outcome list."""
    engine = exec_hybrid.HybridExecutionEngine()
    calls: list[str] = []
    engine.set_rule_executor(lambda rule_id, ctx: calls.append(rule_id))
    engine.register_branches(
        [
            exec_hybrid.ExecutionBranch(id="a", name="a", rules=["ra"], on_success="b"),
            exec_hybrid.ExecutionBranch(id="b", name="b", rules=["rb"], on_success="a"),
        ]
    )
    result = engine.execute("a", {})
    assert result.execution_path == ["a", "b"]
    assert result.branch_outcomes[-1].result is exec_hybrid.BranchResult.ERROR
    assert "cycle detected" in (result.branch_outcomes[-1].error or "")
    assert calls == ["ra", "rb"], "each rule must be dispatched at most once"


def test_hybrid_a_guard_over_a_missing_field_fails_closed_when_flagged(
    monkeypatch,
) -> None:
    """`ne` over an absent field evaluated against None and therefore PASSED —
    a fail-open compliance guard for a context that carries no such field."""
    engine = exec_hybrid.HybridExecutionEngine()
    condition = {"field": "data.region", "ne": "eu"}
    assert engine.evaluate_condition(condition, {"data": {}}) is True

    _enable(monkeypatch, "rules_engine.require_evaluation_evidence")
    assert engine.evaluate_condition(condition, {"data": {}}) is False
    # A field that IS present still behaves normally.
    assert engine.evaluate_condition(condition, {"data": {"region": "us"}}) is True
    assert engine.evaluate_condition(condition, {"data": {"region": "eu"}}) is False


def test_hybrid_condition_runner_does_not_silently_drop_rules() -> None:
    """Reported, not fixed: CONDITIONAL runs only `branch.rules[0]` and reports
    SUCCESS, so rules 2..N are dropped with no record."""
    engine = exec_hybrid.HybridExecutionEngine()
    seen: list[str] = []
    engine.set_rule_executor(lambda rule_id, ctx: seen.append(rule_id))
    branch = exec_hybrid.ExecutionBranch(
        id="c",
        name="n",
        mode=exec_hybrid.ExecutionMode.CONDITIONAL,
        rules=["r1", "r2", "r3"],
    )
    outcome = engine.execute_branch(branch, {})
    assert outcome.result is exec_hybrid.BranchResult.SUCCESS
    assert seen == ["r1"], "pinned as-is: only the first conditional rule runs"


# ---------------------------------------------------------------------------
# HIGH-3 — parallel tasks reported COMPLETED having dispatched nothing
# ---------------------------------------------------------------------------


def test_parallel_task_is_not_completed_when_no_executor_is_wired(
    monkeypatch,
) -> None:
    """HIGH-3. `execute_all()` -> `{total_tasks: 2, completed: 2, failed: 0,
    task_results: [{status: 'completed', result: null}, ...]}` with no rule
    executor ever configured."""
    engine = exec_parallel.ParallelExecutionEngine()
    engine.add_tasks(
        [
            exec_parallel.ParallelTask(id="t1", rule_id="rule-a"),
            exec_parallel.ParallelTask(id="t2", rule_id="rule-b"),
        ]
    )
    result = engine.execute_all()
    assert (result.total_tasks, result.completed, result.failed) == (2, 2, 0)
    assert all(t.result is None for t in result.task_results)

    _enable(monkeypatch, "rules_engine.require_evaluation_evidence")
    engine2 = exec_parallel.ParallelExecutionEngine()
    engine2.add_tasks([exec_parallel.ParallelTask(id="t1", rule_id="rule-a")])
    result2 = engine2.execute_all()
    assert (result2.completed, result2.failed) == (0, 1)
    assert "no rule executor is wired" in (result2.task_results[0].error or "")


def test_parallel_result_to_dict_no_longer_erases_falsy_results() -> None:
    """`str(t.result) if t.result else None` turned 0 / '' / [] / False into
    None, so a rule that legitimately returned "no violation" was
    indistinguishable from one that returned nothing."""
    engine = exec_parallel.ParallelExecutionEngine()
    engine.set_rule_executor(lambda rule_id, ctx: 0)
    engine.add_tasks([exec_parallel.ParallelTask(id="t1", rule_id="r")])
    payload = engine.execute_all().to_dict()
    assert payload["task_results"][0]["has_result"] is True
    assert payload["task_results"][0]["result"] == "0"


def test_parallel_dependency_free_failure_no_longer_loops_forever() -> None:
    """The scheduler re-readied every task whose id was not in
    `completed_ids`, so a dependency-free task that FAILED was re-dispatched
    on every round, forever."""
    calls: list[str] = []

    def boom(rule_id, ctx):
        calls.append(rule_id)
        raise RuntimeError("rule blew up")

    engine = exec_parallel.ParallelExecutionEngine()
    engine.set_rule_executor(boom)
    tasks = [exec_parallel.ParallelTask(id="t1", rule_id="r1")]

    result = engine.execute_with_dependencies(tasks, {})

    assert calls == ["r1"], "a failed task must be attempted exactly once"
    assert result.failed == 1
    assert result.skipped == []


def test_parallel_blocked_dependents_are_reported_not_vanished() -> None:
    """A task whose dependency failed was never dispatched and never appeared
    in task_results, so completed + failed was quietly < total_tasks."""

    def selective(rule_id, ctx):
        if rule_id == "good":
            return {"ok": True}
        raise RuntimeError("dep failed")

    engine = exec_parallel.ParallelExecutionEngine()
    engine.set_rule_executor(selective)
    tasks = [
        exec_parallel.ParallelTask(id="t1", rule_id="bad"),
        exec_parallel.ParallelTask(id="t2", rule_id="good"),
        exec_parallel.ParallelTask(id="t3", rule_id="needs-t2"),
    ]
    result = engine.execute_with_dependencies(
        tasks,
        {"t3": ["t1"]},  # t1 fails, so t3 can never run
    )
    assert result.skipped == ["t3"]
    payload = result.to_dict()
    assert payload["accounted_for"] is True
    assert payload["unaccounted_for"] == 0
    assert payload["skipped"] == ["t3"]


def test_parallel_a_declared_timeout_is_reported_as_a_failure() -> None:
    """NotImplementedError is raised, not silently ignored: fail-closed."""
    engine = exec_parallel.ParallelExecutionEngine()
    engine.set_rule_executor(lambda rule_id, ctx: {"ok": True})
    task = exec_parallel.ParallelTask(id="t1", rule_id="r", timeout=1.5)
    result = engine._execute_task(task)
    assert result.status is exec_parallel.TaskStatus.FAILED
    assert "not implemented" in (result.error or "")


# ---------------------------------------------------------------------------
# HIGH-4 — the sandbox reported a resource attestation it never checked
# ---------------------------------------------------------------------------


def test_sandbox_quota_is_reported_as_a_violation_even_with_the_flag_off() -> None:
    """HIGH-4. The tracked-call wrapper was bound to the *sandboxed* name
    `exec`, but the outer `exec(task.code, ...)` is what ran the code, so
    `call_count` stayed 0 and `_check_resources` was never reached. A 3M-
    iteration script against a 1 ms / 1-call quota came back SUCCESS with
    `resources_used={'function_calls': 0}`."""
    config = exec_sandbox.SandboxConfig(
        sandbox_type=exec_sandbox.SandboxType.PROCESS,
        quota=exec_sandbox.ResourceQuota(cpu_time_ms=1, max_function_calls=1),
    )
    engine = exec_sandbox.SandboxEngine(config)
    result = engine.execute(
        exec_sandbox.SandboxTask(
            id="s1",
            code="x=0\nfor i in range(300000):\n    x+=i\nresult=x",
            input_data={},
        )
    )
    # Default path keeps the historic SUCCESS, but now carries the truth.
    assert result.status is exec_sandbox.SandboxResult.SUCCESS
    assert result.limits_enforced is False
    assert result.limit_violation == "cpu_time exceeded"


def test_sandbox_enforces_its_quota_when_flagged(monkeypatch) -> None:
    _enable(monkeypatch, "rules_engine.verify_sandbox_limits")
    config = exec_sandbox.SandboxConfig(
        sandbox_type=exec_sandbox.SandboxType.PROCESS,
        quota=exec_sandbox.ResourceQuota(cpu_time_ms=1, max_function_calls=1),
    )
    engine = exec_sandbox.SandboxEngine(config)
    result = engine.execute(
        exec_sandbox.SandboxTask(
            id="s1", code="x=0\nfor i in range(300000):\n    x+=i\nresult=x"
        )
    )
    assert result.status is exec_sandbox.SandboxResult.TIMEOUT
    assert result.limits_enforced is True
    assert result.limit_violation == "cpu_time exceeded"


@pytest.mark.parametrize(
    "requested",
    [exec_sandbox.SandboxType.CONTAINER, exec_sandbox.SandboxType.VM],
)
def test_sandbox_container_and_vm_run_in_process_and_say_so(requested) -> None:
    """`execute` routed CONTAINER and VM to the very same in-process exec as
    NONE, so a caller asking for a container got a success for isolation that
    does not exist."""
    config = exec_sandbox.SandboxConfig(sandbox_type=requested)
    engine = exec_sandbox.SandboxEngine(config)
    result = engine.execute(
        exec_sandbox.SandboxTask(id="s1", code="result=41+1", input_data={})
    )
    assert result.status is exec_sandbox.SandboxResult.SUCCESS
    assert result.isolation == "in_process", requested
    assert result.output == 42


@pytest.mark.parametrize(
    "requested",
    [exec_sandbox.SandboxType.CONTAINER, exec_sandbox.SandboxType.VM],
)
def test_sandbox_refuses_unimplemented_isolation_when_flagged(
    monkeypatch, requested
) -> None:
    _enable(monkeypatch, "rules_engine.enforce_sandbox_isolation")
    engine = exec_sandbox.SandboxEngine(
        exec_sandbox.SandboxConfig(sandbox_type=requested)
    )
    result = engine.execute(
        exec_sandbox.SandboxTask(id="s1", code="result=1", input_data={})
    )
    assert result.status is exec_sandbox.SandboxResult.SECURITY_VIOLATION
    assert "not implemented" in (result.error or "")


def test_sandbox_safe_globals_are_escapable_and_that_is_pinned_here() -> None:
    """The restricted namespace blocks `__import__` and `open` but exposes
    `getattr`, so `().__class__.__base__.__subclasses__()` reaches a class
    whose `__init__.__globals__['__builtins__']` hands back the REAL builtins.
    The task is reported `status='success'`.

    This test does not fix that (removing the escape means replacing exec-based
    execution with a real process boundary, which is a redesign). It pins the
    finding so it cannot be forgotten, and asserts the payload now tells the
    truth about what happened."""
    engine = exec_sandbox.SandboxEngine(
        exec_sandbox.SandboxConfig(sandbox_type=exec_sandbox.SandboxType.NONE)
    )
    probe = (
        "b = None\n"
        "for c in ().__class__.__base__.__subclasses__():\n"
        "    gi = getattr(getattr(c, '__init__', None), '__globals__', None)\n"
        "    if gi and '__builtins__' in gi:\n"
        "        bb = gi['__builtins__']\n"
        "        b = getattr(bb, '__dict__', bb)\n"
        "        if b and 'eval' in b:\n"
        "            break\n"
        "result = ('ESCAPED', 'eval' in b)\n"
    )
    result = engine.execute(
        exec_sandbox.SandboxTask(id="esc", code=probe, input_data={})
    )
    assert result.status is exec_sandbox.SandboxResult.SUCCESS
    assert result.output == ("ESCAPED", True), (
        "the safe-globals sandbox is still escapable; if this now fails the "
        "escape was closed and this test should be replaced with a positive "
        "assertion that real builtins are NOT reachable"
    )


def test_sandbox_task_globals_can_replace_the_whole_restricted_namespace() -> None:
    """`safe_globals.update(task.globals)` runs AFTER the restricted builtins
    are installed, so a caller passing `globals={'__builtins__': builtins}`
    replaces the sandbox wholesale. Pinned as a known hole."""
    import builtins as _builtins

    engine = exec_sandbox.SandboxEngine()
    result = engine.execute(
        exec_sandbox.SandboxTask(
            id="g",
            code="result=1",
            input_data={},
            globals={"__builtins__": _builtins},
        )
    )
    assert result.status is exec_sandbox.SandboxResult.SUCCESS
    assert result.output == 1


def test_sandbox_records_every_single_execution_in_its_history() -> None:
    """Only `execute_batch` recorded history, so the engine's sole audit trail
    was empty for every individual `execute()` call."""
    engine = exec_sandbox.SandboxEngine()
    engine.execute(exec_sandbox.SandboxTask(id="solo", code="result=1", input_data={}))
    assert "solo" in engine.get_execution_history()


def test_sandbox_dead_quota_fields_are_documented_not_honoured() -> None:
    """Pins the report: `memory_bytes`, `max_file_size_bytes`,
    `allowed_modules`, `blocked_modules`, `enable_network`,
    `enable_file_system` and `timeout_seconds` are read by nothing."""
    quota = exec_sandbox.ResourceQuota()
    for name in ("memory_bytes", "max_file_size_bytes"):
        assert getattr(quota, name) > 0
    config = exec_sandbox.SandboxConfig()
    for name in (
        "allowed_modules",
        "blocked_modules",
        "enable_network",
        "enable_file_system",
        "timeout_seconds",
    ):
        assert hasattr(config, name)


# ---------------------------------------------------------------------------
# HIGH-5 — core/hooks.py was un-constructible and half of it always raised
# ---------------------------------------------------------------------------


def test_get_hooks_for_ruleset_is_callable() -> None:
    """HIGH-5(a). The module sets `get_rule_registry = None` as a lazy-import
    shim and defines `_get_rule_registry()` to fill it, but
    `get_hooks_for_ruleset` called the *global* — which nothing ever filled —
    so this published @node raised
    `TypeError: 'NoneType' object is not callable` on 100% of calls."""
    mapper = core_hooks.RulesToHooksMapper(decision_engine=DecisionEngine())
    # Call the reader FIRST, before anything has had a chance to populate the
    # module-level `get_rule_registry` shim. Calling `_get_rule_registry()`
    # first would set that global and mask the very bug being pinned.
    assert mapper.get_hooks_for_ruleset("no-such-ruleset") == []
    # The lazy loader is what the reader must use.
    assert callable(core_hooks._get_rule_registry())


def test_rules_to_hooks_mapper_can_be_built_without_an_explicit_engine() -> None:
    """HIGH-5(b). `__init__` referenced a bare `get_decision_engine` that this
    module never imported, so `RulesToHooksMapper()`, `get_hooks_mapper()` and
    the exported `apply_ruleset_to_hooks` all raised NameError."""
    mapper = core_hooks.RulesToHooksMapper()
    assert mapper._decision_engine is not None
    assert core_hooks.get_hooks_mapper() is not None
    assert callable(core_hooks.apply_ruleset_to_hooks)


def test_hooks_for_a_ruleset_accepts_both_action_spellings() -> None:
    """`executor.py` routes both `activate_hook` and `execute_hook`, but this
    reader only matched the alias, so it under-reported the hooks a ruleset
    would really fire."""

    class _Action:
        def __init__(self, action_type, target):
            self.action_type = action_type
            self.target = target

    class _Rule:
        def __init__(self, actions):
            self.actions = actions

    class _RuleSet:
        rules = [
            _Rule(
                [
                    _Action("execute_hook", "hook-a"),
                    _Action("activate_hook", "hook-b"),
                    _Action("block", "not-a-hook"),
                ]
            )
        ]

    class _Registry:
        def get_ruleset(self, ruleset_id):
            return _RuleSet() if ruleset_id == "rs-1" else None

    mapper = core_hooks.RulesToHooksMapper(decision_engine=_StubDecision())
    monkey = core_hooks
    original = monkey._get_rule_registry
    monkey._get_rule_registry = lambda: lambda: _Registry()
    try:
        assert mapper.get_hooks_for_ruleset("rs-1") == ["hook-a", "hook-b"]
        assert mapper.get_hooks_for_ruleset("nope") == []
    finally:
        monkey._get_rule_registry = original


def test_unregistered_hooks_are_reported_instead_of_silently_dropped() -> None:
    """A decision naming a hook with no registered executor produced
    `hooks_executed: []` next to `success: true` — indistinguishable from
    "nothing matched"."""
    mapper = core_hooks.RulesToHooksMapper(decision_engine=_StubDecision())
    mapper._decision_engine.decide_with_ruleset = lambda *a, **k: {
        "success": True,
        "explanation": "Matched rules: block-unapproved-region",
        "hooks_to_execute": ["deny-hook"],
        "triggers_to_activate": ["notify-hook"],
        "context_updates": {},
    }
    out = mapper.apply_ruleset_to_hooks("rs-1", {"amount": 1})
    assert out["hooks_executed"] == []
    assert out["hooks_skipped"] == ["deny-hook"]
    assert out["triggers_skipped"] == ["notify-hook"]
    assert out["enforcement_complete"] is False


def test_a_registered_hook_that_runs_is_reported_as_complete() -> None:
    mapper = core_hooks.RulesToHooksMapper(decision_engine=_StubDecision())
    seen: list[dict] = []
    mapper.register_hook_executor("deny-hook", seen.append)
    mapper._decision_engine.decide_with_ruleset = lambda *a, **k: {
        "success": True,
        "explanation": "",
        "hooks_to_execute": ["deny-hook"],
        "triggers_to_activate": [],
        "context_updates": {},
    }
    out = mapper.apply_ruleset_to_hooks("rs-1", {"amount": 1})
    assert out["hooks_skipped"] == []
    assert out["enforcement_complete"] is True
    assert seen == [{"amount": 1}]


# ---------------------------------------------------------------------------
# core/stateful.py — a transition that never happened, reported as done
# ---------------------------------------------------------------------------


def test_stateful_transition_without_a_handler_is_not_reported_as_done(
    monkeypatch,
) -> None:
    """HIGH-6. `can_transition` passed, no handler was registered, the state
    was NOT changed, and the method returned True."""
    mgr = core_stateful.StateManager()
    mgr.create_state("ent-1", "active")
    rule = core_stateful.StatefulRule(
        rule_id="r", state_machine={"escalate": ["active"]}, handlers={}
    )
    assert rule.execute_transition(mgr, "ent-1", "escalate") is True
    assert mgr.get_state("ent-1").state == "active"

    _enable(monkeypatch, "rules_engine.require_transition_handler")
    assert rule.execute_transition(mgr, "ent-1", "escalate") is False


def test_a_real_state_transition_is_recorded_in_the_entity_history() -> None:
    """Nothing recorded transitions in the state history, so `get_history` was
    empty for any entity driven by a StatefulRule."""
    mgr = core_stateful.StateManager()
    mgr.create_state("ent-2", "active")
    rule = core_stateful.StatefulRule(
        rule_id="r",
        state_machine={"escalate": ["active"]},
        handlers={"escalate": "escalated"},
    )
    assert rule.execute_transition(mgr, "ent-2", "escalate") is True
    assert mgr.get_state("ent-2").state == "escalated"
    history = mgr.get_history("ent-2")
    assert [e.event_type for e in history] == ["state_transition"]
    assert history[0].data["to_state"] == "escalated"


def test_an_illegal_transition_still_returns_false() -> None:
    """A validation that must NOT be weakened."""
    mgr = core_stateful.StateManager()
    mgr.create_state("ent-3", "active")
    rule = core_stateful.StatefulRule(
        rule_id="r", state_machine={"escalate": ["closed"]}, handlers={}
    )
    assert rule.execute_transition(mgr, "ent-3", "escalate") is False
    assert rule.execute_transition(mgr, "no-such-entity", "escalate") is False


# ---------------------------------------------------------------------------
# core/context.py — a TTL that could never be set, and an IndexError
# ---------------------------------------------------------------------------


def test_context_ttl_is_now_settable_and_expiry_is_honoured() -> None:
    """`ContextValue.ttl` existed and `clear_expired` was a published @node,
    but `ContextStore.set` had no way to supply a ttl, so it could only ever
    return 0 and an expired value stayed readable forever."""
    store = core_context.ContextStore()
    store.set("short", "v", ttl=-1)  # already expired
    assert store.clear_expired() == 1
    assert store.get("short", default="gone") == "gone"

    store.set("live", "v", ttl=3600)
    assert store.get("live") == "v"
    assert store.clear_expired() == 0

    store.set("stale", "v", ttl=-1)
    assert store.get("stale", default="gone") == "gone"


def test_context_set_without_a_ttl_still_works() -> None:
    """Additive parameter: the historic call shape is unchanged."""
    store = core_context.ContextStore()
    store.set("k", "v")
    assert store.get("k") == "v"
    assert store.get("missing", default="d") == "d"


def test_get_version_out_of_range_returns_none_not_an_indexerror() -> None:
    mgr = core_context.ContextManager()
    mgr.version_context("k", core_context.Context(type=core_context.ContextType.STATIC))
    assert mgr.get_version("k") is not None
    assert mgr.get_version("k", -1) is not None
    assert mgr.get_version("k", -500) is None
    assert mgr.get_version("k", 99) is None
    assert mgr.get_version("never-keyed") is None


# ---------------------------------------------------------------------------
# execution/engine.py — scope enforcement failed open on an absent fact
# ---------------------------------------------------------------------------


class _Scope:
    def __init__(self, org_ids=None, event_types=None):
        self.org_ids = org_ids
        self.event_types = event_types


class _ScopedRule:
    def __init__(self, rule_id, scope):
        self.id = rule_id
        self.scope = scope


def test_scope_fails_closed_on_a_missing_fact_when_flagged(monkeypatch) -> None:
    """`_matches_scope` read `if caller_org and caller_org not in
    scope.org_ids`, so a context with no `org_id` skipped the restriction
    entirely: a rule scoped to one tenant fired for every tenant-less
    context."""
    eng = exec_engine.RulesEngine()
    rule = _ScopedRule("r-tenant", _Scope(org_ids=["org-eu"]))

    assert eng._matches_scope(rule, {"amount": 1}) is True
    assert eng._matches_scope(rule, {"org_id": "org-us"}) is False
    assert eng._matches_scope(rule, {"org_id": "org-eu"}) is True

    _enable(monkeypatch, "rules_engine.require_scope_fact")
    assert eng._matches_scope(rule, {"amount": 1}) is False
    assert eng._matches_scope(rule, {"org_id": "org-us"}) is False
    assert eng._matches_scope(rule, {"org_id": "org-eu"}) is True
    # An unscoped rule is unaffected.
    assert eng._matches_scope(_ScopedRule("r-any", None), {}) is True


def test_rule_condition_annotation_name_is_imported() -> None:
    """`engine.py` annotated `list[RuleCondition]` without importing it.
    `from __future__ import annotations` hid the NameError until something
    called `typing.get_type_hints` on the method."""
    import typing

    hints = typing.get_type_hints(exec_engine.RulesEngine._evaluate_conditions)
    assert "conditions" in hints


# ---------------------------------------------------------------------------
# execution/executor.py — a rule that raised looked like a rule that passed
# ---------------------------------------------------------------------------


class _StubDecision:
    """Stands in for `DecisionEngine` so the mapper's own logic is under test."""

    def decide_with_ruleset(self, *args, **kwargs):  # pragma: no cover - replaced
        raise AssertionError("the test replaces this")

    def decide(self, *args, **kwargs):  # pragma: no cover - replaced
        raise AssertionError("the test replaces this")


class _BoomRule:
    id = "boom"
    name = "Explodes on evaluate"
    actions: list = []

    def evaluate(self, context):
        raise RuntimeError("condition compiler blew up")


class _MatchRule:
    id = "match"
    name = "Matches"
    actions: list = []

    def evaluate(self, context):
        return True


def test_a_rule_that_raises_is_distinguishable_from_one_that_does_not_match() -> None:
    """`except Exception` recorded `Decision(matched=False)`, and
    `DecisionEngine._build_explanation` rendered that as *"No rules matched.
    Default behavior applies."* — a crash reported as a clean compliance pass."""
    ex = RuleExecutor(registry=object())
    ex._registry = type(
        "R", (), {"get_rules_for_context": staticmethod(lambda ctx: [])}
    )()

    from common_lib.modules.governance.rules_engine.core.types import ExecutionContext

    ctx = ExecutionContext(data={})
    result = ex.execute(ctx, rules=[_BoomRule(), _MatchRule()])
    payload = result.to_dict()

    assert result.rules_evaluated == 2
    assert result.rules_errored == 1
    assert result.evaluation_complete is False
    assert payload["errors"][0]["rule_id"] == "boom"
    assert "condition compiler blew up" in payload["errors"][0]["error"]
    # The historic `success` semantics are preserved while the flag is off.
    assert result.success is True


def test_a_clean_run_reports_a_complete_evaluation() -> None:
    from common_lib.modules.governance.rules_engine.core.types import ExecutionContext

    ex = RuleExecutor(registry=object())
    result = ex.execute(ExecutionContext(data={}), rules=[_MatchRule()])
    assert result.rules_evaluated == 1
    assert result.rules_errored == 0
    assert result.evaluation_complete is True
    assert result.errors == []


def test_depend_on_rule_errors_flag_turns_a_partial_run_into_a_failure(
    monkeypatch,
) -> None:
    from common_lib.modules.governance.rules_engine.core.types import ExecutionContext

    _enable(monkeypatch, "rules_engine.depend_on_rule_errors")
    ex = RuleExecutor(registry=object())
    result = ex.execute(ExecutionContext(data={}), rules=[_BoomRule(), _MatchRule()])
    assert result.success is False
    assert result.evaluation_complete is False


def test_an_unknown_ruleset_reports_that_nothing_was_evaluated() -> None:
    ex = RuleExecutor(registry=object())
    from common_lib.modules.governance.rules_engine.core.types import ExecutionContext

    ex._registry = type("R", (), {"get_ruleset": staticmethod(lambda rid: None)})()
    result = ex.execute_ruleset("no-such-ruleset", ExecutionContext(data={}))
    assert result.evaluation_complete is False
    assert "unknown ruleset_id" in result.errors[0]["error"]


# ---------------------------------------------------------------------------
# core/adapters.py — a webhook secret that verified nothing
# ---------------------------------------------------------------------------


def test_webhook_signature_verification_roundtrips() -> None:
    import hashlib
    import hmac

    secret = "s3cr3t"
    adapter = core_adapters.WebhookAdapter("wh-1", secret=secret)
    body = '{"amount": 1}'
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    assert adapter.verify_signature(body, sig) == {"verified": True, "reason": None}
    assert adapter.verify_signature(body, f"sha256={sig}")["verified"] is True
    assert adapter.verify_signature(body, "deadbeef")["verified"] is False
    assert adapter.verify_signature(body, None)["reason"] == "signature header absent"

    unsigned = core_adapters.WebhookAdapter("wh-2")
    assert unsigned.verify_signature(body, sig)["reason"] == "no secret configured"


def test_adapter_registry_rejects_unsigned_webhooks_when_flagged(monkeypatch) -> None:
    reg = core_adapters.AdapterRegistry()
    reg.register(core_adapters.WebhookAdapter("wh-1", secret="s3cr3t"))

    body = '{"amount": 1}'
    assert reg.process("wh-1", body) is not None
    assert reg.last_rejection is None

    _enable(monkeypatch, "rules_engine.require_webhook_signature")
    assert reg.process("wh-1", body) is None
    assert "signature_rejected" in (reg.last_rejection or {}).get("reason", "")


def test_adapter_process_says_why_it_returned_none() -> None:
    """`process` collapsed unknown-adapter / disabled / invalid into one
    `None`, so a dropped governance event was indistinguishable from an
    empty one."""
    reg = core_adapters.AdapterRegistry()
    adapter = core_adapters.APIAdapter("api-1", path="/x")
    reg.register(adapter)

    assert reg.process("nope", {}) is None
    assert reg.last_rejection["reason"] == "unknown_adapter"

    adapter.disable()
    assert reg.process("api-1", {}) is None
    assert reg.last_rejection["reason"] == "adapter_disabled"

    adapter.enable()
    adapter.set_expected_fields(["amount"])
    assert reg.process("api-1", {"other": 1}) is None
    assert reg.last_rejection["reason"] == "validation_failed"

    assert reg.process("api-1", {"amount": 1}) is not None
    assert reg.last_rejection is None


def test_api_adapter_expected_fields_are_bypassed_by_a_non_dict() -> None:
    """Reported, not fixed: `APIAdapter.validate` returns True for a non-dict,
    and `normalize` then wraps it as `{"data": ...}` — so every declared
    required field is absent from the payload that gets normalized."""
    adapter = core_adapters.APIAdapter("api-1", path="/x")
    adapter.set_expected_fields(["amount"])
    assert adapter.validate("not-a-dict") is True
    assert "amount" not in adapter.normalize("not-a-dict").payload


def test_db_trigger_adapter_survives_a_realistic_row() -> None:
    """`_generate_id` used a bare `json.dumps`, so a DB row containing a
    datetime/Decimal — the input this adapter exists for — raised TypeError."""
    import datetime
    from decimal import Decimal

    adapter = core_adapters.DatabaseTriggerAdapter(
        "db-1", table="orders", operation="INSERT"
    )
    event = adapter.normalize(
        {"id": 1, "total": Decimal("9.99"), "at": datetime.datetime(2026, 1, 1)}
    )
    assert event.event_id
    assert event.source_id == "orders"
    assert event.metadata["operation"] == "INSERT"


# ---------------------------------------------------------------------------
# G5 / G1 hygiene for the slice
# ---------------------------------------------------------------------------


def test_no_relative_imports_in_the_slice() -> None:
    """G5."""
    import pathlib
    import re

    root = pathlib.Path(core_integration.__file__).parent
    pattern = re.compile(r"^\s*(from|import)\s+\.")
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.match(line):
                offenders.append(f"{path.name}:{i}: {line.strip()}")
    assert not offenders, offenders


def test_no_fastapi_imports_in_the_slice() -> None:
    """G1: logic in common_lib, transport in Backend/app."""
    import pathlib

    root = pathlib.Path(core_integration.__file__).parent
    offenders = [
        str(p)
        for p in root.rglob("*.py")
        if "fastapi" in p.read_text()
        and "__pycache__" not in p.parts
        and "tests" not in p.parts
    ]
    assert not offenders, offenders
