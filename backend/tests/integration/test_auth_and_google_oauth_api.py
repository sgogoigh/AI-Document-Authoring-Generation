from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.models.audit import AuditEventLog
from app.models.user import User


def _generate_rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def test_local_register_login_refresh_and_me(client: TestClient, db_session):
    # Register
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "Alice@Example.com", "full_name": "Alice Smith", "password": "StrongPassword123!"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["auth_provider"] == "local"
    assert data["access_token"]
    assert data["refresh_token"]

    # Duplicate email returns 409
    dup = client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "full_name": "Alice", "password": "StrongPassword123!"},
    )
    assert dup.status_code == 409

    # Bad password returns 401 and logs WARN audit event
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    warn_event = db_session.scalar(
        select(AuditEventLog).where(AuditEventLog.event_type == "AUTH_LOGIN_FAILED")
    )
    assert warn_event is not None
    assert warn_event.severity == "WARN"

    # Valid login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "StrongPassword123!"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()

    # /me succeeds with access token, fails without or with refresh token
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "alice@example.com"

    no_auth = client.get("/api/v1/auth/me")
    assert no_auth.status_code == 401

    wrong_type = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert wrong_type.status_code == 401

    # Refresh flow
    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert ref_res.status_code == 200
    assert ref_res.json()["access_token"]


def test_google_oauth_url_and_id_token_cryptographic_verification(
    client: TestClient, db_session, monkeypatch: pytest.MonkeyPatch
):
    client_id = "test-google-client-id.apps.googleusercontent.com"
    monkeypatch.setenv("GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-google-secret")
    get_settings.cache_clear()

    try:
        # 1. Authorization URL builder
        url_res = client.get("/api/v1/auth/google/url", params={"state": "csrf-xyz"})
        assert url_res.status_code == 200
        url_data = url_res.json()
        assert "accounts.google.com/o/oauth2/v2/auth" in url_data["authorize_url"]
        assert client_id in url_data["authorize_url"]
        assert "state=csrf-xyz" in url_data["authorize_url"]

        # 2. Sign a real RSA JWT ID token and verify via google.auth RSA verification
        private_pem, public_pem = _generate_rsa_keypair()
        now = datetime.now(timezone.utc)
        valid_id_token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": client_id,
                "sub": "google-sub-9991",
                "email": "bob.google@example.com",
                "email_verified": True,
                "name": "Bob Google",
                "picture": "https://example.com/bob.png",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=10)).timestamp()),
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": "test-key-1"},
        )

        # Patch Google's public cert lookup so verify_oauth2_token validates the real RSA signature
        from google.oauth2 import id_token as google_id_token_mod

        monkeypatch.setattr(
            google_id_token_mod,
            "_fetch_certs",
            lambda _request, _certs_url: {"test-key-1": public_pem.decode("utf-8")},
        )

        g_res = client.post("/api/v1/auth/google", json={"id_token": valid_id_token})
        assert g_res.status_code == 200
        g_data = g_res.json()
        assert g_data["user"]["email"] == "bob.google@example.com"
        assert g_data["user"]["auth_provider"] == "google"
        assert g_data["user"]["avatar_url"] == "https://example.com/bob.png"

        # 3. Wrong audience must be rejected (401)
        wrong_aud_token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": "wrong-client-id",
                "sub": "google-sub-9991",
                "email": "bob.google@example.com",
                "email_verified": True,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=10)).timestamp()),
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": "test-key-1"},
        )
        bad_aud = client.post("/api/v1/auth/google", json={"id_token": wrong_aud_token})
        assert bad_aud.status_code == 401

        # 4. Unverified email must be rejected (401)
        unverified_token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": client_id,
                "sub": "google-sub-unverified",
                "email": "unverified@example.com",
                "email_verified": False,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=10)).timestamp()),
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": "test-key-1"},
        )
        unver_res = client.post("/api/v1/auth/google", json={"id_token": unverified_token})
        assert unver_res.status_code == 401

        # 5. Existing local user with same verified email gets linked as "hybrid"
        local_reg = client.post(
            "/api/v1/auth/register",
            json={"email": "hybrid@example.com", "full_name": "Hybrid User", "password": "Password123!"},
        )
        assert local_reg.status_code == 201

        hybrid_id_token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": client_id,
                "sub": "google-sub-hybrid",
                "email": "hybrid@example.com",
                "email_verified": True,
                "name": "Hybrid User",
                "picture": "https://example.com/hybrid.png",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=10)).timestamp()),
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": "test-key-1"},
        )
        link_res = client.post("/api/v1/auth/google", json={"id_token": hybrid_id_token})
        assert link_res.status_code == 200
        assert link_res.json()["user"]["auth_provider"] == "hybrid"

        db_user = db_session.scalar(select(User).where(User.email == "hybrid@example.com"))
        assert db_user is not None
        assert db_user.google_sub == "google-sub-hybrid"

        # 6. OAuth2 Authorization Code callback exchange
        mock_http_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id_token": valid_id_token, "access_token": "goog-access"}
        mock_http_client.__enter__.return_value.post.return_value = mock_resp

        import app.services.google_oauth_service as oauth_mod

        monkeypatch.setattr(oauth_mod.httpx, "Client", lambda **_kwargs: mock_http_client)
        cb_res = client.post("/api/v1/auth/google/callback", json={"code": "auth-code-12345"})
        assert cb_res.status_code == 200
        assert cb_res.json()["user"]["email"] == "bob.google@example.com"

        audit_google = db_session.scalars(
            select(AuditEventLog).where(AuditEventLog.event_type == "AUTH_GOOGLE_LOGIN")
        ).all()
        assert len(audit_google) == 3
    finally:
        get_settings.cache_clear()
