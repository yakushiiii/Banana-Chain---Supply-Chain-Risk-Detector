# ADR 0001: Shared Pydantic Schemas

## Status

Accepted

## Context

Banana Chain processes software repositories to generate,
normalize, validate, and store Software Bills of Materials (SBOMs).

Multiple parts of the application need to exchange consistent
data, including the scanning pipeline, normalization service,
database persistence layer, and API endpoints.

Without shared schemas, each component could define its own
data structures, leading to inconsistencies and integration
problems.

The team reviewed the proposed schema contracts through
asynchronous discussion and agreed on the shared structure.

## Decision

We will use Pydantic models as the shared data contracts
throughout Banana Chain.

All shared schemas will be defined in the `app/schemas/`
package and exported through `app/schemas/__init__.py`.

### 1. ScanStatus

ScanStatus will be a string-based enumeration containing:

- queued
- cloning
- scanning
- normalizing
- persisting
- completed
- failed

These values represent the stages of the SBOM scanning pipeline.

### 2. Component

Component represents a normalized SBOM component.

Fields:

- name: Required string
- type: Required string
- version: Optional string
- purl: Optional string
- licenses: List of strings
- locations: List of strings
- source: Required string
- confidence: Enum with declared, inferred, and observed
- properties: List of structured name/value properties

The default confidence value is `declared`.

Lists use independent default factories to prevent
shared mutable state between model instances.

### 3. ScanCreate

ScanCreate represents the data supplied when requesting a scan.

Fields:

- repo_url: Optional validated HTTP URL

The repository URL is optional to support scans initiated
through file uploads.

### 4. ScanRead

ScanRead represents information returned when retrieving
a scan.

Fields:

- scan_id: UUID
- status: ScanStatus
- repo_url: Optional HTTP URL
- component_count: Nonnegative integer, defaulting to zero
- created_at: Optional datetime
- completed_at: Optional datetime
- error_message: Optional string

### 5. ScanContext

ScanContext stores contextual information used during
the scanning process.

Fields:

- scan_id: UUID
- repo_url: Optional HTTP URL
- workspace_path: Path
- commit_sha: Optional string

### 6. Package Structure

Shared schemas will live in the following directory:

app/
schemas/
**init**.py
component.py
context.py
scan.py

The FastAPI application lives in `app/main.py`.

A root-level `app.py` compatibility entry point is retained
to support existing application startup commands.

## Consequences

### Benefits

- Consistent data structures across the application
- Automatic field validation through Pydantic
- Easier integration between services
- Reduced duplication of model definitions
- Improved maintainability and testability

### Tradeoffs

- Changes to shared schemas may affect multiple services
- Developers must coordinate changes to shared data contracts
- Converting external SBOM data into application models
  requires an explicit normalization step

## Testing

Unit tests verify:

- Required fields
- Optional fields and defaults
- Enum validation
- Independent list defaults
- Component properties
- Scan creation and response models
- Scan context validation

The initial implementation passes nine automated tests.

## Future Work

The CycloneDX normalization service will be integrated
with the shared Component model.

The persistence layer will use these schemas when storing
and retrieving SBOMs and their normalized components.

## Team Agreement

The proposed schema structure was discussed asynchronously
with the development team.

The team agreed on the shared model structure, field types,
defaults, and package organization.
