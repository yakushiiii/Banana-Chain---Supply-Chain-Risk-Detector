
from unittest.mock import Mock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_us_80_t_1_scan_submission_returns_queued(monkeypatch):
    task = Mock(id=str(uuid4()))

    monkeypatch.setattr(
        "app.main.scan_repository.apply_async",
        lambda **kwargs: task,
    )

    response = client.post(
        "/api/scan",
        data={"url": "https://github.com/pallets/flask"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["task_id"] == task.id
    assert data["status"] == "queued"
    assert "scan_id" in data
    UUID(data["scan_id"])


def test_us_80_t_1_scan_status_maps_pending_to_queued(monkeypatch):
    pending = Mock()
    pending.state = "PENDING"
    pending.info = None

    monkeypatch.setattr(
        "app.main.AsyncResult",
        lambda *args, **kwargs: pending,
    )

    response = client.get("/api/scan/test-task-id")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_us_80_t_1_scan_status_maps_started_to_running(monkeypatch):
    running = Mock()
    running.state = "STARTED"
    running.info = {"phase": "scanning"}

    monkeypatch.setattr(
        "app.main.AsyncResult",
        lambda *args, **kwargs: running,
    )

    response = client.get("/api/scan/test-task-id")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_us_80_t_1_scan_status_maps_success_to_done(monkeypatch):
    result = {
        "component_count": 1,
        "vulns_ok": True,
        "components": [],
    }

    success = Mock()
    success.state = "SUCCESS"
    success.info = result
    success.result = result

    monkeypatch.setattr(
        "app.main.AsyncResult",
        lambda *args, **kwargs: success,
    )

    response = client.get("/api/scan/test-task-id")

    assert response.status_code == 200
    assert response.json()["status"] == "done"
    assert response.json()["result"] == result


def test_us_80_t_1_scan_status_maps_failure_to_failed(monkeypatch):
    failure = Mock()
    failure.state = "FAILURE"
    failure.info = Exception("Repository scan failed")

    monkeypatch.setattr(
        "app.main.AsyncResult",
        lambda *args, **kwargs: failure,
    )

    response = client.get("/api/scan/test-task-id")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
