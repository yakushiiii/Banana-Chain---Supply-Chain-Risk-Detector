from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_scan_submission_returns_queued(monkeypatch):
    task = Mock(id=str(uuid4()))
    monkeypatch.setattr("app.main.scan_repository.apply_async", lambda **kwargs: task)

    response = client.post("/api/scan", data={"url": "https://github.com/pallets/flask"})

    assert response.status_code == 200
    assert response.json() == {
        "scan_id": task.id,
        "task_id": task.id,
        "status": "queued",
    }


def test_scan_status_maps_pending_to_queued(monkeypatch):
    class Pending:
        state = "PENDING"
        info = None

    monkeypatch.setattr("app.main.AsyncResult", lambda *args, **kwargs: Pending())
    response = client.get("/api/scan/task-1")
    assert response.json() == {"task_id": "task-1", "status": "queued"}


def test_scan_status_maps_progress_to_running(monkeypatch):
    class Progress:
        state = "PROGRESS"
        info = {"status": "running", "phase": "scanning"}

    monkeypatch.setattr("app.main.AsyncResult", lambda *args, **kwargs: Progress())
    response = client.get("/api/scan/task-1")
    assert response.json() == {
        "task_id": "task-1",
        "status": "running",
        "phase": "scanning",
    }


def test_scan_status_maps_success_to_done(monkeypatch):
    result = {"component_count": 1, "vulns_ok": True, "components": []}

    class Success:
        state = "SUCCESS"
        info = result
        result = result

    monkeypatch.setattr("app.main.AsyncResult", lambda *args, **kwargs: Success())
    response = client.get("/api/scan/task-1")
    assert response.json() == {"task_id": "task-1", "status": "done", "result": result}


def test_scan_status_maps_failure_to_failed(monkeypatch):
    class Failed:
        state = "FAILURE"
        info = {"status": "failed", "error": "Syft failed"}

    monkeypatch.setattr("app.main.AsyncResult", lambda *args, **kwargs: Failed())
    response = client.get("/api/scan/task-1")
    assert response.json() == {"task_id": "task-1", "status": "failed", "error": "Syft failed"}
