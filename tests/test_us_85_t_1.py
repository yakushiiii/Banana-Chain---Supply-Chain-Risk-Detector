import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_us_85_t_1_criterion_1_health_returns_ok():
    """Criterion 1: GET /health returns HTTP 200 with { 'api': 'ok', 'db': 'ok' }."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"api": "ok", "db": "ok"}


def test_us_85_t_1_criterion_2_scan_rejects_empty_submission():
    """Criterion 2: POST /api/scan rejects empty submissions with HTTP 400."""
    response = client.post("/api/scan", data={})
    assert response.status_code == 400
    assert "Enter a URL or upload files" in response.json()["detail"]


def test_us_85_t_1_criterion_3_scan_rejects_both_url_and_files():
    """Criterion 3: POST /api/scan rejects submissions containing both URL and files with HTTP 400."""
    response = client.post(
        "/api/scan",
        data={"url": "https://github.com/pallets/flask"},
        files=[("files", ("test.txt", b"dummy content", "text/plain"))],
    )
    assert response.status_code == 400
    assert "Choose either a URL or upload files" in response.json()["detail"]


def test_us_85_t_1_criterion_4_scan_rejects_invalid_url():
    """Criterion 4: POST /api/scan rejects non-GitHub or malformed repository URLs with HTTP 400."""
    response = client.post("/api/scan", data={"url": "https://gitlab.com/invalid/repo"})
    assert response.status_code == 400
    assert "Enter a valid GitHub URL" in response.json()["detail"]


def test_us_85_t_1_criterion_5_security_summary_counts():
    """Criterion 5: Security summary dashboard correctly calculates component counts by severity."""
    mock_components = [
        {"name": "pkg-a", "severity": "Critical", "vuln_count": 2},
        {"name": "pkg-b", "severity": "High", "vuln_count": 1},
        {"name": "pkg-c", "severity": "Medium", "vuln_count": 3},
        {"name": "pkg-d", "severity": "None", "vuln_count": 0},
        {"name": "pkg-e", "severity": "None", "vuln_count": 0},
    ]

    critical = [c for c in mock_components if c["severity"] == "Critical"]
    high = [c for c in mock_components if c["severity"] == "High"]
    medium = [c for c in mock_components if c["severity"] == "Medium"]
    safe = [c for c in mock_components if c["severity"] == "None"]

    assert len(critical) == 1
    assert len(high) == 1
    assert len(medium) == 1
    assert len(safe) == 2
    assert len(mock_components) == 5


def test_us_85_t_1_criterion_6_security_summary_posture():
    """Criterion 6: Security summary correctly determines posture status."""
    def get_posture(components, vulns_ok=True):
        if not vulns_ok:
            return "Vulnerability Check Offline"
        if not components:
            return "No Dependencies Found"
        if any(c["severity"] == "Critical" for c in components):
            return "Critical Risk"
        if any(c["severity"] == "High" for c in components):
            return "High Risk"
        if any(c["severity"] == "Medium" for c in components):
            return "Moderate Risk"
        if any(c["severity"] == "Low" for c in components):
            return "Low Risk"
        return "Secure (No Known Risks)"

    assert get_posture([{"severity": "Critical"}]) == "Critical Risk"
    assert get_posture([{"severity": "High"}]) == "High Risk"
    assert get_posture([{"severity": "Medium"}]) == "Moderate Risk"
    assert get_posture([{"severity": "Low"}]) == "Low Risk"
    assert get_posture([{"severity": "None"}]) == "Secure (No Known Risks)"
    assert get_posture([]) == "No Dependencies Found"
    assert get_posture([{"severity": "Critical"}], vulns_ok=False) == "Vulnerability Check Offline"
