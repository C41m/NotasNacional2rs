from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    email: str = Field(..., max_length=255)
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
