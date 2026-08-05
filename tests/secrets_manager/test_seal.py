"""Tests for Secrets Manager Seal submodule (SSOT §16)."""

from __future__ import annotations

import pytest
from common_lib.modules.secrets_manager.seal.service import SealService
from common_lib.modules.secrets_manager.seal.models import SealState, SealConfig, SealStatus


class TestSealService:
    """Test seal/unseal lifecycle."""

    def test_get_seal_status_not_configured(self, db):
        svc = SealService(session=db)
        status = svc.get_seal_status()
        assert status["sealed"] is True
        assert status["threshold"] == 0

    def test_configure_seal(self, db):
        svc = SealService(session=db)
        result = svc.configure_seal(total_shares=5, threshold=3)
        assert result["sealed"] is True
        assert result["total_shares"] == 5
        assert result["threshold"] == 3
        assert result["progress"] == 0

    def test_configure_seal_with_auto_unseal(self, db):
        svc = SealService(session=db)
        result = svc.configure_seal(total_shares=3, threshold=2, auto_unseal_provider="aws_kms")
        assert result["auto_unseal_enabled"] is True
        assert result["auto_unseal_provider"] == "aws_kms"

    def test_submit_share_progress(self, db):
        svc = SealService(session=db)
        svc.configure_seal(total_shares=3, threshold=3)
        status = svc.submit_unseal_share("op-1", "share-key-1")
        assert status["sealed"] is True
        assert status["shares_submitted"] == 1

    def test_submit_share_reaches_threshold(self, db):
        svc = SealService(session=db)
        svc.configure_seal(total_shares=3, threshold=2)
        svc.submit_unseal_share("op-1", "share-key-a")
        status = svc.submit_unseal_share("op-2", "share-key-b")
        assert status["sealed"] is False
        assert status["status"] == "unsealed"
        assert status["progress"] == 100.0

    def test_duplicate_operator_share_rejected(self, db):
        svc = SealService(session=db)
        svc.configure_seal(total_shares=3, threshold=3)
        svc.submit_unseal_share("op-1", "share-key")
        result = svc.submit_unseal_share("op-1", "share-key-again")
        assert "error" in result

    def test_seal(self, db):
        svc = SealService(session=db)
        svc.configure_seal(total_shares=3, threshold=2)
        svc.submit_unseal_share("op-1", "key-a")
        svc.submit_unseal_share("op-2", "key-b")
        status = svc.seal()
        assert status["sealed"] is True
        assert status["shares_submitted"] == 0

    def test_auto_unseal(self, db):
        svc = SealService(session=db)
        svc.configure_seal(total_shares=3, threshold=2, auto_unseal_provider="local")
        status = svc.auto_unseal()
        assert status["sealed"] is False
        assert status["status"] == "unsealed"

    def test_auto_unseal_not_configured(self, db):
        svc = SealService(session=db)
        svc.configure_seal(total_shares=3, threshold=2)
        result = svc.auto_unseal()
        assert "error" in result

    def test_generate_recovery_keys(self, db):
        svc = SealService(session=db)
        keys = svc.generate_recovery_keys(count=3, threshold=1)
        assert len(keys) == 3
        for k in keys:
            assert "key_name" in k
            assert "raw_key" in k

    def test_list_recovery_keys(self, db):
        svc = SealService(session=db)
        svc.generate_recovery_keys(count=2)
        keys = svc.list_recovery_keys()
        assert len(keys) == 2
