import subprocess
from pathlib import Path

import pytest

from app.schemas import BuildDetection
from app.services import build_runner
from app.services.build_runner import (
    IMAGE_NAME,
    choose_commands,
    docker_args,
    run_build,
)

HELLO_C = '#include <stdio.h>\nint main(void) { printf("hello from the sandbox\\n"); return 0; }\n'
CMAKE_LISTS = "cmake_minimum_required(VERSION 3.10)\nproject(hello C)\nadd_executable(hello main.c)\n"
MAKEFILE = "all:\n\tgcc main.c -o hello\n"   # \t: Makefile recipes must start with a tab


def make_repo(root, files):
    """Create files with the given contents. files = {"path": "contents"}."""
    for name, content in files.items():
        p = Path(root) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def detection(primary, has_sources=True):
    return BuildDetection(primary=primary, has_c_cpp_sources=has_sources)


def docker_ready():
    """True if Docker is running and the banana-builder image exists."""
    try:
        r = subprocess.run(["docker", "image", "inspect", IMAGE_NAME],
                           capture_output=True, check=False, timeout=20)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


needs_docker = pytest.mark.skipif(
    not docker_ready(), reason="Docker or the banana-builder image is not available"
)


def no_build_containers_running():
    r = subprocess.run(["docker", "ps", "-q", "--filter", "name=banana-build-"],
                       capture_output=True, text=True, check=False)
    return r.stdout.strip() == ""


def fail_if_called(*args, **kwargs):
    raise AssertionError("subprocess.run should not be called")


#  integration tests - real Docker

@needs_docker
def test_us_6_t_4_criterion_1_cmake_builds(tmp_path):
    """Criterion 1: A small CMake repo builds: status success, exit code 0, log saved."""
    make_repo(tmp_path, {"main.c": HELLO_C, "CMakeLists.txt": CMAKE_LISTS})
    r = run_build(tmp_path, detection("cmake"))
    assert r.status == "success"
    assert r.exit_code == 0
    assert Path(r.log_path).exists()
    assert "Built target hello" in r.log_tail


@needs_docker
def test_us_6_t_4_criterion_2_make_builds(tmp_path):
    """Criterion 2: A small Makefile repo builds: status success."""
    make_repo(tmp_path, {"main.c": HELLO_C, "Makefile": MAKEFILE})
    r = run_build(tmp_path, detection("make"))
    assert r.status == "success"
    assert r.exit_code == 0


@needs_docker
def test_us_6_t_4_criterion_3_compile_error_fails(tmp_path):
    """Criterion 3: A repo with a compile error returns failed with the error in log_tail."""
    make_repo(tmp_path, {"main.c": "int main(void) { this is not C }\n", "Makefile": MAKEFILE})
    r = run_build(tmp_path, detection("make"))
    assert r.status == "failed"
    assert r.exit_code != 0
    assert "error" in r.log_tail.lower()


@needs_docker
def test_us_6_t_4_criterion_4_timeout_kills_container(tmp_path):
    """Criterion 4: A build that never ends is stopped at the timeout and leaves no container running."""
    make_repo(tmp_path, {"main.c": HELLO_C, "Makefile": "all:\n\tsleep 1000\n"})
    r = run_build(tmp_path, detection("make"), timeout=3)
    assert r.status == "timeout"
    assert r.exit_code is None
    assert no_build_containers_running()


@needs_docker
def test_us_6_t_4_criterion_5_network_blocked(tmp_path):
    """Criterion 5: A build that tries to use the network fails because networking is disabled."""
    make_repo(tmp_path, {"main.c": HELLO_C, "Makefile": "all:\n\tgetent hosts example.com\n"})
    r = run_build(tmp_path, detection("make"))
    assert r.status == "failed"


@needs_docker
def test_us_6_t_4_criterion_8_original_unchanged(tmp_path):
    """Criterion 8: The original workspace is unchanged after a build."""
    make_repo(tmp_path, {"main.c": HELLO_C, "CMakeLists.txt": CMAKE_LISTS})
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    r = run_build(tmp_path, detection("cmake"))
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert r.status == "success"
    assert before == after   # no _build folder or binary appeared in the original


# no-Docker tests

@pytest.mark.parametrize("primary", ["bazel", "scons", "msbuild", None])
def test_us_6_t_4_criterion_6_unsupported_starts_nothing(tmp_path, monkeypatch, primary):
    """Criterion 6: bazel, scons, msbuild or None returns unsupported without starting a container."""
    monkeypatch.setattr(build_runner.subprocess, "run", fail_if_called)
    r = run_build(tmp_path, detection(primary))
    assert r.status == "unsupported"


def test_us_6_t_4_criterion_7_no_sources_starts_nothing(tmp_path, monkeypatch):
    """Criterion 7: A repo with no C/C++ sources returns skipped without starting a container."""
    monkeypatch.setattr(build_runner.subprocess, "run", fail_if_called)
    r = run_build(tmp_path, detection("cmake", has_sources=False))
    assert r.status == "skipped"


def test_us_6_t_4_criterion_9_choose_commands():
    """Criterion 9: Command selection is tested without Docker."""
    assert choose_commands(detection("cmake")) == (["cmake -S . -B _build", "cmake --build _build"], None)
    assert choose_commands(detection("make")) == (["make"], None)
    assert choose_commands(detection("bazel")) == (None, "unsupported")
    assert choose_commands(detection(None)) == (None, "unsupported")
    assert choose_commands(detection("make", has_sources=False)) == (None, "skipped")


def test_us_6_t_4_criterion_9_docker_args_are_locked_down():
    """Criterion 9: The docker arguments are tested without Docker."""
    args = docker_args("banana-build-test", "/tmp/repo", ["make", "make install"])

    def value_after(flag):
        return args[args.index(flag) + 1]

    assert args[:3] == ["docker", "run", "--rm"]
    assert value_after("--network") == "none"
    assert value_after("--memory") == "2g"
    assert value_after("--cpus") == "2"
    assert value_after("--pids-limit") == "512"
    assert value_after("--cap-drop") == "ALL"
    assert value_after("--security-opt") == "no-new-privileges"
    assert value_after("--user") == "builder"
    assert value_after("--name") == "banana-build-test"
    assert value_after("-v") == "/tmp/repo:/src"
    assert args.index("--user") < args.index(IMAGE_NAME)   # flags must come before the image
    assert args[-3:] == ["sh", "-c", "make && make install"]
    assert "/var/run/docker.sock" not in " ".join(args)    # never mount the Docker socket


def test_docker_missing_returns_failed(tmp_path, monkeypatch):
    """If Docker isn't installed, run_build returns failed instead of crashing."""
    def no_docker(*args, **kwargs):
        raise FileNotFoundError("docker")

    make_repo(tmp_path, {"main.c": HELLO_C, "Makefile": MAKEFILE})
    monkeypatch.setattr(build_runner.subprocess, "run", no_docker)
    r = run_build(tmp_path, detection("make"))
    assert r.status == "failed"
    assert "Docker" in r.log_tail