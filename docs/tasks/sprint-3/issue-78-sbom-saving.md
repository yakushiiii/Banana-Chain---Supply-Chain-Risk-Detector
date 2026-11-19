# Issue #78 — Faster SBOM saving

## Approach

- `app/services/sbom_persistence.py` uses the canonical `models.py` tables from `main`, not the older `app/db/models.py` experiment.
- All normalized components are inserted with SQLAlchemy ORM bulk inserts, in configurable batches of 500 rows by default. This reduces database calls relative to `session.add()`/`flush()` for each component.
- Raw CycloneDX JSON, the parent SBOM, component replacement, and all inserts use one transaction. A failure rolls back the whole save.
- On repeat saves, rows are replaced under the same SBOM ID; simultaneous repeat saves of an existing SBOM use a row lock.
- The canonical DB schema already has `ix_components_sbom_id`, `ix_components_purl`, and `uq_components_sbom_id_purl`, created by migration `2c3ac1a5f246_initial_schema.py`. Adding duplicate indexes would increase write overhead and is not needed.
- The `Component` schema's categorical confidence cannot be stored in the existing `components.confidence` float column without an explicit scoring policy. Source, category and locations are preserved in `properties`; raw CycloneDX JSON is retained unchanged.

## Test instructions

1. Use only the dedicated disposable `banana_test` PostgreSQL database. The shared pytest `engine` fixture runs migrations and downgrades.
2. `python -m pytest tests/test_sbom_bulk_persistence.py -q --maxfail=1 --tb=short`
3. `python -m pytest -q --maxfail=1 --tb=short`

The tests cover row counts, raw JSON, repeat-save idempotency, rollback on duplicate PURL, batched SQL statements for 1,200 components, and existing DB indexes.

## Integration caveat

The existing `main` pipeline does not yet contain an active call to the persistence service. Issue #78 implements and tests the database write path; the scan worker / pipeline must call `save_sbom(...)` after normalization for end-to-end persistence.

## Benchmarking

The batch-count test proves the implementation avoids one INSERT call per component, but does not establish a precise wall-clock speedup. Measure representative 1k–10k-component SBOMs against the previous row-by-row approach on comparable PostgreSQL environments before claiming a measured improvement.
