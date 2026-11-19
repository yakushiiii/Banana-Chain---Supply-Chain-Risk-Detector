"""Request and acknowledgement contracts for the asynchronous repo scan API.

ScanCreate intentionally continues to accept missing URLs for legacy upload flows.
"""

import re
from uuid import UUID

from pydantic import BaseModel, HttpUrl, field_validator

from .scan import ScanStatus


_REPO_SEGMENT = re.compile(r"[A-Za-z0-9_.-]+\Z")


class RepoScanCreate(BaseModel):
    """POST /scans requires an HTTPS GitHub owner/repository URL."""

    repo_url: HttpUrl

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, url: HttpUrl) -> HttpUrl:
        if (
            url.scheme != "https"
            or url.host != "github.com"
            or url.port not in (None, 443)
            or url.username is not None
            or url.password is not None
            or url.query is not None
            or url.fragment is not None
        ):
            raise ValueError("Provide an HTTPS github.com repository URL")

        segments = (url.path or "").strip("/").split("/")
        if len(segments) != 2:
            raise ValueError("Repository URL must contain an owner and repository name")

        owner, name = segments
        if name.endswith(".git"):
            name = name[:-4]

        if (
            not owner
            or not name
            or owner in (".", "..")
            or name in (".", "..")
            or not _REPO_SEGMENT.fullmatch(owner)
            or not _REPO_SEGMENT.fullmatch(name)
            or len(owner) > 255
            or len(name) > 255
        ):
            raise ValueError("Repository URL has an invalid owner or repository name")

        # GitHub repository paths are case-insensitive. Canonical URLs prevent
        # two Project rows for case/trailing-slash/.git variations of one repo.
        return HttpUrl(f"https://github.com/{owner.lower()}/{name.lower()}")


class ScanAccepted(BaseModel):
    """Acknowledgement returned before the worker starts processing."""

    scan_id: UUID
    status: ScanStatus
