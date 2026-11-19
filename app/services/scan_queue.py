"""Celery queue adapter; implementation of the scan task belongs to worker #33."""

import os
from uuid import UUID


class ScanQueueError(Exception):
    """The scan job could not be handed to the queue."""


def enqueue_scan(scan_id: UUID) -> None:
    """Publish the scan ID, not an entire ORM object, to the configured worker.

    The worker must register SCAN_TASK_NAME and load its data from PostgreSQL.
    A successful publish does not mean a worker has completed the job.
    """
    task_name = os.environ.get("SCAN_TASK_NAME")
    if not task_name:
        raise ScanQueueError("SCAN_TASK_NAME is not configured")

    try:
        from celery import Celery

        celery = Celery(
            "banana-chain-api",
            broker=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        )
        celery.conf.update(
            broker_connection_timeout=3,
            broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
            task_publish_retry=False,
        )
        celery.send_task(task_name, args=[str(scan_id)])
    except Exception as exc:
        raise ScanQueueError("Could not publish the scan job") from exc
