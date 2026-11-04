from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import delete, insert
from sqlalchemy.orm import sessionmaker

from app.db.database import get_session_factory
from app.db.models import SbomRecord, ComponentRecord
from app.schemas.component import Component


def save_sbom(
    scan_id: UUID,
    raw_doc: dict[str, Any],
    components: list[Component],
    *,
    session_factory: sessionmaker | None = None,
) -> None:
    """
    Persist a raw CycloneDX SBOM and its normalized components.

    All database changes occur within one transaction.

    Saving the same scan again replaces its previous components
    instead of creating duplicates.
    """

    factory = (
        session_factory
        if session_factory is not None
        else get_session_factory()
    )

    # Automatically commits on success or rolls back on failure.
    with factory.begin() as session:

        existing_sbom = session.get(SbomRecord, scan_id)

        if existing_sbom is None:
            # First time saving this scan.
            session.add(
                SbomRecord(
                    scan_id=scan_id,
                    raw=deepcopy(raw_doc),
                )
            )

            # Insert the parent SBOM before its components.
            session.flush()

        else:
            # Replace the previously stored raw document.
            existing_sbom.raw = deepcopy(raw_doc)

        # Remove previous components for this scan.
        session.execute(
            delete(ComponentRecord).where(
                ComponentRecord.scan_id == scan_id
            )
        )

        # Prepare all normalized components for bulk insertion.
        component_rows = [
            {
                "scan_id": scan_id,
                "name": component.name,
                "version": component.version,
                "purl": component.purl,
                "type": component.type,
                "licenses": list(component.licenses),
                "locations": list(component.locations),
                "source": component.source,
                "confidence": component.confidence.value,
                "properties": [
                    prop.model_dump(mode="json")
                    for prop in component.properties
                ],
            }
            for component in components
        ]

        # Insert all components using one bulk operation.
        if component_rows:
            session.execute(
                insert(ComponentRecord),
                component_rows,
            )