import os
import shutil
import tempfile
from pathlib import Path

from celery import Celery

import run_syft
import vulns
from app.schemas import ScanContext
from app.services.clone import CloneError, clone_repo


celery_app = Celery(
    "banana_chain",
    broker=os.getenv(
        "CELERY_BROKER_URL",
        "redis://127.0.0.1:6379/0",
    ),
    backend=os.getenv(
        "CELERY_RESULT_BACKEND",
        "redis://127.0.0.1:6379/1",
    ),
)


celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=int(
        os.getenv("CELERY_SOFT_TIME_LIMIT", "300")
    ),
    task_time_limit=int(
        os.getenv("CELERY_HARD_TIME_LIMIT", "360")
    ),
)


def _status(task, status: str, **extra):
    task.update_state(
        state="PROGRESS",
        meta={
            "status": status,
            **extra,
        },
    )


@celery_app.task(bind=True, name="scan_repository")
def scan_repository(
    self,
    scan_id: str,
    repo_url: str | None,
    upload_dir: str | None,
):
    """Run the scan away from the HTTP request and publish coarse progress states."""

    try:
        _status(
            self,
            "running",
            scan_id=scan_id,
        )

        with tempfile.TemporaryDirectory(
            prefix=f"scan-{scan_id}-"
        ) as tmp:
            tmp_dir = Path(tmp)

            if repo_url:
                _status(
                    self,
                    "running",
                    phase="cloning",
                    scan_id=scan_id,
                )

                ctx = ScanContext(
                    scan_id=scan_id,
                    repo_url=repo_url,
                    workspace_path=tmp_dir / "repo",
                )

                clone_repo(ctx)

            else:
                _status(
                    self,
                    "running",
                    phase="preparing",
                    scan_id=scan_id,
                )

                source = Path(upload_dir or "")

                if not source.is_dir():
                    raise RuntimeError(
                        "Uploaded scan files are no longer available."
                    )

                for item in source.iterdir():
                    destination = tmp_dir / item.name

                    if item.is_dir():
                        shutil.copytree(
                            item,
                            destination,
                        )
                    else:
                        shutil.copy2(
                            item,
                            destination,
                        )

            _status(
                self,
                "running",
                phase="scanning",
                scan_id=scan_id,
            )

            sbom = run_syft.generate_sbom(tmp_dir)

            _status(
                self,
                "running",
                phase="analyzing",
                scan_id=scan_id,
            )

            rows, vulns_ok = vulns.build_rows(sbom)

        if upload_dir:
            shutil.rmtree(
                upload_dir,
                ignore_errors=True,
            )

        result = {
            "scan_id": scan_id,
            "component_count": len(rows),
            "vulns_ok": vulns_ok,
            "components": rows,
        }

        _status(
            self,
            "done",
            scan_id=scan_id,
        )

        return result

    except Exception as exc:
        if upload_dir:
            shutil.rmtree(
                upload_dir,
                ignore_errors=True,
            )

        self.update_state(
            state="FAILURE",
            meta={
                "status": "failed",
                "scan_id": scan_id,
                "error": str(exc),
            },
        )

        raise