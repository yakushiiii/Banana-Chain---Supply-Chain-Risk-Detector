import json
from pathlib import Path
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import SbomRecord, ComponentRecord
from app.services.sbom import save_sbom

from services.cyclonedx import normalize_sbom


@pytest.fixture
def db_context():
    """Create an isolated SQLite database for each test."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    yield engine, session_factory

    engine.dispose()


def load_requests_fixture():
    """Load the sanitized real-world CycloneDX fixture."""

    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "requests.cdx.json"
    )

    return json.loads(
        fixture.read_text(encoding="utf-8")
    )


def test_save_sbom_persists_raw_and_components(db_context):
    _, session_factory = db_context

    scan_id = uuid4()

    raw_doc = load_requests_fixture()
    components = normalize_sbom(raw_doc)

    assert len(raw_doc["components"]) == 31
    assert len(components) == 23

    save_sbom(
        scan_id,
        raw_doc,
        components,
        session_factory=session_factory,
    )

    with session_factory() as session:

        saved_sbom = session.get(SbomRecord, scan_id)

        assert saved_sbom is not None

        # The original, unnormalized document is preserved.
        assert saved_sbom.raw == raw_doc
        assert len(saved_sbom.raw["components"]) == 31

        saved_components = session.scalars(
            select(ComponentRecord).where(
                ComponentRecord.scan_id == scan_id
            )
        ).all()

        assert len(saved_components) == 23

        checkout = next(
            component
            for component in saved_components
            if component.purl
            == "pkg:github/actions/checkout@v7.0.0"
        )

        # Deduplicated components retain merged locations.
        assert len(checkout.locations) == 6


def test_save_sbom_is_idempotent(db_context):
    _, session_factory = db_context

    scan_id = uuid4()

    original_doc = load_requests_fixture()
    original_components = normalize_sbom(original_doc)

    save_sbom(
        scan_id,
        original_doc,
        original_components,
        session_factory=session_factory,
    )

    # Save a different SBOM using the same scan ID.
    replacement_doc = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "components": [
            {
                "type": "library",
                "name": "replacement",
                "version": "1.0",
            }
        ],
    }

    replacement_components = normalize_sbom(replacement_doc)

    save_sbom(
        scan_id,
        replacement_doc,
        replacement_components,
        session_factory=session_factory,
    )

    with session_factory() as session:

        sbom_count = session.scalar(
            select(func.count()).select_from(SbomRecord)
        )

        component_count = session.scalar(
            select(func.count()).select_from(ComponentRecord)
        )

        assert sbom_count == 1
        assert component_count == 1

        saved_sbom = session.get(SbomRecord, scan_id)

        assert saved_sbom.raw == replacement_doc

        saved_component = session.scalar(
            select(ComponentRecord)
        )

        assert saved_component.name == "replacement"


def test_save_sbom_rolls_back_on_failure(db_context):
    engine, session_factory = db_context

    scan_id = uuid4()

    original_doc = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "components": [
            {
                "type": "library",
                "name": "original",
                "version": "1.0",
            }
        ],
    }

    save_sbom(
        scan_id,
        original_doc,
        normalize_sbom(original_doc),
        session_factory=session_factory,
    )

    replacement_doc = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "components": [
            {
                "type": "library",
                "name": "replacement",
                "version": "2.0",
            }
        ],
    }

    # Simulate a database failure during component insertion.
    def fail_component_insert(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        if statement.lstrip().lower().startswith(
            "insert into components"
        ):
            raise RuntimeError("Simulated component insert failure")

    event.listen(
        engine,
        "before_cursor_execute",
        fail_component_insert,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated component insert failure",
        ):
            save_sbom(
                scan_id,
                replacement_doc,
                normalize_sbom(replacement_doc),
                session_factory=session_factory,
            )
    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            fail_component_insert,
        )

    # The failed transaction must preserve the original data.
    with session_factory() as session:

        saved_sbom = session.get(SbomRecord, scan_id)

        assert saved_sbom.raw == original_doc

        saved_components = session.scalars(
            select(ComponentRecord)
        ).all()

        assert len(saved_components) == 1
        assert saved_components[0].name == "original"