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

import run_syft
import vulns
from app.schemas import ScanContext
from app.services.clone import CloneError, clone_repo

app = FastAPI(title="Banana Chain: Supply Chain Risk Detector")
templates = Jinja2Templates(directory="templates")

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
    # Browsers send an emtpy "file" when nothing was picked, so filter those out

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
                ctx = ScanContext(scan_id=scan_id, repo_url=url, workspace_path=tmp_dir / str(scan_id))
                clone_repo(ctx)
            except ValidationError: 
                return error_page(request, "Enter a valid GitHub repo URL, like https://github.com/owner/repo.")
            except (CloneError) as e:
                print("Clone failed:", e)
                return error_page(request, e.message)
        try:
            sbom = run_syft.generate_sbom(tmp_dir)
        except Exception as e: # noqa: BLE001 - last-resort handler so users see an error page, not a 500
            print("Syft failed:", e)
            return error_page(request, "There was an unforeseen error with one or more of your files.")

        rows, vulns_ok = vulns.build_rows(sbom)
        return templates.TemplateResponse(
            request, "results.html", {"sbom": sbom, "rows": rows, "vulns_ok": vulns_ok}
        )

@app.post("/api/scan")
def api_scan(
    url: Annotated[str | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    files = [f for f in (files or []) if f.filename]
    url = url.strip() if url else None
    scan_id = uuid.uuid4()

    if not url and not files:
        raise HTTPException(400, "Enter a URL or upload files.")
    if url and files:
        raise HTTPException(400, "Choose either a URL or upload files.")

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
                raise HTTPException(400, "Enter a valid GitHub repo URL.") from e
            except CloneError as e:
                print("Clone failed:", e)
                raise HTTPException(e.error_code, e.message) from e
        try:
            sbom = run_syft.generate_sbom(tmp_dir)
        except Exception as e:  
            print("Syft failed:", e)
            raise HTTPException(500, "Syft could not scan these files.") from e

    rows, vulns_ok = vulns.build_rows(sbom)
    return {"component_count": len(rows), "vulns_ok": vulns_ok, "components": rows}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=5000)