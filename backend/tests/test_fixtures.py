"""Checks the fixtures in tests/fixtures match what their README documents."""

import json
import shutil
from pathlib import Path

import pytest
from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator

from run_syft import generate_sbom

FIXTURES = Path(__file__).parent / "fixtures"

# Must match the "Expected components" column in tests/fixtures/README.md
EXPECTED_COMPONENTS = {
    "js-app": 54,
    "py-app": 6,
    "go-app": 5,
    "empty-repo": 0,
}

validator = JsonStrictValidator(SchemaVersion.V1_7)


def count_components(sbom):
    # Syft leaves out the "components" key entirely when it finds nothing
    return len(sbom.get("components", []))


def validation_error(path):
    return validator.validate_str(path.read_text())


@pytest.mark.parametrize("fixture, expected", EXPECTED_COMPONENTS.items())
def test_committed_sample_has_expected_components(fixture, expected):
    sbom = json.loads((FIXTURES / f"sample-syft-cyclonedx-{fixture}.json").read_text())
    assert count_components(sbom) == expected


@pytest.mark.skipif(shutil.which("syft") is None, reason="syft is not installed")
@pytest.mark.parametrize("fixture, expected", EXPECTED_COMPONENTS.items())
def test_syft_produces_expected_components(fixture, expected):
    sbom = generate_sbom(FIXTURES / "repos" / fixture)
    assert count_components(sbom) == expected


@pytest.mark.parametrize("fixture", EXPECTED_COMPONENTS)
def test_committed_sample_is_valid_cyclonedx(fixture):
    assert validation_error(FIXTURES / f"sample-syft-cyclonedx-{fixture}.json") is None


def test_malformed_sbom_fails_validation():
    assert validation_error(FIXTURES / "malformed-sbom.json") is not None