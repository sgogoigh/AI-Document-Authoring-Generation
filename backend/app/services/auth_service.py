from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from app.services.audit_service import AuditService
from app.services.google_oauth_service import GoogleIdentity

bearer_scheme = HTTPBearer(auto_error=False)


def _issue_tokens(user: User) -> AuthTokenResponse:
    access_token, expires_in = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


class AuthService:
    """Authentication and user account lifecycle service."""

    @staticmethod
    def register_local_user(db: Session, payload: RegisterRequest) -> AuthTokenResponse:
        email = payload.email.lower().strip()
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        now = datetime.now(timezone.utc)
        user = User(
            email=email,
            full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password),
            auth_provider="local",
            last_login_at=now,
        )
        db.add(user)
        db.flush()

        AuditService.record_event(
            db,
            event_type="AUTH_REGISTER",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            after_state={"email": user.email, "auth_provider": "local"},
        )
        db.commit()
        db.refresh(user)
        return _issue_tokens(user)

    @staticmethod
    def authenticate_local_user(db: Session, payload: LoginRequest) -> AuthTokenResponse:
        email = payload.email.lower().strip()
        user = db.scalar(select(User).where(User.email == email))
        if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
            AuditService.record_event(
                db,
                event_type="AUTH_LOGIN_FAILED",
                entity_type="user",
                entity_id=user.id if user else None,
                user_id=user.id if user else None,
                severity="WARN",
                metadata={"email": email},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")

        user.last_login_at = datetime.now(timezone.utc)
        AuditService.record_event(
            db,
            event_type="AUTH_LOGIN",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            metadata={"auth_provider": user.auth_provider},
        )
        db.commit()
        db.refresh(user)
        return _issue_tokens(user)

    @staticmethod
    def authenticate_google_identity(db: Session, identity: GoogleIdentity) -> AuthTokenResponse:
        user = db.scalar(select(User).where(User.google_sub == identity.sub))
        is_new_user = False

        if not user:
            user = db.scalar(select(User).where(User.email == identity.email))
            if user:
                # Link existing local user to verified Google account
                user.google_sub = identity.sub
                if user.auth_provider == "local":
                    user.auth_provider = "hybrid"
                if identity.avatar_url and not user.avatar_url:
                    user.avatar_url = identity.avatar_url
            else:
                is_new_user = True
                user = User(
                    email=identity.email,
                    full_name=identity.full_name,
                    password_hash=None,
                    auth_provider="google",
                    google_sub=identity.sub,
                    avatar_url=identity.avatar_url,
                )
                db.add(user)
                db.flush()

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")

        user.last_login_at = datetime.now(timezone.utc)
        if identity.avatar_url:
            user.avatar_url = identity.avatar_url

        AuditService.record_event(
            db,
            event_type="AUTH_GOOGLE_LOGIN",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            after_state={
                "email": user.email,
                "auth_provider": user.auth_provider,
                "is_new_user": is_new_user,
            },
        )
        db.commit()
        db.refresh(user)
        return _issue_tokens(user)

    @staticmethod
    def refresh_tokens(db: Session, refresh_token: str) -> AuthTokenResponse:
        try:
            claims = decode_token(refresh_token, expected_type="refresh")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        user = db.get(User, claims["sub"])
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")
        return _issue_tokens(user)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency returning the authenticated active user."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required.",
        )
    try:
        claims = decode_token(credentials.credentials, expected_type="access")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )
    return user
