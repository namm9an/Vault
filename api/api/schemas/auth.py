from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.models.user import UserRole


class SignupRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: UserRole
    org_id: UUID
    department_id: UUID | None = None
    is_active: bool


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    base_currency: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str


class MeResponse(BaseModel):
    user: UserOut
    org: OrgOut


class OkResponse(BaseModel):
    ok: bool = True
