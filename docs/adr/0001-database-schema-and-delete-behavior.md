# ADR 0001: Database schema and delete behavior

## Status
Accepted

## Context
We store projects, scans, SBOMs and components in PostgreSQL. We need a rule for what
happens to child rows when a parent is deleted.

## Decision
Use ON DELETE CASCADE on every foreign key:
projects -> scans -> sboms -> components.

- Scans, SBOMs and components are derived data. A scan can be re-run, so losing
  them with their project is acceptable.
- Cascading avoids orphaned rows and keeps cleanup to a single DELETE.
- The ORM uses passive_deletes=True so Postgres does the work.

## Alternatives considered
RESTRICT: safer against accidental deletes, but every cleanup needs manual
ordered deletes. We may switch projects -> scans to RESTRICT (or soft deletes)
later if scan history becomes something users want to keep.

## Other schema choices
- UUID primary keys (gen_random_uuid()).
- Unique (sbom_id, purl) WHERE purl IS NOT NULL: no duplicate packages per SBOM,
  while components without a purl are still allowed.
- Scan status is text + CHECK constraint, not a native enum, to keep migrations simple.
- All schema changes go through Alembic migrations.