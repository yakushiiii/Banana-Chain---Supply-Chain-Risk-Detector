import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.database import get_session_factory
from app.db.models import SbomRecord, ComponentRecord
from app.services.sbom import save_sbom

from services.cyclonedx import normalize_sbom


def main():
    """Verify SBOM persistence against PostgreSQL."""

    fixture = (
        Path("tests")
        / "fixtures"
        / "requests.cdx.json"
    )

    raw_doc = json.loads(
        fixture.read_text(encoding="utf-8")
    )

    components = normalize_sbom(raw_doc)

    scan_id = uuid4()
    session_factory = get_session_factory()

    print("Raw SBOM entries:", len(raw_doc["components"]))
    print("Normalized components:", len(components))

    try:
        # Save the SBOM.
        save_sbom(
            scan_id,
            raw_doc,
            components,
            session_factory=session_factory,
        )

        # Save it again to verify idempotency.
        save_sbom(
            scan_id,
            raw_doc,
            components,
            session_factory=session_factory,
        )

        with session_factory() as session:
            saved_sbom = session.get(SbomRecord, scan_id)

            saved_components = session.scalars(
                select(ComponentRecord).where(
                    ComponentRecord.scan_id == scan_id
                )
            ).all()

            assert saved_sbom is not None
            assert saved_sbom.raw == raw_doc

            assert len(saved_sbom.raw["components"]) == 31
            assert len(saved_components) == 23

            checkout = next(
                component
                for component in saved_components
                if component.purl
                == "pkg:github/actions/checkout@v7.0.0"
            )

            assert len(checkout.locations) == 6

            print("PostgreSQL persistence verified.")
            print("Stored SBOM records: 1")
            print("Stored component records:", len(saved_components))
            print("Duplicate prevention: passed")
            print("Raw document preservation: passed")

    finally:
        # Remove only the temporary scan created by this test.
        with session_factory.begin() as session:
            session.execute(
                delete(ComponentRecord).where(
                    ComponentRecord.scan_id == scan_id
                )
            )

            session.execute(
                delete(SbomRecord).where(
                    SbomRecord.scan_id == scan_id
                )
            )

        print("Temporary test data cleaned up.")


if __name__ == "__main__":
    main()