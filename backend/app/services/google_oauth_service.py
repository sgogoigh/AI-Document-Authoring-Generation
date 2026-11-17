from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
ALLOWED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    full_name: str
    avatar_url: str | None
    email_verified: bool


def build_google_authorize_url(state: str | None = None) -> dict:
    """Return the Google OAuth2 authorization URL for frontend redirect."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on the server (missing GOOGLE_CLIENT_ID).",
        )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    if state:
        params["state"] = state
    return {
        "authorize_url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}",
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
    }


def verify_google_id_token(token_str: str) -> GoogleIdentity:
    """Verify a Google OIDC ID token and extract identity claims."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on the server (missing GOOGLE_CLIENT_ID).",
        )
    try:
        claims = google_id_token.verify_oauth2_token(
            token_str,
            google_requests.Request(),
            audience=settings.google_client_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {exc}",
        ) from exc

    if claims.get("iss") not in ALLOWED_ISSUERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token issuer",
        )
    if not claims.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is not verified",
        )

    email = claims.get("email", "").lower().strip()
    sub = claims.get("sub", "").strip()
    if not email or not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token missing required identity claims",
        )

    return GoogleIdentity(
        sub=sub,
        email=email,
        full_name=claims.get("name") or email.split("@")[0],
        avatar_url=claims.get("picture"),
        email_verified=True,
    )


def exchange_google_auth_code(code: str, redirect_uri: str | None = None) -> GoogleIdentity:
    """Exchange a Google OAuth2 authorization code for tokens and verify the ID token."""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth code flow requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )

    effective_redirect = redirect_uri or settings.google_redirect_uri
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": effective_redirect,
                    "grant_type": "authorization_code",
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to contact Google token endpoint: {exc}",
        ) from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authorization code exchange failed",
        )

    payload = resp.json()
    raw_id_token = payload.get("id_token")
    if not raw_id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token response missing id_token",
        )
    return verify_google_id_token(raw_id_token)
