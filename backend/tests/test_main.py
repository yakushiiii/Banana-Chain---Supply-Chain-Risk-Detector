from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_home_page_loads():
    response = client.get("/")
    assert response.status_code == 200


def test_results_requires_url_or_files():
    response = client.post("/results", data={})
    assert response.status_code == 200
    assert "Enter a URL or upload files." in response.text