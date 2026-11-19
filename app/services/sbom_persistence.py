"""Transactional, batched persistence of a normalized CycloneDX SBOM.

Uses the shared SQLAlchemy models from ``models.py`` (not the obsolete
``app.db.models`` models from the earlier persistence experiment).
"""

from collections.abc import Iterator, Mapping, Sequence
from copy import deepcopy
from functools import lru_cache
from itertools import islice
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, delete, insert, select
from sqlalchemy.orm import sessionmaker

from app.schemas.component import Component as NormalizedComponent
from models import Component as ComponentRow
from models import Sbom

DEFAULT_BATCH_SIZE = 500


@lru_cache(maxsize=1)
def _default_session_factory() -> sessionmaker:
    """Reuse the connection pool across scans; don't create an engine per save."""
    from settings import settings

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)


def _component_row(component: NormalizedComponent, sbom_id: UUID) -> dict[str, Any]:
    """Convert a normalized component to the current DB column layout.

    The normalized schema has categorical confidence, source and locations,
    whereas the DB confidence column expects a float. Retain those values as
    JSON properties rather than inventing a numeric confidence score.
    """
    properties = [prop.model_dump(mode="json") for prop in component.properties]
    properties.extend(
        (
            {"name": "banana:source", "value": component.source},
            {"name": "banana:confidence", "value": component.confidence.value},
        )
    )
    properties.extend(
        {"name": "banana:location", "value": location}
        for location in component.locations
    )
    return {
        "sbom_id": sbom_id,
        "name": component.name,
        "version": component.version,
        "purl": component.purl,
        "type": component.type,
        "licenses": list(component.licenses),
        "confidence": None,
        "properties": properties,
    }


def _batches(rows: Iterator[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    while batch := list(islice(rows, size)):
        yield batch


def save_sbom(
    scan_id: UUID,
    raw_doc: Mapping[str, Any],
    components: Sequence[NormalizedComponent],
    *,
    session_factory: sessionmaker | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> UUID:
    """Save one CycloneDX document and all its components in one transaction.

    The scan must already exist. A repeat save replaces the scan's component
    set instead of duplicating it. PostgreSQL's unique (sbom_id, purl) index
    protects against duplicate non-null PURLs in a single save; normalized
    components should be deduplicated before calling this function.

    Returns the persistent SBOM ID. A failed insert rolls back the raw JSON,
    delete, and all batches together. Each batch is one ORM bulk INSERT.
    """
    if not isinstance(raw_doc, Mapping) or raw_doc.get("bomFormat") != "CycloneDX":
        raise ValueError("Expected a CycloneDX document")
    spec_version = raw_doc.get("specVersion")
    if not isinstance(spec_version, str) or not spec_version:
        raise ValueError("CycloneDX specVersion is required")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    factory = session_factory if session_factory is not None else _default_session_factory()
    with factory.begin() as session:
        # Lock the existing parent row to serialize repeat saves of a scan.
        sbom = session.scalar(select(Sbom).where(Sbom.scan_id == scan_id).with_for_update())
        if sbom is None:
            sbom = Sbom(scan_id=scan_id, spec_version=spec_version, raw=deepcopy(dict(raw_doc)))
            session.add(sbom)
            session.flush()
        else:
            sbom.spec_version = spec_version
            sbom.raw = deepcopy(dict(raw_doc))
            session.flush()

        session.execute(delete(ComponentRow).where(ComponentRow.sbom_id == sbom.id))
        rows = (_component_row(component, sbom.id) for component in components)
        for batch in _batches(rows, batch_size):
            session.execute(insert(ComponentRow), batch)

        return sbom.id
