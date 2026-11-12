from enum import Enum

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    """How confidently a component was identified."""

    DECLARED = "declared"
    INFERRED = "inferred"
    OBSERVED = "observed"


class ComponentProperty(BaseModel):
    """Additional metadata preserved from an SBOM."""

    name: str = Field(min_length=1)
    value: str = ""


class Component(BaseModel):
    """Normalized representation of an SBOM component."""

    name: str = Field(min_length=1)
    type: str = Field(min_length=1)

    # Some components, particularly files, have no version or PURL.
    version: str | None = None
    purl: str | None = None

    licenses: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)

    # Identify the tool or source that produced this component.
    source: str = Field(min_length=1)

    # Default required by issue #13.
    confidence: Confidence = Confidence.DECLARED

    # Preserve Syft-specific cataloger and location metadata.
    properties: list[ComponentProperty] = Field(
        default_factory=list
    )
