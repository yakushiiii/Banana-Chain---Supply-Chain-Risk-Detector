from typing import Literal

from pydantic import BaseModel, Field


class BuildSystem(BaseModel):
    build_system: str
    markerfile_path: str

class BuildDetection(BaseModel):
    primary: str | None = None
    detected: list[BuildSystem] = Field(default_factory=list)
    configure_scripts: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    has_c_cpp_sources: bool = False
    truncated: bool = False

class BuildResult(BaseModel):
    status: Literal["success", "failed", "timeout", "unsupported", "skipped"]
    exit_code: int | None = None
    duration_seconds: float = 0.0
    commands: list[str] = Field(default_factory=list)
    log_path: str | None = None
    log_tail: str = ""