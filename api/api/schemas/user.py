from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.models.user import UserRole
from api.schemas.auth import UserOut


class UserListResponse(BaseModel):
    items: list[UserOut]
    next_cursor: str | None = None


class UserInvite(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: UserRole = UserRole.EMPLOYEE
    department_id: UUID | None = None
    password: str = Field(min_length=8, max_length=200)


class UserInviteResponse(BaseModel):
    user: UserOut
    invite_token: str


class UserUpdate(BaseModel):
    role: UserRole | None = None
    department_id: UUID | None = None
    is_active: bool | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=200)


class UserResponse(BaseModel):
    user: UserOut
