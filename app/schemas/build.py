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