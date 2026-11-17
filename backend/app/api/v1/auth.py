from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthTokenResponse,
    GoogleCodeLoginRequest,
    GoogleTokenLoginRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService, get_current_user
from app.services.google_oauth_service import (
    build_google_authorize_url,
    exchange_google_auth_code,
    verify_google_id_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=AuthTokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with email & password and issue JWT tokens."""
    return AuthService.register_local_user(db, payload)


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate an existing email/password user."""
    return AuthService.authenticate_local_user(db, payload)


@router.get("/google/url")
def google_authorize_url(state: str | None = None):
    """Return the Google OAuth2 authorization URL for browser sign-in."""
    return build_google_authorize_url(state=state)


@router.post("/google", response_model=AuthTokenResponse)
def google_id_token_login(payload: GoogleTokenLoginRequest, db: Session = Depends(get_db)):
    """Authenticate using a verified Google OIDC ID token."""
    identity = verify_google_id_token(payload.id_token)
    return AuthService.authenticate_google_identity(db, identity)


@router.post("/google/callback", response_model=AuthTokenResponse)
def google_code_callback(payload: GoogleCodeLoginRequest, db: Session = Depends(get_db)):
    """Exchange a Google OAuth2 authorization code and authenticate the user."""
    identity = exchange_google_auth_code(payload.code, redirect_uri=payload.redirect_uri)
    return AuthService.authenticate_google_identity(db, identity)


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh_session(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Issue a new access & refresh token pair."""
    return AuthService.refresh_tokens(db, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user
