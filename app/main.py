import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app import run_grype, run_syft
from app.schemas import ScanContext
from app.services.clone import CloneError, clone_repo

app = FastAPI(title="Banana Chain: Supply Chain Risk Detector")
templates = Jinja2Templates(directory="templates")


class ScanError(Exception):
    """Something went wrong during a scan."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def scan_project(url: str | None, files: list[UploadFile] | None) -> tuple[dict, list[dict]]:
    """Shared by /results and /api/scan: save or clone, run Syft, run Grype.

    Returns (sbom, findings). Raises ScanError with a user-friendly message.
    """
    # Browsers send an empty "file" when nothing was picked, so filter those out
    files = [f for f in (files or []) if f.filename]
    url = url.strip() if url else None
    scan_id = uuid.uuid4()

    if not url and not files:
        raise ScanError("Enter a URL or upload files.", 400)
    if url and files:
        raise ScanError("Choose either a URL or upload files.", 400)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        if files:
            for f in files:
                dest = tmp_dir / Path(f.filename).name
                with open(dest, "wb") as out:
                    shutil.copyfileobj(f.file, out)
        else:
            try:
                ctx = ScanContext(scan_id=scan_id, repo_url=url, workspace_path=tmp_dir / str(scan_id))
                clone_repo(ctx)
            except ValidationError as e:
                raise ScanError(
                    "Enter a valid GitHub repo URL, like https://github.com/owner/repo.", 400
                ) from e
            except CloneError as e:
                print("Clone failed:", e)
                raise ScanError(e.message, e.error_code) from e

        try:
            sbom = run_syft.generate_sbom(tmp_dir)
        except Exception as e:  # noqa: BLE001 - last-resort handler so users see an error page, not a 500
            print("Syft failed:", e)
            raise ScanError("There was an unforeseen error with one or more of your files.") from e

        try:
            findings = run_grype.scan_sbom(sbom)
        except run_grype.GrypeError as e:
            print("Grype failed:", e)
            raise ScanError("We couldn't check this project for vulnerabilities. Please try again.") from e

    return sbom, findings


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
    try:
        sbom, findings = scan_project(url, files)
    except ScanError as e:
        return error_page(request, e.message)

    rows = run_grype.rows_from_findings(sbom, findings)
    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "sbom": sbom,
            "rows": rows,
            "vulns_ok": True,  # Grype failures return an error page, so reaching here means it worked
            "vulns": findings,
            "findings_text": run_grype.format_findings(findings),
        },
    )


@app.post("/api/scan")
def api_scan(
    url: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    try:
        sbom, findings = scan_project(url, files)
    except ScanError as e:
        raise HTTPException(e.status_code, e.message) from e

    rows = run_grype.rows_from_findings(sbom, findings)
    return {
        "component_count": len(rows),
        "vulns_ok": True,
        "components": rows,
        "findings": findings,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=5000)