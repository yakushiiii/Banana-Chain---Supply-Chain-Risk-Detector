from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class ScanContext(BaseModel):
    """Information shared between stages of a scan."""

    scan_id: UUID

    repo_url: HttpUrl | None = None

    workspace_path: Path

    # Not available until the repository has been cloned.
    commit_sha: str | None = None
