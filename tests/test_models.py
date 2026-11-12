import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from models import Component, Project, Sbom, Scan


def make_chain(session, purl="pkg:pypi/fastapi@0.110.0"):
    project = Project(repo_url="https://github.com/u/r", owner="u", name="r")
    scan = Scan(project=project, status="queued")
    sbom = Sbom(scan=scan, spec_version="1.6", raw={"bomFormat": "CycloneDX"})
    comp = Component(
        sbom=sbom, name="fastapi", version="0.110.0", purl=purl, type="library",
        licenses=[{"license": {"id": "MIT"}}], confidence=0.9, properties=[{"name": "k", "value": "v"}],
    )
    session.add_all([project, scan, sbom, comp])
    session.flush()
    return project, scan, sbom, comp


def test_insert_and_read_each_entity(session):
    project, scan, sbom, comp = make_chain(session)
    session.expire_all()

    assert session.get(Project, project.id).owner == "u"
    assert session.get(Project, project.id).created_at is not None
    assert session.get(Scan, scan.id).status == "queued"
    assert session.get(Sbom, sbom.id).raw["bomFormat"] == "CycloneDX"
    c = session.get(Component, comp.id)
    assert c.licenses[0]["license"]["id"] == "MIT"
    assert c.purl == "pkg:pypi/fastapi@0.110.0"


def test_repo_url_unique(session):
    session.add(Project(repo_url="https://github.com/u/r", owner="u", name="r"))
    session.add(Project(repo_url="https://github.com/u/r", owner="u", name="r"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_duplicate_purl_in_same_sbom_rejected(session):
    _, _, sbom, _ = make_chain(session)
    session.add(Component(sbom_id=sbom.id, name="dup", purl="pkg:pypi/fastapi@0.110.0", type="library"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_null_purls_allowed_multiple_times(session):
    _, _, sbom, _ = make_chain(session)
    session.add_all([
        Component(sbom_id=sbom.id, name="a", purl=None, type="file"),
        Component(sbom_id=sbom.id, name="b", purl=None, type="file"),
    ])
    session.flush()


def test_invalid_status_rejected(session):
    project = Project(repo_url="https://github.com/u/x", owner="u", name="x")
    session.add(Scan(project=project, status="bogus"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_project_cascades(session):
    project, _, sbom, comp = make_chain(session)
    session.delete(project)
    session.flush()
    assert session.scalar(select(Sbom).where(Sbom.id == sbom.id)) is None
    assert session.scalar(select(Component).where(Component.id == comp.id)) is None


def test_migrations_round_trip_and_no_drift(engine, alembic_cfg):
    command.downgrade(alembic_cfg, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(alembic_cfg, "head")
    assert {"projects", "scans", "sboms", "components"} <= set(inspect(engine).get_table_names())
    command.check(alembic_cfg)  # fails if models differ from migrations