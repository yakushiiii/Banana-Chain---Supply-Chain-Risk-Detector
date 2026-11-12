import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, Index, MetaData, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Deterministic constraint names so autogenerate and downgrade are reliable
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    repo_url: Mapped[str] = mapped_column(Text, unique=True)
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    scans: Mapped[list["Scan"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class Scan(Base):
    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed')", name="status_valid"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    error_message: Mapped[str | None] = mapped_column(Text)
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="scans")
    sbom: Mapped["Sbom | None"] = relationship(
        back_populates="scan", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )


class Sbom(Base):
    __tablename__ = "sboms"

    id: Mapped[uuid.UUID] = uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), unique=True
    )
    spec_version: Mapped[str] = mapped_column(String(20))
    raw: Mapped[dict] = mapped_column(JSONB)

    scan: Mapped[Scan] = relationship(back_populates="sbom")
    components: Mapped[list["Component"]] = relationship(
        back_populates="sbom", cascade="all, delete-orphan", passive_deletes=True
    )


class Component(Base):
    __tablename__ = "components"
    __table_args__ = (
        Index("ix_components_sbom_id", "sbom_id"),
        Index("ix_components_purl", "purl"),
        Index(
            "uq_components_sbom_id_purl",
            "sbom_id",
            "purl",
            unique=True,
            postgresql_where=text("purl IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    sbom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sboms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(Text)
    purl: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(50))
    licenses: Mapped[list | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    properties: Mapped[list | None] = mapped_column(JSONB)

    sbom: Mapped[Sbom] = relationship(back_populates="components")