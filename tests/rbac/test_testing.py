"""Tests for RBAC Testing/Fuzzing/Verification (SSOT 32).

Verifies PermissionFuzzer and AuthorizationVerifier for generating
and running permission test scenarios.
"""


import pytest
from datetime import datetime

class TestPermissionFuzzer:
    """Test PermissionFuzzer scenario generation."""

    def test_generate_random_scenarios(self, sqlmodel_db):
        from common_lib.modules.rbac.testing.service import PermissionFuzzer, FuzzStrategy
        fuzzer = PermissionFuzzer(sqlmodel_db, seed=42)
        scenarios = fuzzer.generate_scenarios(strategy=FuzzStrategy.RANDOM, count=10)
        assert len(scenarios) == 10
        for s in scenarios:
            assert s.user_id > 0
            assert s.permission_name
            assert isinstance(s.expected_result, bool)

    def test_generate_edge_cases(self, sqlmodel_db):
        from common_lib.modules.rbac.testing.service import PermissionFuzzer, FuzzStrategy
        fuzzer = PermissionFuzzer(sqlmodel_db, seed=42)
        scenarios = fuzzer.generate_scenarios(strategy=FuzzStrategy.EDGE_CASE, count=5)
        assert len(scenarios) > 0
        # Edge cases should include empty, zero, None-like scenarios
        user_ids = {s.user_id for s in scenarios}
        assert 0 in user_ids or -1 in user_ids

    def test_generate_negative_scenarios(self, sqlmodel_db):
        from common_lib.modules.rbac.testing.service import PermissionFuzzer, FuzzStrategy
        fuzzer = PermissionFuzzer(sqlmodel_db, seed=42)
        scenarios = fuzzer.generate_scenarios(strategy=FuzzStrategy.NEGATIVE, count=5)
        assert len(scenarios) > 0
        # All negative scenarios should expect False
        for s in scenarios:
            assert s.expected_result is False

    def test_generate_stress_scenarios(self, sqlmodel_db):
        from common_lib.modules.rbac.testing.service import PermissionFuzzer, FuzzStrategy
        fuzzer = PermissionFuzzer(sqlmodel_db, seed=42)
        scenarios = fuzzer.generate_scenarios(strategy=FuzzStrategy.STRESS, count=20)
        assert len(scenarios) == 20
        assert all("stress" in s.name for s in scenarios)

class TestAuthorizationVerifier:
    """Test AuthorizationVerifier scenario execution."""

    def test_run_single_scenario(self, sqlmodel_db):
        from common_lib.modules.rbac.testing.service import AuthorizationVerifier, VerificationScenario
        verifier = AuthorizationVerifier(sqlmodel_db)
        scenario = VerificationScenario(
            name="test_single",
            description="Single test scenario",
            user_id=1,
            permission_name="test:read",
            resource_id=None,
            expected_result=False,
        )
        result = verifier.run_scenario(scenario)
        assert result.expected is False
        assert result.passed is True  # Default deny

    def test_run_batch_empty(self, sqlmodel_db):
        from common_lib.modules.rbac.testing.service import AuthorizationVerifier
        verifier = AuthorizationVerifier(sqlmodel_db)
        report = verifier.run_batch([])
        assert report["total"] == 0
        assert report["pass_rate"] == 0

    def test_get_coverage_report_empty(self, sqlmodel_db):
        from common_lib.modules.rbac.testing.service import AuthorizationVerifier
        verifier = AuthorizationVerifier(sqlmodel_db)
        report = verifier.get_coverage_report()
        assert "No scenarios" in report["status"]

    def test_get_coverage_after_scenarios(self, sqlmodel_db):
        from common_lib.modules.rbac.testing.service import AuthorizationVerifier, VerificationScenario
        verifier = AuthorizationVerifier(sqlmodel_db)
        scenarios = [
            VerificationScenario("s1", "test1", 1, "perm:a", "res_1", False),
            VerificationScenario("s2", "test2", 2, "perm:b", "res_2", False),
        ]
        verifier.run_batch(scenarios)
        report = verifier.get_coverage_report()
        assert report["unique_permissions_tested"] == 2
        assert report["unique_users_tested"] == 2
