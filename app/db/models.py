from typing import Any
from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


# PostgreSQL uses JSONB; SQLite can use JSON for isolated tests.
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class SbomRecord(Base):
    """Stores the original CycloneDX document for a scan."""

    __tablename__ = "sboms"

    scan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    raw: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE,
        nullable=False,
    )


class ComponentRecord(Base):
    """Stores a normalized component belonging to an SBOM."""

    __tablename__ = "components"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    scan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sboms.scan_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    version: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    purl: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    licenses: Mapped[list[str]] = mapped_column(
        JSON_TYPE,
        nullable=False,
    )

    locations: Mapped[list[str]] = mapped_column(
        JSON_TYPE,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    confidence: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    properties: Mapped[list[dict[str, str]]] = mapped_column(
        JSON_TYPE,
        nullable=False,
    )