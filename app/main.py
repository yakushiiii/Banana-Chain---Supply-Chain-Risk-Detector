import tempfile, uuid, shutil
import run_syft
from pathlib import Path
from app.schemas import ScanContext
from app.services.clone import clone_repo, CloneError

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError

app = FastAPI(title="Banana Chain: Supply Chain Risk Detector")
templates = Jinja2Templates(directory="templates")

def error_page(request: Request, message: str):
    return templates.TemplateResponse(request, "main.html", {"error": message})

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "main.html")

@app.post("/results")
def results(
    request: Request,
    url: str | None = Form(None),
    files: list[UploadFile] = File([])
    ):
    # Browsers send an emtpy "file" when nothing was picked, so filter those out

    files = [f for f in files if f.filename]
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
        except Exception as e:
            print("Syft failed:", e)
            return error_page(request, "There was an unforeseen error with one or more of your files.")

        return templates.TemplateResponse(request, "results.html", {"sbom": sbom})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=5000)