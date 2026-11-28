import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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


# Keep in sync with app.schemas.scan.ScanStatus and this issue's Alembic revision.
SCAN_STATUS_VALUES = (
    "queued", "running", "succeeded",  # legacy persisted statuses
    "cloning", "scanning", "normalizing", "persisting",
    "checking_files", "matching", "scoring", "completed", "partial", "failed",
)
SEVERITY_BANDS = ("none", "low", "medium", "high", "critical", "unknown")
ASSESSMENT_STATUSES = ("assessed", "not_assessed")


def accepted(values: tuple[str, ...]) -> str:
    return ",".join(f"'{value}'" for value in values)


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
            f"status IN ({accepted(SCAN_STATUS_VALUES)})", name="status_valid"
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
    findings: Mapped[list["ScanFinding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", passive_deletes=True
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
        CheckConstraint("risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 10)", name="risk_score_range"),
        CheckConstraint(f"risk_band IS NULL OR risk_band IN ({accepted(SEVERITY_BANDS)})", name="risk_band_valid"),
        CheckConstraint(f"assessment_status IN ({accepted(ASSESSMENT_STATUSES)})", name="assessment_status_valid"),
        CheckConstraint(
            "assessment_status <> 'not_assessed' OR (risk_score IS NULL AND risk_band IS NULL)",
            name="not_assessed_without_score",
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
    risk_score: Mapped[float | None] = mapped_column(Float)
    risk_band: Mapped[str | None] = mapped_column(String(20))
    assessment_status: Mapped[str] = mapped_column(
        String(20), default="not_assessed", server_default="not_assessed"
    )
    assessment_reason: Mapped[str | None] = mapped_column(Text)

    sbom: Mapped[Sbom] = relationship(back_populates="components")
    vulnerability_matches: Mapped[list["ComponentVulnerability"]] = relationship(
        back_populates="component", cascade="all, delete-orphan", passive_deletes=True
    )


class Vulnerability(Base):
    """OSV cache; shared across all scans/components."""

    __tablename__ = "vulnerabilities"
    __table_args__ = (
        CheckConstraint(
            "cvss_score IS NULL OR (cvss_score >= 0 AND cvss_score <= 10)",
            name="cvss_score_range",
        ),
        CheckConstraint(
            f"severity_band IN ({accepted(SEVERITY_BANDS)})",
            name="severity_band_valid",
        ),
    )

    osv_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    aliases: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    summary: Mapped[str | None] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text)
    cvss_vector: Mapped[str | None] = mapped_column(Text)
    cvss_score: Mapped[float | None] = mapped_column(Float)
    severity_band: Mapped[str] = mapped_column(
        String(20), default="unknown", server_default="unknown"
    )
    published: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    references: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    fixed_versions: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    component_matches: Mapped[list["ComponentVulnerability"]] = relationship(
        back_populates="vulnerability", cascade="all, delete-orphan", passive_deletes=True
    )


class ComponentVulnerability(Base):
    __tablename__ = "component_vulnerabilities"
    __table_args__ = (
        UniqueConstraint("component_id", "osv_id", name="uq_component_vulnerabilities_component_osv"),
        Index("ix_component_vulnerabilities_osv_id", "osv_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("components.id", ondelete="CASCADE")
    )
    osv_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("vulnerabilities.osv_id", ondelete="CASCADE")
    )
    fixed_version: Mapped[str | None] = mapped_column(Text)

    component: Mapped[Component] = relationship(back_populates="vulnerability_matches")
    vulnerability: Mapped[Vulnerability] = relationship(back_populates="component_matches")


class ScanFinding(Base):
    __tablename__ = "scan_findings"
    __table_args__ = (
        CheckConstraint(
            f"severity IN ({accepted(SEVERITY_BANDS)})", name="severity_valid"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(100))
    ecosystem: Mapped[str | None] = mapped_column(String(100))
    path: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    scan: Mapped[Scan] = relationship(back_populates="findings")


class EpssScore(Base):
    """Daily EPSS snapshot for a CVE; PK retains history by observation date."""

    __tablename__ = "epss_scores"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 1", name="score_range"),
        CheckConstraint("percentile >= 0 AND percentile <= 1", name="percentile_range"),
    )

    cve_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    percentile: Mapped[float] = mapped_column(Float)
