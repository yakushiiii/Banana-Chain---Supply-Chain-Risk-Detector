"""Asynchronous scan creation and polling endpoints (Issue #34)."""

from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.schemas.repo_scan import RepoScanCreate, ScanAccepted
from app.schemas.scan import ScanRead, ScanStatus
from app.services.scan_queue import ScanQueueError, enqueue_scan
from models import Component, Project, Sbom, Scan
from settings import settings

router = APIRouter(tags=["scans"])


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(settings.database_url, pool_pre_ping=True)


def get_session():
    with Session(get_engine()) as session:
        yield session


def _find_or_create_project(session: Session, url: str) -> Project:
    project = session.scalar(select(Project).where(Project.repo_url == url))
    if project is not None:
        return project

    owner, name = url.removeprefix("https://github.com/").split("/")
    # Savepoint handles concurrent requests submitting the same new repository.
    # The unique index on projects.repo_url enforces the invariant atomically.
    try:
        with session.begin_nested():
            project = Project(repo_url=url, owner=owner, name=name)
            session.add(project)
            session.flush()
        return project
    except IntegrityError:
        project = session.scalar(select(Project).where(Project.repo_url == url))
        if project is None:
            raise
        return project


@router.post(
    "/scans",
    response_model=ScanAccepted,
    status_code=202,
    summary="Queue a GitHub repository scan",
    responses={
        202: {
            "description": "Queued for asynchronous scanning",
            "content": {
                "application/json": {
                    "example": {
                        "scan_id": "71f4c512-9340-4b41-b947-4b8f6043db12",
                        "status": "queued",
                    }
                }
            },
        },
        422: {"description": "Invalid or missing GitHub repository URL"},
        503: {"description": "The scan queue is not available"},
    },
)
def create_scan(
    request: RepoScanCreate = Body(
        ...,
        openapi_examples={
            "github": {
                "summary": "Scan a public GitHub repository",
                "value": {"repo_url": "https://github.com/psf/requests"},
            }
        },
    ),
    session: Session = Depends(get_session),
) -> ScanAccepted:
    url = str(request.repo_url)
    try:
        project = _find_or_create_project(session, url)
        scan = Scan(project_id=project.id, status="queued")
        session.add(scan)
        session.commit()
        session.refresh(scan)
    except Exception:
        session.rollback()
        raise

    # Commit first so a worker can read the scan by ID as soon as it receives it.
    try:
        enqueue_scan(scan.id)
    except ScanQueueError as exc:
        # Avoid leaving an unprocessable job permanently in `queued`.
        scan.status = "failed"
        scan.error_message = "Scan job could not be queued"
        scan.finished_at = datetime.now(timezone.utc)
        session.commit()
        raise HTTPException(status_code=503, detail="Scan queue unavailable") from exc

    return ScanAccepted(scan_id=scan.id, status=ScanStatus.QUEUED)


@router.get(
    "/scans/{scan_id}",
    response_model=ScanRead,
    summary="Get scan status and component count",
    responses={
        200: {
            "description": "Latest persisted scan state",
            "content": {
                "application/json": {
                    "example": {
                        "scan_id": "71f4c512-9340-4b41-b947-4b8f6043db12",
                        "status": "completed",
                        "repo_url": "https://github.com/psf/requests",
                        "component_count": 31,
                        "created_at": "2026-11-18T19:00:00Z",
                        "completed_at": "2026-11-18T19:02:15Z",
                        "error_message": None,
                    }
                }
            },
        },
        404: {"description": "Scan ID not found"},
    },
)
def get_scan(scan_id: UUID, session: Session = Depends(get_session)) -> ScanRead:
    scan = session.scalar(
        select(Scan).options(joinedload(Scan.project)).where(Scan.id == scan_id)
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Pre-#37 databases used `running`/`succeeded`; newer databases accept
    # fine-grained status values. Maintain response compatibility with both.
    value = {"running": "scanning", "succeeded": "completed"}.get(scan.status, scan.status)

    component_count = 0
    if value in {"completed", "succeeded", "partial"}:
        component_count = session.scalar(
            select(func.count(Component.id))
            .join(Sbom, Component.sbom_id == Sbom.id)
            .where(Sbom.scan_id == scan.id)
        ) or 0

    return ScanRead(
        scan_id=scan.id,
        status=value,
        repo_url=scan.project.repo_url,
        component_count=component_count,
        created_at=scan.created_at,
        completed_at=scan.finished_at if value in {"completed", "succeeded"} else None,
        error_message=scan.error_message,
    )
