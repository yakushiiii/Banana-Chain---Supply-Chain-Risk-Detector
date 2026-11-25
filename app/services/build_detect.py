import os
from pathlib import Path

from app.schemas import BuildDetection, BuildSystem

"""Detect C/C++ build systems in a repo by file names only. Never runs anything from the repo."""

POSSIBLE_MARKERFILES = { 
    "autotools": ["configure.ac", "configure.in", "Makefile.am"],
    "cmake": ["CMakeLists.txt"],
    "meson": ["meson.build"],
    "bazel": ["WORKSPACE", "WORKSPACE.bazel", "MODULE.bazel", "BUILD", "BUILD.bazel"],
    "scons": ["SConstruct"],
    "make": ["Makefile", "makefile", "GNUmakefile"]
}
MARKER_EXTENSIONS = {
    "msbuild": [".sln", ".vcxproj"],
}
SKIP_DIRS = {".git", "node_modules", "build", "third_party", "vendor", "external"}
C_CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
CONFIGURE_SCRIPTS = {"configure", "autogen.sh", "bootstrap"}
PACKAGE_MANIFESTS = {"conanfile.txt", "conanfile.py", "vcpkg.json"}
BUILD_PRIORITY = {"autotools": 0, "cmake": 1, "meson": 2, "bazel": 3, "scons": 4, "msbuild": 5, "make": 6}

def detect_build(repo_path, max_depth=6, max_files=50000):
    build_system_models = []
    configure_scripts = []
    pkg_managers = []
    has_c_cpp_sources = False
    truncated = False
    file_num = 0

    for root, dirnames, filenames in os.walk(repo_path, followlinks=False):
        if file_num >= max_files:
            truncated = True
            break

        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        depth = len(Path(root).relative_to(repo_path).parts)

        if depth >= max_depth: 
            dirnames[:] = []

        for file in filenames:
            if file_num >= max_files:
                truncated = True
                break

            file_num += 1
            full = Path(root) / file
            rel = full.relative_to(repo_path) # path relative to the user repo root
            ext = Path(file).suffix.lower()

            if not has_c_cpp_sources and ext in C_CPP_EXTENSIONS: 
                has_c_cpp_sources = True

            if file in CONFIGURE_SCRIPTS:
                configure_scripts.append(rel.as_posix())
                continue
            elif file in PACKAGE_MANIFESTS:
                pkg_managers.append(rel.as_posix())
                continue               

            for build_system, markerfiles in POSSIBLE_MARKERFILES.items():
                if file in markerfiles:
                    build_system_models.append(BuildSystem(build_system=build_system, markerfile_path=rel.as_posix()))
                    break

            for build_system, extensions in MARKER_EXTENSIONS.items():
                if ext in extensions:
                    build_system_models.append(BuildSystem(build_system=build_system, markerfile_path=rel.as_posix()))
                    break

    primary = pick_primary(build_system_models, has_c_cpp_sources)

    return BuildDetection(
        primary=primary, 
        detected=build_system_models, 
        configure_scripts=configure_scripts, 
        package_managers=pkg_managers, 
        has_c_cpp_sources=has_c_cpp_sources, 
        truncated=truncated
        )

def pick_primary(matches, has_c_cpp_sources):
    if not matches or not has_c_cpp_sources: 
        return None

    best = min(matches, key=lambda m: ((len(Path(m.markerfile_path).parts) - 1), (BUILD_PRIORITY[m.build_system])))
    return best.build_system
