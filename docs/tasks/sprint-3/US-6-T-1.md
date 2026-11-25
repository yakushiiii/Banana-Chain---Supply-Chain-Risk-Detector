---
id: US-6-T-1
story: US-6
sprint: 3
assignee: Sofia Yakushi
estimate_hours: 8
---

# Detect C/C++ build system

## Description
Serves User Story #6 (Upload and scan C/C++ projects / Issue #61). After a repo is cloned or uploaded, this task inspects it by file names only to find which C/C++ build system it uses, along with configure scripts, package manifests, and whether it contains C/C++ source files. The result is stored on `ScanContext.build_system` for later tasks: Makefile parsing (#79), CMakeLists parsing (#62), and the sandboxed build runner (#63).

Parsing build files, running builds, and executing anything from the repo are out of scope (#63 handles builds).

## Specs
- `app/services/build_detect.py` provides `detect_build(repo_path, max_depth=6, max_files=50000) -> BuildDetection`.
- Never runs, builds, or executes anything from the repo; only file names are inspected.
- Detects build systems by marker files:
  - autotools: `configure.ac`, `configure.in`, `Makefile.am`
  - cmake: `CMakeLists.txt`
  - meson: `meson.build`
  - bazel: `WORKSPACE`, `WORKSPACE.bazel`, `MODULE.bazel`, `BUILD`, `BUILD.bazel`
  - scons: `SConstruct`
  - msbuild: `*.sln`, `*.vcxproj`
  - make: `Makefile`, `makefile`, `GNUmakefile`
- Records configure scripts (`configure`, `autogen.sh`, `bootstrap`) without running them. A bare `configure` does not count as Autotools.
- Records package manifests (`conanfile.txt`, `conanfile.py`, `vcpkg.json`).
- Walks with `os.walk(..., followlinks=False)`, skips `.git`, `node_modules`, `build`, `third_party`, `vendor`, `external`, stops descending at depth 6, and stops after 50,000 files with `truncated = True`.
- Detects C/C++ sources (`.c`, `.cc`, `.cpp`, `.cxx`, `.h`, `.hh`, `.hpp`, `.hxx`, case-insensitive). With no sources, `primary` is `None`.
- `pick_primary` chooses the shallowest match, then by priority: autotools > cmake > meson > bazel > scons > msbuild > make.
- `app/main.py` calls `detect_build` after `clone_repo` and after uploads in both `/results` and `/api/scan`.
- Models `BuildSystem` and `BuildDetection` live in `app/schemas/build.py` (ADR 0001).
- Automated tests in `tests/test_build_detect.py` with test names matching the acceptance criteria.

## Requirements
- No new runtime dependencies.
- Must not execute any file from the scanned repository.
- `ScanContext` change agreed with the team per ADR 0001.

## Known limitations
- Uploaded files lose their folder structure (`main.py` saves them by file name only), so detection on uploads only sees root-level files.
- Projects whose build files are deeper than 6 folders are not detected.
- Only Make (#79) and CMake (#62) have parsers; other detected systems rely on the build runner (#63).

## Acceptance criteria
1. A repo with only `CMakeLists.txt` at the root (plus C/C++ sources) is detected as CMake.
2. A repo with `configure.ac`, `Makefile.am` and a `Makefile` is detected as Autotools, with configure scripts listed.
3. A repo with a root `CMakeLists.txt` and a `src/Makefile` is detected as CMake.
4. A CMake repo with a vendored `third_party/*/Makefile` is still CMake, and the vendored Makefile isn't listed.
5. A hand-written `configure` and a `Makefile` (no `configure.ac`) is detected as Make, with `configure` listed as a configure script.
6. A repo with a `Makefile` but no C/C++ sources reports no C/C++ build system (`primary = None`).
7. An empty repo returns `primary = None` without errors.
8. A symlink pointing outside the repo is not followed.
9. Walking stops at the file limit and sets `truncated = True`.