"""Issue #72: API exposes the complete, unmodified CycloneDX SBOM for download."""

from fastapi.testclient import TestClient

from app.main import app


def test_scan_returns_original_cyclonedx_document(monkeypatch):
    from app import main

    sample_sbom = {
        "$schema": "http://cyclonedx.org/schema/bom-1.7.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": "urn:uuid:4c6f4b8b-94de-4d87-8b14-2c77f186961a",
        "metadata": {"component": {"type": "application", "name": "sample-app"}},
        "components": [
            {"type": "library", "name": "requests", "version": "2.32.0",
             "purl": "pkg:pypi/requests@2.32.0"},
        ],
        "dependencies": [{"ref": "pkg:pypi/requests@2.32.0"}],
    }
    monkeypatch.setattr(main.run_syft, "generate_sbom", lambda _path: sample_sbom)
    monkeypatch.setattr(main.vulns, "build_rows", lambda _sbom: ([], True))

    with TestClient(app) as client:
        response = client.post(
            "/api/scan", files={"files": ("requirements.txt", b"requests==2.32.0")}
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sbom"] == sample_sbom
    assert payload["sbom"]["bomFormat"] == "CycloneDX"
    assert payload["sbom"]["specVersion"] == "1.7"
    assert payload["components"] == []  # UI summary remains unchanged.
    assert payload["vulns_ok"] is True
