"""Regression tests: three file_browser handlers reported success on failure.

1. `DELETE /signed/{token}` returned success=True unconditionally.
2. `revoke_signed_url()` itself returned a hardcoded True.
3. `POST /files/{id}/encrypt` and `/decrypt` returned HTTP 200 with an
   `{"error": ...}` body, because the service signals refusal with a truthy
   dict and the handler only checked `if not result`.

Offline: the handlers are called directly with the common_lib service functions
monkeypatched, so no database and no server are involved.
"""

import pytest
from fastapi import HTTPException

from app.modules import file_browser as fb


class TestRevokeSignedUrlHandler:
    async def test_reports_404_when_nothing_was_revoked(self, monkeypatch):
        monkeypatch.setattr(fb, "revoke_signed_url", lambda token: False)
        with pytest.raises(HTTPException) as exc:
            await fb.revoke_signed_url_handler("no-such-token")
        assert exc.value.status_code == 404

    async def test_reports_success_when_a_row_was_deleted(self, monkeypatch):
        monkeypatch.setattr(fb, "revoke_signed_url", lambda token: True)
        response = await fb.revoke_signed_url_handler("live-token")
        assert response.success is True


class TestEncryptDecryptHandlersSurfaceErrors:
    async def test_encrypt_error_becomes_409_not_200(self, monkeypatch):
        monkeypatch.setattr(
            "common_lib.modules.file_system.service.encrypt_file",
            lambda file_id: {"error": "File already encrypted"},
        )
        with pytest.raises(HTTPException) as exc:
            await fb.encrypt_file_handler("abc")
        assert exc.value.status_code == 409
        assert "already encrypted" in exc.value.detail

    async def test_encrypt_success_still_passes_through(self, monkeypatch):
        monkeypatch.setattr(
            "common_lib.modules.file_system.service.encrypt_file",
            lambda file_id: {"file_id": file_id, "encrypted": True},
        )
        result = await fb.encrypt_file_handler("abc")
        assert result["encrypted"] is True

    async def test_encrypt_missing_file_still_404(self, monkeypatch):
        monkeypatch.setattr(
            "common_lib.modules.file_system.service.encrypt_file", lambda file_id: None
        )
        with pytest.raises(HTTPException) as exc:
            await fb.encrypt_file_handler("abc")
        assert exc.value.status_code == 404

    async def test_decrypt_failure_becomes_422(self, monkeypatch):
        monkeypatch.setattr(
            "common_lib.modules.file_system.service.decrypt_file",
            lambda file_id: {"error": "Decryption failed"},
        )
        with pytest.raises(HTTPException) as exc:
            await fb.decrypt_file_handler("abc")
        assert exc.value.status_code == 422

    async def test_decrypt_not_encrypted_becomes_409(self, monkeypatch):
        monkeypatch.setattr(
            "common_lib.modules.file_system.service.decrypt_file",
            lambda file_id: {"error": "File not encrypted"},
        )
        with pytest.raises(HTTPException) as exc:
            await fb.decrypt_file_handler("abc")
        assert exc.value.status_code == 409

    async def test_decrypt_success_still_passes_through(self, monkeypatch):
        monkeypatch.setattr(
            "common_lib.modules.file_system.service.decrypt_file",
            lambda file_id: {"file_id": file_id, "decrypted": True},
        )
        result = await fb.decrypt_file_handler("abc")
        assert result["decrypted"] is True


class TestRevokeSignedUrlServiceRowcount:
    """The service itself must not claim success when no row matched."""

    def test_returns_false_when_delete_matched_nothing(self, tmp_path, monkeypatch):
        import sqlite3

        from sqlalchemy import create_engine, event

        from common_lib.modules.file_system.services import signed_url_service as sus

        dbfile = tmp_path / "s.db"
        sqlite3.connect(dbfile).close()
        engine = create_engine(f"sqlite:///{dbfile}")

        @event.listens_for(engine, "connect")
        def _attach(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("ATTACH DATABASE ':memory:' AS system")
            cur.execute(
                "CREATE TABLE IF NOT EXISTS system.signed_urls ("
                "token TEXT, file_id TEXT, user_id TEXT, expires_at INTEGER,"
                " created_at TIMESTAMP)"
            )
            cur.close()

        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

        monkeypatch.setattr(sus, "_engine", lambda: engine)

        assert sus.revoke_signed_url("never-existed") is False

    def test_returns_true_when_a_row_was_deleted(self, tmp_path, monkeypatch):
        import sqlite3

        from sqlalchemy import create_engine, event, text as sa_text
        from sqlmodel import Session

        from common_lib.modules.file_system.services import signed_url_service as sus

        dbfile = tmp_path / "s.db"
        sqlite3.connect(dbfile).close()
        engine = create_engine(f"sqlite:///{dbfile}")

        @event.listens_for(engine, "connect")
        def _attach(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("ATTACH DATABASE ':memory:' AS system")
            cur.execute(
                "CREATE TABLE IF NOT EXISTS system.signed_urls ("
                "token TEXT, file_id TEXT, user_id TEXT, expires_at INTEGER,"
                " created_at TIMESTAMP)"
            )
            cur.close()

        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

        with Session(engine) as db:
            db.execute(
                sa_text(
                    "INSERT INTO system.signed_urls (token, file_id, expires_at)"
                    " VALUES ('live', 'f1', 99999999999)"
                )
            )
            db.commit()

        monkeypatch.setattr(sus, "_engine", lambda: engine)

        assert sus.revoke_signed_url("live") is True
        assert sus.revoke_signed_url("live") is False, (
            "second revoke must not claim success"
        )
