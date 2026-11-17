from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


def _create_token(
    subject: str,
    email: str,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, email: str) -> tuple[str, int]:
    """Create a signed JWT access token and return (token, expires_in_seconds)."""
    settings = get_settings()
    delta = timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(user_id, email, "access", delta), int(delta.total_seconds())


def create_refresh_token(user_id: str, email: str) -> str:
    """Create a signed JWT refresh token."""
    settings = get_settings()
    delta = timedelta(days=settings.refresh_token_expire_days)
    return _create_token(user_id, email, "refresh", delta)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT token, raising ValueError on invalid or wrong-type tokens."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise ValueError(f"Expected {expected_type} token")
    if not payload.get("sub"):
        raise ValueError("Token missing subject claim")
    return payload
