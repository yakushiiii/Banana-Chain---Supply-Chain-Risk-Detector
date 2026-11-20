from enum import Enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ScanStatus(str, Enum):
    """Possible states in the SBOM scanning pipeline."""

    QUEUED = "queued"
    CLONING = "cloning"
    SCANNING = "scanning"
    NORMALIZING = "normalizing"
    PERSISTING = "persisting"
    COMPLETED = "completed"
    FAILED = "failed"

class ScanCreate(BaseModel):
    """Data provided when requesting a new scan."""

    # Optional because the application also supports file uploads.
    # Uploaded files are handled separately through multipart requests.
    repo_url: HttpUrl | None = None

class ScanRead(BaseModel):
    """Information returned when retrieving a scan."""

    scan_id: UUID
    status: ScanStatus

    repo_url: HttpUrl | None = None

    component_count: int = Field(default=0, ge=0)

    created_at: datetime | None = None
    completed_at: datetime | None = None

    error_message: str | None = None
