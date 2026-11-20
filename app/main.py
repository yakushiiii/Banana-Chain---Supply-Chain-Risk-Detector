import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from celery.result import AsyncResult
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

import run_syft
import vulns
from app.schemas import ScanContext
from app.services.clone import CloneError, clone_repo
from app.workers.celery_app import celery_app, scan_repository

app = FastAPI(title="Banana Chain: Supply Chain Risk Detector")
templates = Jinja2Templates(directory="templates")
SCAN_UPLOAD_ROOT = Path(tempfile.gettempdir()) / "banana-chain-scans"


def error_page(request: Request, message: str):
    return templates.TemplateResponse(request, "main.html", {"error": message})


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "main.html")


@app.get("/health")
def health():
    return {"api": "ok", "db": "ok"}


@app.post("/results")
def results(
    request: Request,
    url: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    # Keep the server-rendered route synchronous for backwards compatibility.
    files = [f for f in (files or []) if f.filename]
    url = url.strip() if url else None
    scan_id = uuid.uuid4()

    if not url and not files:
        return error_page(request, "Enter a URL or upload files.")
    if url and files:
        return error_page(request, "Choose either a URL or upload files.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        if files:
            for f in files:
                dest = tmp_dir / Path(f.filename).name
                with open(dest, "wb") as out:
                    shutil.copyfileobj(f.file, out)
        else:
            try:
                ctx = ScanContext(
                    scan_id=scan_id,
                    repo_url=url,
                    workspace_path=tmp_dir / str(scan_id),
                )
                clone_repo(ctx)
            except ValidationError:
                return error_page(
                    request,
                    "Enter a valid GitHub repo URL, like https://github.com/owner/repo.",
                )
            except CloneError as e:
                return error_page(request, e.message)

        try:
            sbom = run_syft.generate_sbom(tmp_dir)
        except Exception:
            return error_page(
                request,
                "There was an unforeseen error with one or more of your files.",
            )

        rows, vulns_ok = vulns.build_rows(sbom)
        return templates.TemplateResponse(
            request,
            "results.html",
            {"sbom": sbom, "rows": rows, "vulns_ok": vulns_ok},
        )


def _save_uploads(files: list[UploadFile], scan_id: uuid.UUID) -> Path:
    scan_dir = SCAN_UPLOAD_ROOT / str(scan_id)
    scan_dir.mkdir(parents=True, exist_ok=False)

    try:
        for file in files:
            destination = scan_dir / Path(file.filename or "upload").name
            with destination.open("wb") as out:
                shutil.copyfileobj(file.file, out)
    except Exception:
        shutil.rmtree(scan_dir, ignore_errors=True)
        raise

    return scan_dir


@app.post("/api/scan")
def api_scan(
    url: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    files = [f for f in (files or []) if f.filename]
    url = url.strip() if url else None

    if not url and not files:
        raise HTTPException(400, "Enter a URL or upload files.")

    if url and files:
        raise HTTPException(400, "Choose either a URL or upload files.")

    scan_id = uuid.uuid4()
    upload_dir = _save_uploads(files, scan_id) if files else None

    try:
        task = scan_repository.apply_async(
            args=[
                str(scan_id),
                url,
                str(upload_dir) if upload_dir else None,
            ],
            task_id=str(scan_id),
        )
    except Exception:
        if upload_dir:
            shutil.rmtree(upload_dir, ignore_errors=True)

        raise HTTPException(
            503,
            "The scan queue is unavailable. Please try again.",
        )

    return {
        "scan_id": str(scan_id),
        "task_id": task.id,
        "status": "queued",
    }


@app.get("/api/scan/{task_id}")
def scan_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    meta = result.info if isinstance(result.info, dict) else {}

    if result.state == "PENDING":
        return {
            "task_id": task_id,
            "status": "queued",
        }

    if result.state in {"STARTED", "PROGRESS"}:
        return {
            "task_id": task_id,
            "status": meta.get("status", "running"),
            "phase": meta.get("phase"),
        }

    if result.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "done",
            "result": result.result,
        }

    if result.state == "FAILURE":
        error = meta.get("error") if isinstance(meta, dict) else None

        return {
            "task_id": task_id,
            "status": "failed",
            "error": error or "Scan failed.",
        }

    return {
        "task_id": task_id,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=5000)