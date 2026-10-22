import re, subprocess, tempfile, uuid, shutil
import run_syft
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="Banana Chain: Supply Chain Risk Detector")
templates = Jinja2Templates(directory="templates")

GITHUB_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+?(\.git)?/?$")

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

    if not url and not files:
        return error_page(request, "Enter a URL or upload files.")
    if url and files:
        return error_page(request, "Choose either a URL or upload files.")
    if url and not GITHUB_RE.match(url):
        return error_page(request, "Enter a valid URL or upload files.")



    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        if files:
            for f in files:
                dest = tmp_dir / Path(f.filename).name
                with open(dest, "wb") as out:
                    shutil.copyfileobj(f.file, out)
        else:
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(tmp_dir / "repo")],
                    check=True, timeout=60,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print("Clone failed:", e)
                return error_page(request, "There was an error with your respository. Must use a public repository, if repository must remain private try uploading project files instead.")
        try:
            sbom = run_syft.generate_sbom(tmp_dir)
        except Exception as e:
            print("Syft failed:", e)
            return error_page(request, "There was an unforeseen error with one or more of your files.")
        
        return templates.TemplateResponse(request, "results.html", {"sbom": sbom})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=5000)