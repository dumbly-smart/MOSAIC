"""Public FastAPI request and response schemas."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class CaseStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    CLOSED = "closed"


class DocumentKind(StrEnum):
    TENDER = "tender"
    BIDDER = "bidder"


class CaseCreate(BaseModel):
    tender_title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by: UUID
    tender_title: str
    description: str | None
    status: CaseStatus
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    kind: DocumentKind
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    processing_status: str
    created_at: datetime


class UserResponse(BaseModel):
    id: UUID
    email: str | None


class HealthResponse(BaseModel):
    status: str
    configured: bool


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=6, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
