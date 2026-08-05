"""
Tests for Secrets Manager SSH submodule (SSOT 08).

Tests key pair CRUD, target registration, OTP lifecycle, certificate management.
"""
from __future__ import annotations

import pytest
from common_lib.modules.secrets_manager.ssh.service import SshService


class TestSshService:
    """Test SSH key management, OTP, and certificates."""

    def test_create_key_pair(self, db):
        svc = SshService(session=db)
        result = svc.create_key_pair(name="deploy-key", key_type="ed25519")
        assert result["name"] == "deploy-key"
        assert "fingerprint" in result

    def test_list_key_pairs(self, db):
        svc = SshService(session=db)
        svc.create_key_pair(name="kp-1")
        svc.create_key_pair(name="kp-2")
        pairs = svc.list_key_pairs()
        assert len(pairs) >= 2
        names = [p["name"] for p in pairs]
        assert "kp-1" in names
        assert "kp-2" in names

    def test_revoke_key_pair(self, db):
        svc = SshService(session=db)
        svc.create_key_pair(name="revoke-kp")
        assert svc.revoke_key_pair(name="revoke-kp") is True
        pairs = svc.list_key_pairs(status="revoked")
        assert len(pairs) >= 1

    def test_revoke_key_pair_not_found(self, db):
        svc = SshService(session=db)
        assert svc.revoke_key_pair(name="nonexistent") is False

    def test_register_target(self, db):
        svc = SshService(session=db)
        result = svc.register_target(hostname="bastion.example.com", port=22)
        assert result["hostname"] == "bastion.example.com"
        assert "id" in result

    def test_list_targets(self, db):
        svc = SshService(session=db)
        svc.register_target(hostname="server1.example.com")
        svc.register_target(hostname="server2.example.com")
        targets = svc.list_targets()
        assert len(targets) >= 2

    def test_generate_otp(self, db):
        svc = SshService(session=db)
        svc.register_target(hostname="jumpbox.example.com")
        result = svc.generate_otp(target_hostname="jumpbox.example.com")
        assert "otp_code" in result
        assert "valid_until" in result

    def test_generate_otp_target_not_found(self, db):
        svc = SshService(session=db)
        result = svc.generate_otp(target_hostname="nonexistent")
        assert "error" in result

    def test_validate_otp_valid(self, db):
        svc = SshService(session=db)
        svc.register_target(hostname="gateway.example.com")
        otp = svc.generate_otp(target_hostname="gateway.example.com")
        assert svc.validate_otp(otp_code=otp["otp_code"], target_hostname="gateway.example.com") is True

    def test_validate_otp_one_time_use(self, db):
        """OTP should only be valid once."""
        svc = SshService(session=db)
        svc.register_target(hostname="one-time.example.com")
        otp = svc.generate_otp(target_hostname="one-time.example.com")
        assert svc.validate_otp(otp_code=otp["otp_code"], target_hostname="one-time.example.com") is True
        assert svc.validate_otp(otp_code=otp["otp_code"], target_hostname="one-time.example.com") is False

    def test_issue_ssh_certificate(self, db):
        svc = SshService(session=db)
        svc.create_key_pair(name="ssh-ca", key_type="ed25519")
        result = svc.issue_certificate(
            key_id="user@example.com",
            ca_key_pair_name="ssh-ca",
            principals=["ubuntu", "admin"],
        )
        assert "serial_number" in result
        assert result["key_id"] == "user@example.com"

    def test_issue_ssh_certificate_ca_not_found(self, db):
        svc = SshService(session=db)
        result = svc.issue_certificate(key_id="user@test.com", ca_key_pair_name="nonexistent-ca")
        assert "error" in result

    def test_revoke_ssh_certificate(self, db):
        svc = SshService(session=db)
        svc.create_key_pair(name="revoke-ca", key_type="ed25519")
        cert = svc.issue_certificate(key_id="old-user", ca_key_pair_name="revoke-ca")
        assert svc.revoke_certificate(serial_number=cert["serial_number"]) is True

    def test_revoke_ssh_certificate_not_found(self, db):
        svc = SshService(session=db)
        assert svc.revoke_certificate(serial_number="NONEXISTENT") is False
