"""Real PostgreSQL integration smoke test (requires isolated banana_test DB).

Run explicitly with: python -m pytest tests/test_scan_api_postgres.py -q
The shared engine fixture upgrades and downgrades Alembic on this database.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import scans as scan_api
from app.main import app
from models import Component, Project, Sbom, Scan


def test_scan_api_project_scan_sbom_polling_with_postgres(engine, monkeypatch):
    repo_url = f"https://github.com/banana-api/issue34-{uuid4().hex}"
    dispatched = []
    monkeypatch.setattr(scan_api, "enqueue_scan", dispatched.append)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[scan_api.get_session] = session_override
    project_id = None
    try:
        with TestClient(app) as client:
            first = client.post("/scans", json={"repo_url": repo_url})
            second = client.post("/scans", json={"repo_url": repo_url})
            assert first.status_code == second.status_code == 202
            first_id = UUID(first.json()["scan_id"])
            second_id = UUID(second.json()["scan_id"])
            assert first_id != second_id
            assert dispatched == [first_id, second_id]

            with Session(engine) as session:
                project = session.scalar(select(Project).where(Project.repo_url == repo_url))
                assert project is not None
                project_id = project.id
                assert session.scalar(
                    select(func.count(Scan.id)).where(Scan.project_id == project.id)
                ) == 2

            assert client.get(f"/scans/{first_id}").json()["component_count"] == 0

            # Simulate the persistence work performed by the Issue #33 worker.
            with Session(engine) as session:
                scan = session.get(Scan, first_id)
                scan.status = "succeeded"  # legacy terminal status supported by both revisions
                scan.finished_at = datetime.now(timezone.utc)
                sbom = Sbom(scan_id=first_id, spec_version="1.6", raw={})
                session.add(sbom)
                session.flush()
                session.add(
                    Component(sbom_id=sbom.id, name="requests", type="library", version="2.31.0")
                )
                session.commit()

            completed = client.get(f"/scans/{first_id}")
            assert completed.status_code == 200
            assert completed.json()["status"] == "completed"
            assert completed.json()["component_count"] == 1
            assert completed.json()["completed_at"] is not None
            assert client.get(f"/scans/{uuid4()}").status_code == 404
    finally:
        app.dependency_overrides.clear()
        if project_id is not None:
            with Session(engine) as session:
                project = session.get(Project, project_id)
                if project is not None:
                    session.delete(project)
                    session.commit()
