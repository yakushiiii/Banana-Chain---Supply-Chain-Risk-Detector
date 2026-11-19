"""PostgreSQL integration coverage for Issue #78.

Uses the shared banana_test engine fixture. It applies/downgrades Alembic,
so point the environment at the dedicated disposable test database only.
"""

from uuid import uuid4

import pytest
from sqlalchemy import delete, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.schemas.component import Component as NormalizedComponent
from app.services.sbom_persistence import save_sbom
from models import Component, Project, Sbom, Scan


def component(name: str, purl: str | None = None) -> NormalizedComponent:
    return NormalizedComponent(
        name=name,
        type="library",
        purl=purl,
        source="syft",
        locations=[f"/repo/{name}"],
        licenses=["MIT"],
    )


def raw_doc(n: int) -> dict:
    return {"bomFormat": "CycloneDX", "specVersion": "1.7", "components": [{"name": str(i)} for i in range(n)]}


@pytest.fixture
def scan_context(engine):
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        project = Project(repo_url=f"https://github.com/issue78/{uuid4().hex}", owner="issue78", name="fixture")
        session.add(project)
        session.flush()
        project_id = project.id
        scan = Scan(project_id=project.id, status="queued")
        session.add(scan)
        session.flush()
        scan_id = scan.id
    yield factory, scan_id
    with factory.begin() as session:
        session.execute(delete(Project).where(Project.id == project_id))


def test_bulk_save_persists_raw_and_normalized_components(scan_context):
    factory, scan_id = scan_context
    components = [component("alpha", "pkg:pypi/alpha@1"), component("local")]
    sbom_id = save_sbom(scan_id, raw_doc(2), components, session_factory=factory)
    with factory() as session:
        sbom = session.get(Sbom, sbom_id)
        assert sbom.scan_id == scan_id
        assert sbom.spec_version == "1.7"
        assert sbom.raw["components"] == raw_doc(2)["components"]
        saved = session.scalars(select(Component).where(Component.sbom_id == sbom_id).order_by(Component.name)).all()
        assert [item.name for item in saved] == ["alpha", "local"]
        assert saved[0].licenses == ["MIT"]
        assert {p["name"]: p["value"] for p in saved[0].properties}["banana:source"] == "syft"


def test_repeat_save_replaces_rows_without_changing_sbom_id(scan_context):
    factory, scan_id = scan_context
    first_id = save_sbom(scan_id, raw_doc(1), [component("old", "pkg:pypi/old@1")], session_factory=factory)
    second_id = save_sbom(scan_id, raw_doc(1), [component("new", "pkg:pypi/new@2")], session_factory=factory)
    assert first_id == second_id
    with factory() as session:
        names = session.scalars(select(Component.name).where(Component.sbom_id == first_id)).all()
        assert names == ["new"]


def test_failed_bulk_insert_rolls_back_existing_data(scan_context):
    factory, scan_id = scan_context
    sbom_id = save_sbom(scan_id, raw_doc(1), [component("original", "pkg:pypi/original@1")], session_factory=factory)
    duplicate_purl = "pkg:pypi/duplicate@1"
    with pytest.raises(IntegrityError):
        save_sbom(
            scan_id,
            raw_doc(2),
            [component("a", duplicate_purl), component("b", duplicate_purl)],
            session_factory=factory,
        )
    with factory() as session:
        sbom = session.get(Sbom, sbom_id)
        assert len(sbom.raw["components"]) == 1
        saved = session.scalars(select(Component.name).where(Component.sbom_id == sbom_id)).all()
        assert saved == ["original"]


def test_large_save_uses_batched_sql_instead_of_one_insert_per_component(scan_context, engine):
    factory, scan_id = scan_context
    count = 1200
    inserts = []

    def before_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO COMPONENTS"):
            inserts.append(statement)

    event.listen(engine, "before_cursor_execute", before_execute)
    try:
        sbom_id = save_sbom(
            scan_id,
            raw_doc(0),
            [component(f"package-{i}", f"pkg:pypi/package-{i}@1") for i in range(count)],
            session_factory=factory,
            batch_size=400,
        )
    finally:
        event.remove(engine, "before_cursor_execute", before_execute)

    with factory() as session:
        saved_count = len(session.scalars(select(Component.id).where(Component.sbom_id == sbom_id)).all())
        assert saved_count == count
    assert 1 <= len(inserts) <= 10, "Unexpected per-row component INSERT statements"


def test_required_component_lookup_indexes_exist(engine):
    names = {index["name"] for index in inspect(engine).get_indexes("components")}
    assert {"ix_components_sbom_id", "ix_components_purl", "uq_components_sbom_id_purl"} <= names


def test_invalid_document_does_not_modify_database(scan_context):
    factory, scan_id = scan_context
    with pytest.raises(ValueError, match="specVersion"):
        save_sbom(scan_id, {"bomFormat": "CycloneDX"}, [component("x")], session_factory=factory)
    with factory() as session:
        assert session.scalar(select(Sbom).where(Sbom.scan_id == scan_id)) is None
