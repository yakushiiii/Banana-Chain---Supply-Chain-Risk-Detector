from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_us_85_t_1_health_returns_ok():
    """US-85-T-1: Verify that GET /health returns HTTP 200 and health status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"api": "ok", "db": "ok"}
