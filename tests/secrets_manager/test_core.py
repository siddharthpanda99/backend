"""
Tests for Secrets Manager Core submodule (SSOT 05, 06).

Tests key management, encrypt/decrypt, encrypt_value pipeline.
"""

from __future__ import annotations

import pytest
from common_lib.modules.secrets_manager.core.service import EncryptionService


class TestEncryptionService:
    """Test encryption key management and crypto operations."""

    def test_create_key(self, db):
        svc = EncryptionService(session=db)
        result = svc.create_key(
            name="test-key",
            purpose="encrypt",
            algorithm="aes-256-gcm",
            created_by="test-user",
        )
        assert result["name"] == "test-key"
        assert result["version"] == 1

    def test_get_key_by_name(self, db):
        svc = EncryptionService(session=db)
        svc.create_key(name="my-key", purpose="encrypt")
        key = svc.get_key(name="my-key")
        assert key is not None
        assert key.name == "my-key"
        assert key.purpose == "encrypt"

    def test_get_key_by_id(self, db):
        svc = EncryptionService(session=db)
        result = svc.create_key(name="id-lookup", purpose="encrypt")
        key = svc.get_key(key_id=result["id"])
        assert key is not None
        assert key.name == "id-lookup"

    def test_get_key_not_found(self, db):
        svc = EncryptionService(session=db)
        assert svc.get_key(name="nonexistent") is None
        assert svc.get_key(key_id="bad-id") is None

    def test_list_keys(self, db):
        svc = EncryptionService(session=db)
        svc.create_key(name="key-a", purpose="encrypt")
        svc.create_key(name="key-b", purpose="sign")
        svc.create_key(name="key-c", purpose="encrypt")

        all_keys = svc.list_keys()
        assert len(all_keys) == 3

        encrypt_keys = svc.list_keys(purpose="encrypt")
        assert len(encrypt_keys) == 2

    def test_rotate_key(self, db):
        svc = EncryptionService(session=db)
        svc.create_key(name="rotate-me", purpose="encrypt", auto_rotate=True)

        result = svc.rotate_key(name="rotate-me")
        assert result is not None
        assert result["version"] == 2

    def test_rotate_key_not_found(self, db):
        svc = EncryptionService(session=db)
        assert svc.rotate_key(name="nonexistent") is None

    def test_encrypt_decrypt_roundtrip(self, db):
        svc = EncryptionService(session=db)
        svc.create_key(name="crypto-key", purpose="encrypt")

        blob = svc.encrypt("hello-world", key_name="crypto-key")
        assert blob.ciphertext is not None
        assert blob.key_id is not None
        assert blob.algorithm == "aes-256-gcm"

        decrypted = svc.decrypt(blob)
        assert decrypted == "hello-world"

    def test_encrypt_decrypt_empty_string(self, db):
        svc = EncryptionService(session=db)
        svc.create_key(name="empty-key", purpose="encrypt")

        blob = svc.encrypt("", key_name="empty-key")
        decrypted = svc.decrypt(blob)
        assert decrypted == ""

    def test_encrypt_decrypt_special_chars(self, db):
        svc = EncryptionService(session=db)
        svc.create_key(name="special-key", purpose="encrypt")

        plaintext = "special!@#$%^&*()_+-=[]{}\\|;':\",./<>?`~"
        blob = svc.encrypt(plaintext, key_name="special-key")
        decrypted = svc.decrypt(blob)
        assert decrypted == plaintext

    def test_encrypt_value_pipeline(self, db):
        """Test the encrypt_value -> decrypt_value pipeline (used by VaultService)."""
        svc = EncryptionService(session=db)
        svc.create_key(name="pipeline-key", purpose="encrypt")

        encrypted = svc.encrypt_value("pipeline-test", key_name="pipeline-key")
        assert isinstance(encrypted, str)
        assert ":" in encrypted  # key_id:version:iv:tag:ciphertext

        decrypted = svc.decrypt_value(encrypted)
        assert decrypted == "pipeline-test"

    def test_decrypt_value_legacy_fallback(self, db):
        """decrypt_value should return as-is for non-blob strings (legacy support)."""
        svc = EncryptionService(session=db)
        result = svc.decrypt_value("plain-text-fallback")
        assert result == "plain-text-fallback"

    def test_encrypt_with_different_keys_produce_different_results(self, db):
        svc = EncryptionService(session=db)
        svc.create_key(name="key-1", purpose="encrypt")
        svc.create_key(name="key-2", purpose="encrypt")

        blob1 = svc.encrypt("same-data", key_name="key-1")
        blob2 = svc.encrypt("same-data", key_name="key-2")

        assert blob1.ciphertext != blob2.ciphertext

    def test_encrypt_missing_key_raises(self, db):
        svc = EncryptionService(session=db)
        with pytest.raises(ValueError, match="Encryption key not found"):
            svc.encrypt("data", key_name="missing-key")
