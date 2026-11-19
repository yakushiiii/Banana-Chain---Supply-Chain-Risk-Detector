"""End-to-end HTTP tests against a disposable SQLite ORM simulation.

PostgreSQL/Alembic baseline tests remain in tests/test_models.py. Tests here
verify FastAPI contracts and SQLAlchemy behavior without needing Redis/Syft.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import scans as scan_api
from app.main import app
from app.schemas.repo_scan import RepoScanCreate
from models import Base, Component, Project, Sbom, Scan


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    """SQLite test DB accepts JSONB columns; production remains PostgreSQL."""
    return "JSON"


@pytest.fixture
def api_fixture(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    # Only build the four tables the scan API touches. Other feature tables
    # may use PostgreSQL-only defaults such as JSONB casts (Issue #37).
    Base.metadata.create_all(
        engine, tables=[Project.__table__, Scan.__table__, Sbom.__table__, Component.__table__]
    )

    def override_session():
        with Session(engine) as session:
            yield session

    dispatched = []
    monkeypatch.setattr(scan_api, "enqueue_scan", dispatched.append)
    app.dependency_overrides[scan_api.get_session] = override_session
    with TestClient(app) as client:
        yield client, engine, dispatched
    app.dependency_overrides.clear()
    engine.dispose()


def test_openapi_documents_both_endpoints(api_fixture):
    client, _, _ = api_fixture
    spec = client.get("/openapi.json").json()
    assert spec["paths"]["/scans"]["post"]["responses"].keys() >= {"202", "422", "503"}
    assert spec["paths"]["/scans/{scan_id}"]["get"]["responses"].keys() >= {"200", "404", "422"}
    assert spec["paths"]["/scans"]["post"]["responses"]["202"]["content"]["application/json"]["example"]["status"] == "queued"
    assert spec["paths"]["/scans/{scan_id}"]["get"]["responses"]["200"]["content"]["application/json"]["example"]["status"] == "completed"


def test_post_queues_and_persists_scan(api_fixture):
    client, engine, dispatched = api_fixture
    response = client.post("/scans", json={"repo_url": "https://github.com/PSF/Requests.git/"})
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload == {"scan_id": str(dispatched[0]), "status": "queued"}

    with Session(engine) as session:
        project = session.scalar(select(Project))
        scan = session.scalar(select(Scan))
        assert project.repo_url == "https://github.com/psf/requests"
        assert project.owner == "psf"
        assert project.name == "requests"
        assert scan.id == dispatched[0]
        assert scan.project_id == project.id
        assert scan.status == "queued"


def test_get_queued_scan(api_fixture):
    client, _, _ = api_fixture
    created = client.post("/scans", json={"repo_url": "https://github.com/psf/requests"})
    response = client.get("/scans/" + created.json()["scan_id"])
    assert response.status_code == 200
    result = response.json()
    assert result["scan_id"] == created.json()["scan_id"]
    assert result["status"] == "queued"
    assert result["component_count"] == 0
    assert result["created_at"] is not None
    assert result["completed_at"] is None
    assert result["error_message"] is None
    assert result["repo_url"] == "https://github.com/psf/requests"


@pytest.mark.parametrize("body", [
    {},
    {"repo_url": None},
    {"repo_url": "not-a-url"},
    {"repo_url": "https://google.com/user/repo"},
    {"repo_url": "https://github.com/"},
    {"repo_url": "https://github.com/user"},
    {"repo_url": "https://github.com/user/repo/issues"},
    {"repo_url": "http://github.com/user/repo"},
    {"repo_url": "https://github.com/user/repo?tab=readme"},
    {"repo_url": "https://github.com/user/repo#readme"},
    {"repo_url": "https://github.com.evil.example/user/repo"},
    {"repo_url": "https://github.com:444/user/repo"},
    {"repo_url": "https://github.com/user/%2e%2e"},
])
def test_post_rejects_invalid_repos_without_db_writes(body, api_fixture):
    client, engine, dispatched = api_fixture
    response = client.post("/scans", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]
    assert dispatched == []
    with Session(engine) as session:
        assert session.scalar(select(func.count(Project.id))) == 0
        assert session.scalar(select(func.count(Scan.id))) == 0


def test_duplicate_url_creates_two_scans_but_one_project(api_fixture):
    client, engine, dispatched = api_fixture
    first = client.post("/scans", json={"repo_url": "https://github.com/user/repo"})
    second = client.post("/scans", json={"repo_url": "https://github.com/USER/REPO.git/"})
    assert first.status_code == second.status_code == 202
    assert first.json()["scan_id"] != second.json()["scan_id"]
    assert len(dispatched) == 2
    with Session(engine) as session:
        assert session.scalar(select(func.count(Project.id))) == 1
        assert session.scalar(select(func.count(Scan.id))) == 2


def test_unknown_uuid_returns_404(api_fixture):
    client, _, _ = api_fixture
    response = client.get("/scans/" + str(uuid4()))
    assert response.status_code == 404
    assert response.json() == {"detail": "Scan not found"}


def test_malformed_scan_id_returns_422(api_fixture):
    client, _, _ = api_fixture
    assert client.get("/scans/not-a-uuid").status_code == 422


def test_queue_failure_marks_scan_failed(api_fixture, monkeypatch):
    client, engine, dispatched = api_fixture

    def reject(_scan_id):
        raise scan_api.ScanQueueError("offline")

    monkeypatch.setattr(scan_api, "enqueue_scan", reject)
    response = client.post("/scans", json={"repo_url": "https://github.com/user/repo"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Scan queue unavailable"}
    assert dispatched == []
    with Session(engine) as session:
        scan = session.scalar(select(Scan))
        assert scan.status == "failed"
        assert scan.finished_at is not None
        assert scan.error_message == "Scan job could not be queued"


def test_completed_scan_returns_saved_component_count(api_fixture):
    client, engine, _ = api_fixture
    created = client.post("/scans", json={"repo_url": "https://github.com/user/repo"}).json()
    with Session(engine) as session:
        scan = session.get(Scan, UUID(created["scan_id"]))
        # In the initial schema, the legacy succeeded value denotes completion.
        scan.status = "succeeded"
        scan.finished_at = datetime.now(timezone.utc)
        sbom = Sbom(scan_id=scan.id, spec_version="1.6", raw={})
        session.add(sbom)
        session.flush()
        session.add_all([
            Component(sbom_id=sbom.id, name="a", type="library"),
            Component(sbom_id=sbom.id, name="b", type="library"),
        ])
        session.commit()

    response = client.get("/scans/" + created["scan_id"])
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "completed"
    assert result["component_count"] == 2
    assert result["completed_at"] is not None


def test_failed_scan_does_not_claim_component_count(api_fixture):
    client, engine, _ = api_fixture
    created = client.post("/scans", json={"repo_url": "https://github.com/user/repo"}).json()
    with Session(engine) as session:
        scan = session.get(Scan, UUID(created["scan_id"]))
        scan.status = "failed"
        scan.error_message = "Clone failed"
        session.commit()
    result = client.get("/scans/" + created["scan_id"]).json()
    assert result["status"] == "failed"
    assert result["error_message"] == "Clone failed"
    assert result["component_count"] == 0


def test_existing_upload_contract_remains_optional():
    from app.schemas.scan import ScanCreate

    assert ScanCreate().repo_url is None
    assert str(RepoScanCreate(repo_url="https://github.com/org/repo").repo_url) == (
        "https://github.com/org/repo"
    )
