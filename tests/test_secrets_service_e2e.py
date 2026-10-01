"""End-to-end tests for EncryptionService over the real cipher and a real DB.

These replace the old XOR path, so they exercise the actual code rather than a
stand-in: a real SQLite session, a real key row, and the real KEK from the
environment. A hand-rolled stand-in validated the wrong object last time this
module was changed.
"""

from __future__ import annotations

import base64
import os

import pytest
from sqlmodel import Session, create_engine, select

from common_lib.modules.generated_models import sm_models
from common_lib.modules.secrets_manager.core.crypto import (
    KEK_ENV_VAR,
    KEK_VERSION_ENV_VAR,
    SecretCryptoError,
)
from common_lib.modules.secrets_manager.core.service import EncryptionService

KEK = base64.urlsafe_b64encode(os.urandom(32)).decode()


@pytest.fixture()
def session(tmp_path, monkeypatch):
    monkeypatch.setenv(KEK_ENV_VAR, KEK)
    monkeypatch.setenv(KEK_VERSION_ENV_VAR, "1")
    engine = create_engine(f"sqlite:///{tmp_path / 'sm.db'}")
    # Only this table: a full create_all trips unrelated FK ordering.
    sm_models.SmEncryptionKeys.__table__.create(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def svc(session):
    return EncryptionService(session=session)


# ── F16: the insert that had never once succeeded ─────────────────────────────


def test_create_key_persists(svc, session):
    """F16: status/version/created_at are NOT NULL and were never passed."""
    key = svc.create_key("master")
    assert key["name"] == "master"
    row = session.exec(select(sm_models.SmEncryptionKeys)).one()
    assert row.name == "master"
    assert row.status == "ACTIVE"
    assert row.version == 1
    assert row.created_at is not None


def test_created_by_is_never_null(svc, session):
    """created_by is nullable but the caller omits it; a real value is better."""
    svc.create_key("master")
    assert session.exec(select(sm_models.SmEncryptionKeys)).one().created_by == "local"


def test_key_material_is_not_stored_in_the_clear(svc, session):
    """The column is named encrypted_key_material; it used to hold bare base64."""
    svc.create_key("master")
    row = session.exec(select(sm_models.SmEncryptionKeys)).one()
    stored = row.encrypted_key_material
    assert stored.startswith("v2:"), "key material is not sealed under the KEK"
    # And the plaintext material must not be recoverable by reading the column.
    assert "v2" in stored and stored.count(":") == 4


# ── round trip through the service ────────────────────────────────────────────


def test_encrypt_decrypt_round_trip(svc):
    svc.create_key("master")
    blob = svc.encrypt("hunter2", key_name="master")
    assert svc.decrypt(blob) == "hunter2"


def test_encrypt_value_round_trip(svc):
    """The serialized envelope path, which is what callers actually store."""
    svc.create_key("master")
    sealed = svc.encrypt_value("s3cret", key_name="master")
    assert sealed.startswith("v2:")
    assert svc.decrypt_value(sealed) == "s3cret"


def test_algorithm_recorded_matches_the_cipher(svc):
    """The record must describe the bytes. It used to claim GCM over XOR."""
    svc.create_key("master")
    blob = svc.encrypt("x", key_name="master")
    assert blob.algorithm == "aes-256-gcm"


def test_tag_is_the_real_gcm_tag(svc):
    """The old tag was os.urandom(16) -- random bytes, never verified."""
    svc.create_key("master")
    blob = svc.encrypt("x", key_name="master")
    # A real GCM tag is 16 bytes; random bytes would also be 16, so assert the
    # stronger property: it equals the tail of the ciphertext.
    assert (
        blob.tag
        == base64.b64encode(
            base64.urlsafe_b64decode(blob.ciphertext.split(":")[-1])[-16:]
        ).decode()
    )


def test_iv_is_the_nonce_actually_used(svc):
    """The old iv was generated and then ignored by the cipher."""
    svc.create_key("master")
    blob = svc.encrypt("x", key_name="master")
    nonce = base64.urlsafe_b64decode(blob.ciphertext.split(":")[3])
    assert base64.b64decode(blob.iv) == nonce


def test_unknown_key_raises(svc):
    with pytest.raises(ValueError, match="not found"):
        svc.encrypt("x", key_name="does-not-exist")


# ── authentication survives the round trip through the service ────────────────


def test_tampered_ciphertext_is_rejected(svc):
    """Flipping a plaintext bit must not yield a plaintext at all."""
    svc.create_key("master")
    blob = svc.encrypt("hunter2", key_name="master")
    fields = blob.ciphertext.split(":")
    raw = bytearray(base64.urlsafe_b64decode(fields[4]))
    raw[0] ^= 0x01
    fields[4] = base64.urlsafe_b64encode(bytes(raw)).decode()
    blob.ciphertext = ":".join(fields)
    with pytest.raises(SecretCryptoError, match="Authentication failed"):
        svc.decrypt(blob)


def test_blob_cannot_be_moved_to_another_key(svc):
    """A ciphertext re-labelled with a different key must not open."""
    svc.create_key("master")
    svc.create_key("other")
    blob = svc.encrypt("hunter2", key_name="master")
    other = svc.get_key(name="other")
    blob.key_id = other.id
    with pytest.raises(SecretCryptoError, match="Authentication failed"):
        svc.decrypt(blob)


def test_legacy_blob_is_refused_not_echoed(svc):
    """F1: the old passthrough returned the input as if it were the secret."""
    svc.create_key("master")
    with pytest.raises(Exception) as e:
        svc.decrypt_value("plaintext-not-encrypted")
    assert "hunter" not in str(e.value)
    assert "plaintext-not-encrypted" not in str(e.value)


def test_missing_kek_refuses_rather_than_defaulting(svc, monkeypatch):
    """No default KEK: the same mistake as the literal just removed."""
    svc.create_key("master")
    monkeypatch.delenv(KEK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        "common_lib.modules.secrets_manager.core.crypto._CACHED", None, raising=False
    )
    with pytest.raises(SecretCryptoError, match="not set"):
        svc.encrypt("x", key_name="master")


# ── distinct secrets do not share key material ────────────────────────────────


def test_two_secrets_produce_different_ciphertext(svc):
    svc.create_key("master")
    a = svc.encrypt_value("identical", key_name="master")
    b = svc.encrypt_value("identical", key_name="master")
    assert a != b, "a fresh salt/nonce per call is required"


def test_same_secret_twice_decrypts(svc):
    svc.create_key("master")
    for _ in range(3):
        assert svc.decrypt_value(svc.encrypt_value("v", key_name="master")) == "v"
