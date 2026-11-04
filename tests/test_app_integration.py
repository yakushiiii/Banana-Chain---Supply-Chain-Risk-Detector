
import json
from pathlib import Path

from fastapi.testclient import TestClient

from importlib import import_module

app_module = import_module("app.main")


def test_results_normalization_and_raw_sbom(monkeypatch):
    """Verify FastAPI displays normalized data and preserves raw SBOM."""

    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "requests.cdx.json"
    )

    raw_sbom = json.loads(
        fixture_path.read_text(encoding="utf-8")
    )

    assert len(raw_sbom["components"]) == 31

    def fake_generate_sbom(path):
        return raw_sbom

    monkeypatch.setattr(
        app_module.run_syft,
        "generate_sbom",
        fake_generate_sbom
    )

    with TestClient(app_module.app) as client:
        response = client.post(
            "/results",
            files={
                "files": (
                    "example.txt",
                    b"example test content",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")

    assert "23 unique components found" in response.text
    assert "(31 raw SBOM entries)" in response.text

    assert "<td>repo/requirements-dev.txt</td>" in response.text

    marker = "const sbom ="
    assert marker in response.text

    embedded_json = response.text.split(marker, 1)[1].lstrip()

    downloaded_sbom, _ = json.JSONDecoder().raw_decode(
        embedded_json
    )

    assert downloaded_sbom == raw_sbom
