import re, subprocess, tempfile, uuid
import run_syft
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Banana Chain: Supply Chain Risk Detector")

@app.get("/")
async def root():
    return send_file("index.html")

@app.post("/api/sbom")
def sbom():
    
    #repo_url = body.get("repo_url", "")
    if "file" in request.files or not repo_url.startswith("https://github.com/"):
        return jsonify({"error": "no file uploaded"}), 400

    upload = request.files["file"]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "upload")
        upload.save(path)
        try:
            sbom = run_syft.generate_sbom(path)
        except Exception:
            return jsonify({"error": "could not read file"}), 500

    return jsonify(sbom)

if __name__ == "__main__":
    app.run(port=5000)