from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleTokenLoginRequest(BaseModel):
    id_token: str = Field(min_length=10)


class GoogleCodeLoginRequest(BaseModel):
    code: str = Field(min_length=4)
    redirect_uri: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    auth_provider: str
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
