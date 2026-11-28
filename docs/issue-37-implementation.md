# Issue #37 — implementation and local verification

This work was built from the user's exported `origin/main` archive. It extends,
rather than edits, the existing Alembic baseline `2c3ac1a5f246`.

## Contents

- `models.py`: cache, component advisory matches, scan findings, EPSS history,
  component risk metadata, expanded scan statuses. Foreign keys use the existing
  UUID and OSV string key types.
- `migrations/versions/41e37a6d9c20_vulnerability_schema.py`: reversible
  PostgreSQL migration; status constraint is plain VARCHAR + CHECK.
- `app/schemas/vulnerability.py`: response contracts matching the database.
- `app/schemas/__init__.py`, `app/schemas/scan.py`: public exports and statuses.
- `docs/adr/0002-vulnerability-contract.md`: **proposed**, requires owner review.
- `docs/api-examples/`: hand-authored mock JSON response shapes.
- `tests/test_vulnerability_contract.py`: standalone Pydantic tests.
- `tests/test_vulnerability_db.py`: DB insert/read, constraints, cascade, EPSS,
  migration downgrade/upgrade, no-drift.

## Important test database warning

The existing `tests/conftest.py` runs `alembic upgrade head` at test setup
and `alembic downgrade base` on teardown. Do **not** run model tests against
`sbom_db`, development data or production. Use a separate, disposable
`banana_test` database only. Ensure your environment variables or `.env`
point to your actual local PostgreSQL port/user/password. `POSTGRES_DB` may
remain the development DB because `conftest.py` explicitly selects
`banana_test`, but check the effective URL before executing database tests.

## Apply and run (PowerShell in repository root)

```powershell
# Create your feature branch before applying the patch.
git switch main
git pull --ff-only origin main
git switch -c feature/37-vulnerability-schema

# Copy the changed files from the ZIP into the repository root,
# or apply the supplied .patch from this repository root.
git apply --check .\BananaChain-Issue37.patch
git apply .\BananaChain-Issue37.patch

# If your actual main has changed since the archive, resolve conflicts
# rather than overwriting newer teammate changes.
python -m pytest tests/test_schemas.py tests/test_vulnerability_contract.py -q

# Verify banana_test really is disposable and that credentials work first.
python -c "from settings import settings; from sqlalchemy.engine import make_url; u=make_url(settings.make_url('banana_test')); print(u.host, u.port, u.database, u.username)"

# Against the isolated banana_test database only:
python -m pytest tests/test_models.py tests/test_vulnerability_db.py -q --maxfail=1 --tb=short

# Check both sets of tests together as the final confidence step.
python -m pytest tests -q --maxfail=1 --tb=short
```

`test_models.py` already performs a `base -> head` migration round trip;
`test_vulnerability_db.py` additionally tests `head -> -1 -> head`.

## Owner review before merge

1. Hold and record the required 30-minute backend/pipeline/frontend contract
   session. Agree on severity/score policy, CVE-to-OSV EPSS alias handling,
   UUID serialization, planned response routes, and what `partial` means.
2. Replace the **pending** placeholders in ADR 0002 with actual approval and
   decisions; update models, examples and tests if those decisions change.
3. Ask the frontend owner to confirm JSON mock shapes and null risk handling.
4. Confirm that `git status` shows only intentional Issue #37 changes. Never
   commit `.env`, PostgreSQL passwords, generated caches, or a test DB dump.

**Not in scope:** live OSV enrichment, EPSS fetch jobs, scoring algorithm,
API endpoints and Celery worker tasks; the new models are their contracts.
