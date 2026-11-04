import pytest
import json
from pathlib import Path
from copy import deepcopy

from services.cyclonedx import (
    InvalidSbom,
    validate_sbom,
    normalize_sbom,
    serialize_normalized,
)

def test_valid_sbom():
  document = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.7",
    "components": []
  }

  validate_sbom(document)

def test_invalid_sbom():
  document = {
    "bomFormat": "InvalidFormat",
    "specVersion": "1.7",
    "components": []
  }

  with pytest.raises(InvalidSbom):
    validate_sbom(document)

def test_unsupported_version():
  document = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "components": []
  }

  with pytest.raises(InvalidSbom):
    validate_sbom(document)

def test_malformed_component():
  document = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.7",
    "components": [
      {"name": "example"}
    ]
  }

  with pytest.raises(InvalidSbom):
    validate_sbom(document)

def test_duplicate_components_merge():
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "components": [
            {
                "type": "library",
                "name": "requests",
                "version": "2.31.0",
                "purl": "pkg:pypi/requests@2.31.0",
                "properties": [
                    {
                        "name": "syft:location:0:path",
                        "value": "requirements.txt"
                    }
                ],
            },
            {
                "type": "library",
                "name": "requests",
                "version": "2.31.0",
                "purl": "pkg:pypi/requests@2.31.0",
                "properties": [
                    {
                        "name": "syft:location:0:path",
                        "value": "pyproject.toml"
                    }
                ],
            },
        ],
    }

    original = deepcopy(document)
    components = normalize_sbom(document)

    assert len(components) == 1
    assert components[0]["name"] == "requests"
    assert components[0]["locations"] == [
        "pyproject.toml",
        "requirements.txt",
    ]

    # Normalization must not mutate the raw SBOM.
    assert document == original


def test_duplicate_fallback_without_purl():
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "components": [
            {
                "type": "library",
                "name": "example",
                "version": "1.0"
            },
            {
                "type": "library",
                "name": " example ",
                "version": "1.0"
            },
        ],
    }

    components = normalize_sbom(document)

    assert len(components) == 1
    assert components[0]["name"] == "example"


def test_deterministic_output():
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "components": [
            {"type": "library", "name": "zlib", "version": "1.2.0"},
            {"type": "library", "name": "requests", "version": "2.31.0"},
            {"type": "library", "name": "alpha", "version": "1.0"},
        ],
    }

    first = serialize_normalized(normalize_sbom(document))

    reversed_document = deepcopy(document)
    reversed_document["components"].reverse()

    second = serialize_normalized(
        normalize_sbom(reversed_document)
    )

    assert first == second

def test_real_requests_sbom():
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "requests.cdx.json"
    )

    raw = json.loads(fixture.read_text(encoding="utf-8"))

    assert raw["specVersion"] == "1.7"
    assert len(raw["components"]) == 31

    normalized = normalize_sbom(raw)

    # 8 duplicate GitHub Actions entries should be removed.
    assert len(normalized) == 23

    # The other 9 components represent files.
    assert sum(c["type"] == "file" for c in normalized) == 9

    # Duplicate occurrences must retain their locations.
    checkout = next(
        c for c in normalized
        if c["purl"] == "pkg:github/actions/checkout@v7.0.0"
    )
    assert len(checkout["locations"]) == 6

    setup_python = next(
        c for c in normalized
        if c["purl"] == "pkg:github/actions/setup-python@v7.0.0"
    )
    assert len(setup_python["locations"]) == 4

    # Verify the original Syft cataloger metadata survives.
    catalogers = {
        prop["value"]
        for component in normalized
        for prop in component["properties"]
        if prop["name"] == "syft:package:foundBy"
    }

    assert "python-package-cataloger" in catalogers
    assert "github-actions-usage-cataloger" in catalogers

def test_temporary_paths_are_deterministic():

    def make_document(temp_name):
        root = rf"C:\Users\tester\AppData\Local\Temp\{temp_name}"

        file_path = (
            f"/c/Users/tester/AppData/Local/Temp/"
            f"{temp_name}/repo/requirements.txt"
        )

        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "metadata": {
                "component": {
                    "type": "file",
                    "name": root,
                }
            },
            "components": [
                {
                    "type": "file",
                    "name": file_path,
                },
                {
                    "type": "library",
                    "name": "example",
                    "version": "1.0",
                    "properties": [
                        {
                            "name": "syft:location:0:path",
                            "value": file_path,
                        }
                    ],
                },
            ],
        }

    first = normalize_sbom(make_document("tmpABC"))
    second = normalize_sbom(make_document("tmpXYZ"))

    # Different temporary directories must give identical output.
    assert serialize_normalized(first) == serialize_normalized(second)

    # File paths should be relative to the scan directory.
    file_component = next(
        c for c in first if c["type"] == "file"
    )
    assert file_component["name"] == "repo/requirements.txt"

    # Syft locations should also be normalized.
    library = next(
        c for c in first if c["type"] == "library"
    )
    assert library["locations"] == ["repo/requirements.txt"]
