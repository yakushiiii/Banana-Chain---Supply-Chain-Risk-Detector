# Issue #34: Scan API endpoints

## API contract

`POST /scans` accepts **JSON** `{"repo_url":"https://github.com/owner/repo"}`.
The repository URL must be a HTTPS `github.com` URL with exactly an owner and
repository path. Variants with `.git`, different case, or a trailing slash are
canonicalized so the same repository is stored as one Project. A missing URL,
invalid domain, non-repo path, malformed URL, etc. returns **422**.

The endpoint finds or creates `Project`, creates **one new** `Scan(status=queued)`
per request, commits it, publishes the scan UUID to a Celery broker, and returns
**202** with `{ "scan_id": "<UUID>", "status": "queued" }`. The queue operation
must happen after the DB commit so the worker can immediately query it.
Concurrent first submissions are protected by `projects.repo_url`'s unique
constraint and a SQLAlchemy savepoint.

`GET /scans/{scan_id}` returns `ScanRead` with:
- `scan_id`, `status`, and canonical `repo_url`
- `created_at`, `completed_at`, and `error_message`
- `component_count`: **0 while queued/running**; after completing, the count
  of components in the persisted SBOM; **partial** scans also return saved
  component counts (once Issue #37 is merged).

Existing persisted `running` and `succeeded` statuses are mapped to
`scanning` and `completed` respectively for API compatibility until the worker
uses the detailed statuses. Newer #37 statuses remain unchanged. Unknown UUIDs
return **404**; malformed UUID paths return FastAPI's **422**. The preexisting
`/api/scan` multipart endpoint continues handling file uploads unchanged.

## Background worker integration (Issue #33)

The endpoint **publishes** the scan UUID to Celery but deliberately does not
implement the scan worker (tracked in Issue #33). Do not claim a scan can reach
`completed` until Issue #33 has registered the worker and it is running. A
successfully published task can still be unconsumed when no worker is running.

Install the root dependencies (includes `celery[redis]`) and configure these
environment variables **before** starting Uvicorn:

```powershell
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_PASSWORD = Read-Host "Enter PostgreSQL password"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:SCAN_TASK_NAME = "the.registered.worker.task.name"
python -m uvicorn app.main:app --port 5000
```

**`SCAN_TASK_NAME` must exactly match** the Celery task name registered by
Issue #33. The task should accept a single positional string argument with the
scan UUID and look up the Scan in PostgreSQL. When that name isn't configured,
or the broker cannot be reached, `POST /scans` responds **503** and marks its
created Scan as `failed` with an error. The queue adapter cannot verify worker
registration at publish time.

## Local tests

The HTTP/queue tests use a disposable SQLite ORM simulation and fake the
queue, so they don't require Redis or Syft:

```powershell
python -m pytest tests/test_scan_api.py tests/test_scan_queue.py -q
```

Run the existing PostgreSQL tests **only on a disposable, isolated `banana_test`
database**; the fixture runs Alembic downgrade to `base` at teardown:

```powershell
python -m pytest tests/test_models.py -q
```

Run end-to-end only after Redis + the Issue #33 worker are online:

```powershell
curl.exe -i -X POST http://127.0.0.1:5000/scans -H "Content-Type: application/json" -d '{"repo_url":"https://github.com/psf/requests"}'
# Replace <uuid> with the POST response's scan_id.
curl.exe -i http://127.0.0.1:5000/scans/<uuid>
```

On PowerShell, `Invoke-RestMethod` is also convenient:

```powershell
$scan = Invoke-RestMethod -Uri http://127.0.0.1:5000/scans -Method Post `
  -ContentType application/json -Body '{"repo_url":"https://github.com/psf/requests"}'
Invoke-RestMethod -Uri "http://127.0.0.1:5000/scans/$($scan.scan_id)"
```

## Frontend OpenAPI types

After starting FastAPI and installing the frontend dependencies:

```powershell
cd frontend
npm install
npm run gen:api
```

The new `gen:api` uses a Node script instead of the old Bash-only variable
expansion, so it works in Windows PowerShell. `frontend/vite.config.ts` now
proxies `/scans` in development. This issue does **not** change the existing
frontend's synchronous `/api/scan` user flow; switching the user interface to
async polling requires a separate frontend integration.

## Risks / future work

- Workers must acknowledge and update scan lifecycle and persist SBOMs as
  defined by #33; `202` only confirms queue publication, not scan completion.
- No remote GitHub availability test occurs at POST time. A syntactically
  valid URL may be private, nonexistent, or too large; the worker must record
  such failures in `Scan.error_message` and update status to `failed`.
- Queue publication and a database commit are separate operations; a process
  crash between them can leave a scan in `queued`. Durable outbox/repair may
  be added in a follow-up. Broker publish acknowledgments are not worker ACKs.
