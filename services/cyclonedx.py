from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from packageurl import PackageURL
from typing import TYPE_CHECKING
from pydantic import ValidationError

from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

if TYPE_CHECKING:
    from app.schemas.component import Component

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

def normalize_purl(value: str | None) -> str | None:
    """Normalize a Package URL into a consistent representation."""
    if not value or not value.strip():
        return None

    try:
        return PackageURL.from_string(value.strip()).to_string()
    except ValueError as exc:
        raise InvalidSbom(f"Invalid package URL: {value}") from exc

def normalize_scan_path(value: str, scan_root: str | None) -> str:
    """Remove the temporary scan directory from file paths."""

    def portable(path: str) -> str:
        path = path.replace("\\", "/")

        # Convert C:/Users/... into /c/Users/...
        if len(path) >= 2 and path[1] == ":":
            path = "/" + path[0].lower() + path[2:]

        return path

    path = portable(value)

    if scan_root:
        root = portable(scan_root).rstrip("/")

        if path.casefold().startswith(root.casefold() + "/"):
            return path[len(root) + 1:]

    return path

def normalize_component(
      component: dict,
      scan_root: str | None = None
) -> dict:
    """Convert one CycloneDX component into our internal format."""

    # Preserve and consistently order Syft metadata.
    properties = sorted({
        (
            prop["name"],
            normalize_scan_path(prop.get("value", ""), scan_root)
            if prop["name"].startswith("syft:location:")
            and prop["name"].endswith(":path")
            else prop.get("value", "")
        )
        for prop in component.get("properties", [])
    })

    # Extract the source files identified by Syft.
    locations = sorted({
        value
        for name, value in properties
        if name.startswith("syft:location:")
        and name.endswith(":path")
    })

    # Extract license identifiers, names, and expressions.
    licenses = set()

    for entry in component.get("licenses", []):
        if "expression" in entry:
            licenses.add(entry["expression"])
        elif "license" in entry:
            license_data = entry["license"]
            license_name = (
                license_data.get("id")
                or license_data.get("name")
            )
            if license_name:
                licenses.add(license_name)

    version = component.get("version")
    version = version.strip() if version else None

    name = component["name"].strip()

    if component["type"] == "file":
        name = normalize_scan_path(name, scan_root)

    return {
        "name": name,
        "version": version or None,
        "purl": normalize_purl(component.get("purl")),
        "type": component["type"].strip().lower(),
        "licenses": sorted(licenses),
        "locations": locations,
        "source": "syft",
        "confidence": "declared",
        "properties": [
            {"name": name, "value": value}
            for name, value in properties
        ],
    }


def _choose_text(first: str | None, second: str | None):
    """Choose a consistent value regardless of input order."""
    values = [value for value in (first, second) if value]
    return min(values, key=lambda value: (value.casefold(), value)) if values else None


def normalize_sbom(document: dict) -> list[Component]:
    """Validate, normalize, deduplicate, and sort SBOM components."""

    from app.schemas.component import Component

    validate_sbom(document)

    metadata = document.get("metadata") or {}
    source_component = metadata.get("component") or {}
    scan_root = source_component.get("name")

    unique = {}

    for raw_component in document.get("components", []):
        component = normalize_component(raw_component, scan_root)

        # Prefer PURL identity; fall back when PURL is missing.
        if component["purl"]:
            key = ("purl", component["purl"])
        else:
            key = (
                "fallback",
                component["name"].casefold(),
                component["version"],
                component["type"],
            )

        if key not in unique:
            unique[key] = component
            continue

        existing = unique[key]

        # Merge metadata instead of losing information.
        existing["licenses"] = sorted(
            set(existing["licenses"]) | set(component["licenses"])
        )
        existing["locations"] = sorted(
            set(existing["locations"]) | set(component["locations"])
        )

        combined_properties = {
            (prop["name"], prop["value"])
            for prop in existing["properties"] + component["properties"]
        }

        existing["properties"] = [
            {"name": name, "value": value}
            for name, value in sorted(combined_properties)
        ]

        # Make conflicting display fields deterministic.
        for field in ("name", "version", "type"):
            existing[field] = _choose_text(
                existing[field], component[field]
            )

    ordered = sorted(
        unique.values(),
        key=lambda component: (
            component["purl"] or "",
            component["name"].casefold(),
            component["version"] or "",
            component["type"],
        ),
    )

    try:
        return [
            Component.model_validate(component)
            for component in ordered
        ]
    except ValidationError as exc:
        raise InvalidSbom(
            "Normalized component failed Pydantic validation."
        ) from exc


def serialize_normalized(components: list[Component]) -> bytes:
    """Serialize normalized components into deterministic JSON bytes."""

    component_dicts = [
        component.model_dump(mode="json")
        for component in components
    ]

    return json.dumps(
        component_dicts,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
