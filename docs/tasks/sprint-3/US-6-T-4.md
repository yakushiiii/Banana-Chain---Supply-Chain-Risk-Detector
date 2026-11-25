---
id: US-6-T-4
story: US-6
sprint: 3
assignee: Sofia Yakushi
estimate_hours: 10
---

# Sandboxed build runner

## Description
Serves User Story 6 (Upload and scan C/C++ projects / Issue #63). This task builds a C/C++ project inside a locked-down Docker container, using the build system found by US-6-T-1 (#61), and saves the build log. Builds run code from untrusted repositories, so the container has no network access, resource limits, a timeout, and no extra privileges. The build is what US-6-T-5 (#64) will observe to record build-time dependencies.

Parsing build files and recording dependencies are out of scope (#62, #79, #64).

## Specs
- `app/services/build_runner.py` provides `run_build(workspace_path, detection, timeout=600) -> BuildResult`.
- Builds run on a copy of the workspace; the original files are never changed.
- Builder image at `docker/builder/Dockerfile` with gcc, g++, make, cmake and pkg-config, running as a non-root user.
- Commands chosen from `detection.primary`:
  - cmake: `cmake -S . -B _build` then `cmake --build _build`
  - make: `make`
  - any other system, or `None`: no build, status `unsupported`
  - no C/C++ sources: no build, status `skipped`
- `docker run` is called through `subprocess` with `--rm`, `--network none`, `--memory`, `--cpus`, `--pids-limit`, `--cap-drop ALL`, `--security-opt no-new-privileges`, a non-root `--user`, a unique container name, and the workspace copy mounted at `/src` as the only mount.
- On timeout the container is killed and the status is `timeout`.
- Combined output is saved to `build.log`; the last part is kept in the result.
- `BuildResult` in `app/schemas/build.py`: status, exit_code, duration_seconds, commands, log_path, log_tail.
- If Docker is unavailable, the result is `failed` with a clear message instead of an exception.

## Requirements
- No new Python dependencies.
- Nothing from the scanned repository runs outside the container.
- The Docker socket is never mounted into the build container.

## Acceptance criteria
1. A small CMake repo builds: status `success`, exit code 0, log saved.
2. A small Makefile repo builds: status `success`.
3. A repo with a compile error returns `failed` with the error in `log_tail`.
4. A build that never ends is stopped at the timeout, returns `timeout`, and leaves no container running.
5. A build that tries to use the network fails because networking is disabled.
6. A repo detected as bazel, scons, msbuild or None returns `unsupported` without starting a container.
7. A repo with no C/C++ sources returns `skipped` without starting a container.
8. The original workspace is unchanged after a build.
9. Unit tests cover command selection and the docker arguments without Docker; integration tests use real Docker and are skipped when Docker is unavailable.

## Future work
- Autotools and Meson builds.
- A command prefix hook for #64.
- Capping the log file size.