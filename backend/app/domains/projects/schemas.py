"""Pydantic schemas for the projects domain."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domains.projects.models import ProjectRole


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class ProjectListItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    role: ProjectRole


class MemberRead(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: ProjectRole


class MemberAdd(BaseModel):
    email: EmailStr
    role: ProjectRole = ProjectRole.member


class MemberRoleUpdate(BaseModel):
    role: ProjectRole
