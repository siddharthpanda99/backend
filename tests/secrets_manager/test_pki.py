"""
Tests for Secrets Manager PKI submodule (SSOT 07).

Tests CA management, certificate issuance, revocation, expiry monitoring.
"""

from __future__ import annotations

from common_lib.modules.secrets_manager.pki.service import CertificateService


class TestCertificateService:
    """Test PKI certificate lifecycle management."""

    def test_create_ca(self, db):
        svc = CertificateService(session=db)
        result = svc.create_ca(
            name="internal-ca",
            type="internal",
            allowed_domains="*.example.com",
        )
        assert result["name"] == "internal-ca"
        assert "id" in result

    def test_list_cas(self, db):
        svc = CertificateService(session=db)
        svc.create_ca(name="ca-1", type="internal")
        svc.create_ca(name="ca-2", type="external")
        cas = svc.list_cas()
        assert len(cas) >= 2
        names = [c["name"] for c in cas]
        assert "ca-1" in names
        assert "ca-2" in names

    def test_issue_certificate(self, db):
        svc = CertificateService(session=db)
        svc.create_ca(
            name="issuer-ca", type="internal", allowed_domains="*.example.com"
        )
        result = svc.issue_certificate(
            common_name="api.example.com",
            ca_name="issuer-ca",
            ttl_seconds=86400,
            subject_alt_names=["api.example.com", "api-v2.example.com"],
        )
        assert result["common_name"] == "api.example.com"
        assert "serial_number" in result
        assert "expires_at" in result

    def test_issue_certificate_ca_not_found(self, db):
        svc = CertificateService(session=db)
        result = svc.issue_certificate(common_name="test.com", ca_name="nonexistent-ca")
        assert "error" in result
        assert "not found" in result["error"]

    def test_list_certificates(self, db):
        svc = CertificateService(session=db)
        svc.create_ca(name="list-ca", type="internal")
        svc.issue_certificate(common_name="srv1.example.com", ca_name="list-ca")
        svc.issue_certificate(common_name="srv2.example.com", ca_name="list-ca")

        certs = svc.list_certificates(ca_name="list-ca")
        assert len(certs) >= 2
        names = [c["common_name"] for c in certs]
        assert "srv1.example.com" in names

    def test_list_certificates_filter_by_status(self, db):
        svc = CertificateService(session=db)
        svc.create_ca(name="status-ca", type="internal")
        svc.issue_certificate(
            common_name="keep-active.example.com", ca_name="status-ca"
        )
        cert2 = svc.issue_certificate(
            common_name="revoke-me.example.com", ca_name="status-ca"
        )
        svc.revoke_certificate(serial_number=cert2["serial_number"])

        all_certs = svc.list_certificates(ca_name="status-ca")
        active = [c for c in all_certs if c["status"] == "active"]
        revoked = [c for c in all_certs if c["status"] == "revoked"]
        assert len(active) >= 1
        assert len(revoked) >= 1

    def test_revoke_certificate(self, db):
        svc = CertificateService(session=db)
        svc.create_ca(name="revoke-ca", type="internal")
        cert = svc.issue_certificate(
            common_name="revoke-me.example.com", ca_name="revoke-ca"
        )

        assert (
            svc.revoke_certificate(
                serial_number=cert["serial_number"], reason="compromised"
            )
            is True
        )

    def test_revoke_certificate_not_found(self, db):
        svc = CertificateService(session=db)
        assert svc.revoke_certificate(serial_number="NONEXISTENT") is False

    def test_get_expiring(self, db):
        svc = CertificateService(session=db)
        svc.create_ca(name="expiry-ca", type="internal")
        svc.issue_certificate(
            common_name="short.example.com", ca_name="expiry-ca", ttl_seconds=1
        )
        svc.issue_certificate(
            common_name="long.example.com", ca_name="expiry-ca", ttl_seconds=86400
        )

        import time

        time.sleep(1.1)

        expiring = svc.get_expiring(days=30)
        expiring_names = [c["common_name"] for c in expiring]
        assert "short.example.com" in expiring_names
