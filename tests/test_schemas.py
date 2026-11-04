
import pytest
from pydantic import ValidationError
from pathlib import Path
from uuid import uuid4

from app.schemas.scan import ScanCreate, ScanRead
from app.schemas.context import ScanContext

from app.schemas.scan import ScanStatus
from app.schemas.component import (
    Component,
    Confidence,
    ComponentProperty,
)


def test_scan_status_values():
    assert {status.value for status in ScanStatus} == {
        "queued",
        "cloning",
        "scanning",
        "normalizing",
        "persisting",
        "completed",
        "failed",
    }


def test_component_required_fields():
    with pytest.raises(ValidationError):
        Component(name="requests", type="library")

    with pytest.raises(ValidationError):
        Component(name="requests", source="syft")

    with pytest.raises(ValidationError):
        Component(type="library", source="syft")


def test_component_defaults():
    component = Component(
        name="requests",
        type="library",
        source="syft",
    )

    assert component.version is None
    assert component.purl is None
    assert component.licenses == []
    assert component.locations == []
    assert component.properties == []
    assert component.confidence == Confidence.DECLARED


def test_component_confidence_validation():
    component = Component(
        name="requests",
        type="library",
        source="syft",
        confidence="observed",
    )

    assert component.confidence == Confidence.OBSERVED

    with pytest.raises(ValidationError):
        Component(
            name="requests",
            type="library",
            source="syft",
            confidence="unknown",
        )

def test_component_metadata():
    component = Component(
        name="requests",
        version="2.31.0",
        type="library",
        source="syft",
        properties=[
            {
                "name": "syft:package:foundBy",
                "value": "python-package-cataloger",
            }
        ],
    )

    assert isinstance(component.properties[0], ComponentProperty)
    assert component.properties[0].value == "python-package-cataloger"

def test_mutable_defaults_are_independent():
    first = Component(
        name="first",
        type="library",
        source="syft",
    )
    second = Component(
        name="second",
        type="library",
        source="syft",
    )

    first.locations.append("requirements.txt")

    assert second.locations == []

def test_scan_create():
    scan = ScanCreate(
        repo_url="https://github.com/psf/requests"
    )

    assert str(scan.repo_url) == "https://github.com/psf/requests"

    # File-upload scans may not have a repository URL.
    upload_scan = ScanCreate()
    assert upload_scan.repo_url is None

    with pytest.raises(ValidationError):
        ScanCreate(repo_url="not-a-valid-url")

def test_scan_read():
    scan_id = uuid4()

    scan = ScanRead(
        scan_id=scan_id,
        status="queued",
    )

    assert scan.scan_id == scan_id
    assert scan.status == ScanStatus.QUEUED
    assert scan.component_count == 0
    assert scan.error_message is None

    # Required fields must be provided.
    with pytest.raises(ValidationError):
        ScanRead(status="queued")

    with pytest.raises(ValidationError):
        ScanRead(scan_id=scan_id)

    # Component counts cannot be negative.
    with pytest.raises(ValidationError):
        ScanRead(
            scan_id=scan_id,
            status="completed",
            component_count=-1,
        )

def test_scan_context():
    scan_id = uuid4()

    context = ScanContext(
        scan_id=scan_id,
        repo_url="https://github.com/psf/requests",
        workspace_path="C:/temp/scan123",
    )

    assert context.scan_id == scan_id
    assert isinstance(context.workspace_path, Path)
    assert context.commit_sha is None

    # Workspace path is required.
    with pytest.raises(ValidationError):
        ScanContext(scan_id=scan_id)
