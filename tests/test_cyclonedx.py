import pytest

from services.cyclonedx import InvalidSbom, validate_sbom

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