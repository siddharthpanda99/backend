"""
Tests for Secrets Manager Vault submodule (SSOT 01).

Tests CRUD, versioning, listing, metadata, and edge cases.
"""
from __future__ import annotations

import pytest
from common_lib.modules.secrets_manager.vault.service import VaultService


class TestVaultService:
    """Test secret CRUD and versioning."""

    def test_create_secret(self, db):
        svc = VaultService(session=db)
        result = svc.create_secret(
            name="test-secret",
            value="my-secret-value",
            path="/test",
            description="A test secret",
            tags=["test", "demo"],
            created_by="test-user",
        )
        assert result["name"] == "test-secret"
        assert result["version"] == 1
        assert result["path"] == "/test"
        assert "id" in result

    def test_create_secret_duplicate_name(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="dup-secret", value="value1")
        result = svc.create_secret(name="dup-secret", value="value2")
        assert "error" in result
        assert "already exists" in result["error"]

    def test_read_secret(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="read-test", value="secret-value")
        result = svc.read_secret(name="read-test")
        assert result is not None
        assert result["name"] == "read-test"
        assert result["value"] == "secret-value"
        assert result["version"] == 1

    def test_read_secret_not_found(self, db):
        svc = VaultService(session=db)
        result = svc.read_secret(name="nonexistent")
        assert result is None

    def test_read_secret_specific_version(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="versioned-test", value="v1")
        svc.update_secret(name="versioned-test", value="v2")
        svc.update_secret(name="versioned-test", value="v3")

        v1 = svc.read_secret(name="versioned-test", version=1)
        v3 = svc.read_secret(name="versioned-test")  # latest

        assert v1["value"] == "v1"
        assert v1["version"] == 1
        assert v3["value"] == "v3"
        assert v3["version"] == 3

    def test_update_secret_creates_new_version(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="update-test", value="original")
        result = svc.update_secret(name="update-test", value="updated")
        assert result["version"] == 2

        read = svc.read_secret(name="update-test")
        assert read["value"] == "updated"
        assert read["version"] == 2

    def test_update_secret_not_found(self, db):
        svc = VaultService(session=db)
        result = svc.update_secret(name="nonexistent", value="new-value")
        assert result is None

    def test_list_secrets(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="list-a", value="a", path="/alpha")
        svc.create_secret(name="list-b", value="b", path="/beta")
        svc.create_secret(name="list-c", value="c", path="/alpha")

        result = svc.list_secrets()
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_list_secrets_with_path_filter(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="filter-a", value="a", path="/alpha")
        svc.create_secret(name="filter-b", value="b", path="/beta")

        result = svc.list_secrets(path="/alpha")
        assert result["total"] == 1
        assert result["items"][0]["name"] == "filter-a"

    def test_list_secrets_pagination(self, db):
        svc = VaultService(session=db)
        for i in range(5):
            svc.create_secret(name=f"page-{i}", value=str(i))

        result = svc.list_secrets(limit=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_get_secret_info(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="info-test", value="val", description="info desc",
                          tags=["info"], owner="owner1", ttl_seconds=3600)
        info = svc.get_secret_info(name="info-test")
        assert info["name"] == "info-test"
        assert info["description"] == "info desc"
        assert info["tags"] == ["info"]
        assert info["owner"] == "owner1"
        assert info["ttl_seconds"] == 3600
        assert info["stats"]["total_versions"] == 1

    def test_get_secret_info_not_found(self, db):
        svc = VaultService(session=db)
        result = svc.get_secret_info(name="nonexistent")
        assert result is None

    def test_delete_secret_soft(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="delete-test", value="val")
        assert svc.delete_secret(name="delete-test") is True
        # Should not be readable
        assert svc.read_secret(name="delete-test") is None

    def test_delete_secret_not_found(self, db):
        svc = VaultService(session=db)
        assert svc.delete_secret(name="nonexistent") is False

    def test_hard_delete_secret(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="hard-delete", value="val")
        assert svc.hard_delete_secret(name="hard-delete") is True
        assert svc.read_secret(name="hard-delete") is None
        assert svc.get_secret_info(name="hard-delete") is None

    def test_list_versions(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="versions", value="v1")
        svc.update_secret(name="versions", value="v2")
        svc.update_secret(name="versions", value="v3")

        versions = svc.list_versions(name="versions")
        assert versions is not None
        assert len(versions) == 3
        assert versions[0]["version"] == 3  # Ordered desc
        assert versions[2]["version"] == 1

    def test_destroy_version(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="destroy-version", value="v1")
        svc.update_secret(name="destroy-version", value="v2")

        assert svc.destroy_version(name="destroy-version", version=1) is True
        versions = svc.list_versions(name="destroy-version", include_destroyed=False)
        assert len(versions) == 1
        assert versions[0]["version"] == 2

    def test_max_versions_enforcement(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="max-versions", value="v1", max_versions=2)
        svc.update_secret(name="max-versions", value="v2")
        svc.update_secret(name="max-versions", value="v3")

        # Version 1 should be destroyed
        versions = svc.list_versions(name="max-versions", include_destroyed=True)
        destroyed = [v for v in versions if v["destroyed"]]
        assert len(destroyed) == 1

    def test_secret_with_ttl(self, db):
        svc = VaultService(session=db)
        svc.create_secret(name="ttl-secret", value="val", ttl_seconds=60)
        info = svc.get_secret_info(name="ttl-secret")
        assert info["ttl_seconds"] == 60
        assert info["expires_at"] is not None

    def test_encryption_decryption_roundtrip(self, db):
        svc = VaultService(session=db)
        # Test that _encrypt and _decrypt work correctly
        plaintext = "sensitive-data-123!@#"
        cipher = svc._encrypt(plaintext)
        assert cipher != plaintext
        decrypted = svc._decrypt(cipher)
        assert decrypted == plaintext
