import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.scan_queue import ScanQueueError, enqueue_scan


def test_queue_requires_worker_task_name(monkeypatch):
    monkeypatch.delenv("SCAN_TASK_NAME", raising=False)
    with pytest.raises(ScanQueueError, match="not configured"):
        enqueue_scan(uuid4())


def test_queue_dispatches_only_scan_id(monkeypatch):
    sent = []

    class FakeCelery:
        def __init__(self, name, broker):
            assert name == "banana-chain-api"
            assert broker == "redis://127.0.0.1:6379/0"
            self.conf = SimpleNamespace(update=lambda **kwargs: None)

        def send_task(self, name, args):
            sent.append((name, args))

    monkeypatch.setenv("SCAN_TASK_NAME", "banana.scan.run")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setitem(sys.modules, "celery", SimpleNamespace(Celery=FakeCelery))
    scan_id = uuid4()
    enqueue_scan(scan_id)
    assert sent == [("banana.scan.run", [str(scan_id)])]


def test_queue_wraps_broker_failure(monkeypatch):
    class BrokenCelery:
        def __init__(self, *_args, **_kwargs):
            self.conf = SimpleNamespace(update=lambda **kwargs: None)

        def send_task(self, *_args, **_kwargs):
            raise ConnectionError("broker is down")

    monkeypatch.setenv("SCAN_TASK_NAME", "banana.scan.run")
    monkeypatch.setitem(sys.modules, "celery", SimpleNamespace(Celery=BrokenCelery))
    with pytest.raises(ScanQueueError, match="publish"):
        enqueue_scan(uuid4())
