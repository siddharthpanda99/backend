"""Tests for the v2 secret cipher.

Security properties asserted here, not merely exercised:

- round-trip
- **authentication**: a flipped ciphertext bit, a flipped nonce, a flipped salt,
  a wrong KEK, and a wrong context each raise rather than returning plaintext
- **nonce uniqueness** across many seals under one KEK
- **distinct keys per secret**: the same plaintext under two contexts produces
  different ciphertext, and neither DEK can open the other's blob
- the legacy blob is refused with a reason, not silently misread
- no default KEK exists

These are real crypto properties, so the tests assert the property rather than
just a value. Each was watched failing against a deliberately broken variant.
"""

from __future__ import annotations

import os

import pytest

from common_lib.modules.secrets_manager.core.crypto import (
    BLOB_VERSION,
    KEK_ENV_VAR,
    KEK_VERSION_ENV_VAR,
    LegacyBlobError,
    SealedSecret,
    SecretCryptoError,
    derive_dek,
    load_kek,
    open_sealed,
    seal,
)

KEK = os.urandom(32)
OTHER_KEK = os.urandom(32)
CTX = "secret:db-prod:password"


@pytest.fixture()
def kek(monkeypatch):
    import base64

    monkeypatch.setenv(KEK_ENV_VAR, base64.urlsafe_b64encode(KEK).decode())
    monkeypatch.setenv(KEK_VERSION_ENV_VAR, "1")
    return KEK


# ── round trip ────────────────────────────────────────────────────────────────


def test_round_trip(kek):
    sealed = seal("hunter2", context=CTX, kek=kek, kek_version="1")
    assert open_sealed(sealed, context=CTX, kek=kek) == "hunter2"


def test_serialized_round_trip(kek):
    sealed = seal("s3cret", context=CTX, kek=kek, kek_version="1")
    assert sealed.serialize().startswith(f"{BLOB_VERSION}:")
    assert (
        open_sealed(SealedSecret.parse(sealed.serialize()), context=CTX, kek=kek)
        == "s3cret"
    )


def test_empty_string_round_trips(kek):
    """An empty secret is a legitimate value, not an error."""
    assert (
        open_sealed(
            seal("", context=CTX, kek=kek, kek_version="1"), context=CTX, kek=kek
        )
        == ""
    )


def test_unicode_round_trips(kek):
    v = "pässwörd-日本語-🔐"
    assert (
        open_sealed(
            seal(v, context=CTX, kek=kek, kek_version="1"), context=CTX, kek=kek
        )
        == v
    )


def test_long_plaintext_exceeding_key_length(kek):
    """The old XOR reused key bytes past len(key); GCM has no such limit."""
    v = "A" * 10_000
    assert (
        open_sealed(
            seal(v, context=CTX, kek=kek, kek_version="1"), context=CTX, kek=kek
        )
        == v
    )


# ── authentication: the property the old cipher had none of ──────────────────


def test_flipped_ciphertext_bit_is_detected(kek):
    sealed = seal("hunter2", context=CTX, kek=kek, kek_version="1")
    raw = bytearray(sealed.ciphertext)
    raw[0] ^= 0x01
    tampered = SealedSecret(sealed.salt, sealed.nonce, bytes(raw), sealed.kek_version)
    with pytest.raises(SecretCryptoError, match="Authentication failed"):
        open_sealed(tampered, context=CTX, kek=kek)


def test_flipped_nonce_is_detected(kek):
    sealed = seal("hunter2", context=CTX, kek=kek, kek_version="1")
    bad = bytearray(sealed.nonce)
    bad[0] ^= 0xFF
    with pytest.raises(SecretCryptoError):
        open_sealed(
            SealedSecret(
                sealed.salt, bytes(bad), sealed.ciphertext, sealed.kek_version
            ),
            context=CTX,
            kek=kek,
        )


def test_flipped_salt_is_detected(kek):
    """A changed salt derives a different key, so the tag must not verify."""
    sealed = seal("hunter2", context=CTX, kek=kek, kek_version="1")
    bad = bytearray(sealed.salt)
    bad[0] ^= 0xFF
    with pytest.raises(SecretCryptoError):
        open_sealed(
            SealedSecret(
                bytes(bad), sealed.nonce, sealed.ciphertext, sealed.kek_version
            ),
            context=CTX,
            kek=kek,
        )


def test_aad_binding_is_load_bearing(kek):
    """Isolate the AAD: hold the derived key CONSTANT, vary only the AAD.

    Without this, the AAD binding is untested. The other tests all vary the
    *context*, which changes the derived key, so they would still pass with
    ``aad=b""`` -- the failure would be caught by the wrong key rather than by
    the missing binding. A neuter of the AAD lines turns this test red and
    leaves the context test green, which is what makes it worth having.

    Pinning the DEK removes key-derivation as a variable, so the only remaining
    thing that can reject the blob is the AAD.
    """
    import common_lib.modules.secrets_manager.core.crypto as c

    sealed = seal("hunter2", context=CTX, kek=kek, kek_version="1")
    fixed_dek = derive_dek(kek, sealed.salt, CTX)

    original = c.derive_dek
    try:
        c.derive_dek = lambda *a, **k: fixed_dek

        # Sanity: with the DEK pinned, the untouched blob still opens. If this
        # failed, the assertion below would pass for the wrong reason.
        assert c.open_sealed(sealed, context=CTX, kek=kek) == "hunter2", (
            "pinning the DEK changed the outcome -- this test would prove nothing"
        )

        # Same key, same nonce, same ciphertext; only the recorded KEK version
        # differs. That changes the AAD and nothing else.
        with pytest.raises(SecretCryptoError, match="Authentication failed"):
            c.open_sealed(
                SealedSecret(sealed.salt, sealed.nonce, sealed.ciphertext, "2"),
                context=CTX,
                kek=kek,
            )
    finally:
        c.derive_dek = original


def test_wrong_kek_is_detected(kek):
    sealed = seal("hunter2", context=CTX, kek=kek, kek_version="1")
    with pytest.raises(SecretCryptoError, match="Authentication failed"):
        open_sealed(sealed, context=CTX, kek=OTHER_KEK)


def test_wrong_context_is_detected(kek):
    """A blob cannot be replayed against a different secret identity."""
    sealed = seal("hunter2", context=CTX, kek=kek, kek_version="1")
    with pytest.raises(SecretCryptoError, match="Authentication failed"):
        open_sealed(sealed, context="secret:db-prod:other-password", kek=kek)


def test_wrong_kek_version_is_detected(kek):
    """A blob written under one KEK version must not open under another."""
    sealed = seal("hunter2", context=CTX, kek=kek, kek_version="1")
    # Rewriting the recorded version changes the AAD, so the tag cannot verify.
    forged = SealedSecret(sealed.salt, sealed.nonce, sealed.ciphertext, "2")
    with pytest.raises(SecretCryptoError, match="Authentication failed"):
        open_sealed(forged, context=CTX, kek=kek)


# ── per-secret key separation ─────────────────────────────────────────────────


def test_same_plaintext_under_two_contexts_differs(kek):
    a = seal("identical", context="secret:a", kek=kek, kek_version="1")
    b = (
        seal("identical", context="secret:b", dek_unused=None, kek=kek, kek_version="1")
        if False
        else seal("identical", context="secret:b", kek=kek, kek_version="1")
    )
    assert a.ciphertext != b.ciphertext


def test_distinct_salts_derive_distinct_keys(kek):
    s1, s2 = os.urandom(16), os.urandom(16)
    assert derive_dek(kek, s1, CTX) != derive_dek(kek, s2, CTX)
    assert derive_dek(kek, s1, CTX) == derive_dek(kek, s1, CTX)  # deterministic


def test_a_dek_for_one_secret_cannot_open_another(kek):
    """The property that makes per-secret derivation worth doing."""
    a = seal("secret-a-value", context="secret:a", kek=kek, kek_version="1")
    b = seal("secret-b-value", context="secret:b", kek=kek, kek_version="1")
    # Try to open b's blob using a's derived key material.
    leaked_dek = derive_dek(kek, a.salt, "secret:a")
    forged = SealedSecret(b.salt, b.nonce, b.ciphertext, b.kek_version)
    with pytest.raises(SecretCryptoError):
        # open with a's DEK by monkeypatching derive_dek's output
        import common_lib.modules.secrets_manager.core.crypto as c

        original = c.derive_dek
        try:
            c.derive_dek = lambda *a_, **k_: leaked_dek
            c.open_sealed(forged, context="secret:b", kek=kek)
        finally:
            c.derive_dek = original


# ── nonce hygiene ─────────────────────────────────────────────────────────────


def test_nonces_do_not_repeat(kek):
    """GCM's catastrophic failure is nonce reuse under one key."""
    nonces = {
        seal("x", context="secret:n", kek=kek, kek_version="1").nonce
        for _ in range(500)
    }
    assert len(nonces) == 500
    salts = {
        s.salt
        for s in (
            seal("x", context="secret:s", kek=kek, kek_version="1") for _ in range(500)
        )
    }
    assert len(salts) == 500


# ── the legacy blob is refused, not misread ──────────────────────────────────


@pytest.mark.parametrize(
    "legacy",
    [
        "plaintext-not-encrypted",
        "a:b:c",
        "key1:1:aXY=:dGFn:Y2lwaGVydGV4dA==",
        "",
    ],
)
def test_legacy_blob_is_refused_with_a_reason(legacy):
    with pytest.raises(LegacyBlobError, match=r"(?i)re-encrypt"):
        SealedSecret.parse(legacy)


def test_legacy_error_explains_why_reading_is_unsafe():
    """The message must say why, so an operator does not 'fix' it by guessing."""
    with pytest.raises(LegacyBlobError) as e:
        SealedSecret.parse("key1:1:aXY=:dGFn:Y2lwaGVydGV4dA==")
    m = str(e.value)
    assert "repeating-key XOR" in m
    assert "aes-256-gcm" in m
    assert "Re-encrypt" in m


def test_malformed_v2_blob_raises_not_legacy():
    with pytest.raises(SecretCryptoError, match="Malformed"):
        SealedSecret.parse(f"{BLOB_VERSION}:only:three:fields")


def test_v2_with_bad_base64_raises():
    with pytest.raises(SecretCryptoError, match="base64"):
        SealedSecret.parse(f"{BLOB_VERSION}:1:!!!:!!!:!!!")


# ── no default key, ever ─────────────────────────────────────────────────────


def test_missing_kek_raises_rather_than_defaulting(monkeypatch):
    monkeypatch.delenv(KEK_ENV_VAR, raising=False)
    with pytest.raises(SecretCryptoError, match="not set"):
        load_kek()


def test_short_kek_is_rejected(monkeypatch):
    import base64

    monkeypatch.setenv(KEK_ENV_VAR, base64.urlsafe_b64encode(os.urandom(16)).decode())
    with pytest.raises(SecretCryptoError, match="32 bytes"):
        load_kek()


def test_kek_version_defaults_and_reads_back(monkeypatch, kek):
    monkeypatch.delenv(KEK_VERSION_ENV_VAR, raising=False)
    assert load_kek()[1] == "1"
    monkeypatch.setenv(KEK_VERSION_ENV_VAR, "7")
    assert load_kek()[1] == "7"


def test_empty_context_is_rejected(kek):
    """A secret with no identity cannot be bound, so it must not be sealed."""
    with pytest.raises(SecretCryptoError, match="context"):
        seal("x", context="", kek=kek, kek_version="1")
