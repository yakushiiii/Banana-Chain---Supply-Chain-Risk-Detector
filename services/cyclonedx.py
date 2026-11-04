import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

SUPPORTED_VERSION = '1.7'
SCHEMA_DIR = Path(__file__).parent / "schemas"

class InvalidSbom(ValueError):
  """Raised when an SBOM fails CycloneDX validation."""
  pass

@lru_cache(maxsize=1)
def get_validator():
  """Load and cache the official CycloneDX 1.7 validator."""

  with open(SCHEMA_DIR / "bom-1.7.schema.json", encoding="utf-8") as f:
    bom_schema = json.load(f)

  with open(SCHEMA_DIR / "spdx.schema.json", encoding="utf-8") as f:
    spdx_schema = json.load(f)

  #resolve cyclonedx's spdx reference locally
  registry = Registry().with_resource(
    spdx_schema["$id"],
    Resource.from_contents(spdx_schema)
  )

  Draft7Validator.check_schema(bom_schema)

  return Draft7Validator(
    bom_schema,
    registry=registry,
    format_checker=FormatChecker()
  )

def validate_sbom(document: dict) -> None:
  """validate a cyclonedx document or raise invalidsbom."""

  if not isinstance(document, dict):
    raise InvalidSbom("SBOM must be a JSON object.")

  if document.get("specVersion") != SUPPORTED_VERSION:
    raise InvalidSbom(
      f"Unsupported cyclonedx version. Expected {SUPPORTED_VERSION}."
    )

  validator = get_validator()
  error = next(iter(validator.iter_errors(document)), None)

  if error is not None:
    location = "/".join(map(str, error.absolute_path)) or "root"
    raise InvalidSbom(f"invalid sbom at {location}: {error.message}")