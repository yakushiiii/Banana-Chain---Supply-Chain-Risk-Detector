import os
from pathlib import Path

import pytest

from app.services.build_detect import detect_build, pick_primary
from app.schemas import BuildSystem


# ---------- helpers ----------

def make_repo(root, files):
    """Create empty files (and their folders) inside root."""
    for f in files:
        p = Path(root) / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")


def run(root, **kwargs):
    result = detect_build(str(root), **kwargs)
    return {
        "matches": {(m.build_system, m.markerfile_path) for m in result.detected},
        "configure": set(result.configure_scripts),
        "pkgs": set(result.package_managers),
        "truncated": result.truncated,
        "sources": result.has_c_cpp_sources,
        "primary": result.primary,
    }


def bs(system, path):
    return BuildSystem(build_system=system, markerfile_path=path)


# ---------- acceptance criteria ----------

def test_us_84_t_1_criterion_1_cmake_only(tmp_path):
    """Criterion 1: A repo with only CMakeLists.txt at the root (plus C/C++ sources) is detected as CMake."""
    make_repo(tmp_path, ["CMakeLists.txt", "src/main.c"])
    r = run(tmp_path)
    assert r["matches"] == {("cmake", "CMakeLists.txt")}
    assert r["sources"] is True
    assert r["primary"] == "cmake"


def test_us_84_t_1_criterion_2_autotools_with_configure_scripts(tmp_path):
    """Criterion 2: configure.ac + Makefile.am + Makefile is detected as Autotools, with configure scripts listed."""
    make_repo(tmp_path, ["configure.ac", "Makefile.am", "Makefile", "configure", "autogen.sh", "src/main.c"])
    r = run(tmp_path)
    assert r["matches"] == {
        ("autotools", "configure.ac"),
        ("autotools", "Makefile.am"),
        ("make", "Makefile"),
    }
    assert r["configure"] == {"configure", "autogen.sh"}
    assert r["primary"] == "autotools"


def test_us_84_t_1_criterion_3_root_cmake_beats_subfolder_make(tmp_path):
    """Criterion 3: A root CMakeLists.txt and a src/Makefile is detected as CMake."""
    make_repo(tmp_path, ["CMakeLists.txt", "src/Makefile", "src/main.c"])
    r = run(tmp_path)
    assert r["matches"] == {("cmake", "CMakeLists.txt"), ("make", "src/Makefile")}
    assert r["primary"] == "cmake"


def test_us_84_t_1_criterion_4_vendored_makefile_skipped(tmp_path):
    """Criterion 4: A CMake repo with a vendored third_party/*/Makefile is still CMake, and the vendored Makefile isn't listed."""
    make_repo(tmp_path, ["CMakeLists.txt", "third_party/zlib/Makefile", "src/main.c"])
    r = run(tmp_path)
    assert r["matches"] == {("cmake", "CMakeLists.txt")}
    assert r["primary"] == "cmake"


def test_us_84_t_1_criterion_5_handwritten_configure_is_make(tmp_path):
    """Criterion 5: A hand-written configure + Makefile (no configure.ac) is Make, with configure listed as a script."""
    make_repo(tmp_path, ["configure", "Makefile", "main.c"])
    r = run(tmp_path)
    assert r["matches"] == {("make", "Makefile")}
    assert r["configure"] == {"configure"}
    assert r["primary"] == "make"


def test_us_84_t_1_criterion_6_makefile_without_sources(tmp_path):
    """Criterion 6: A Makefile but no C/C++ source files reports no C/C++ build system."""
    make_repo(tmp_path, ["Makefile", "README.md", "app.py"])
    r = run(tmp_path)
    assert r["sources"] is False
    assert r["primary"] is None


def test_us_84_t_1_criterion_7_empty_repo(tmp_path):
    """Criterion 7: An empty repo returns primary = None without errors."""
    r = run(tmp_path)
    assert r["matches"] == set()
    assert r["primary"] is None
    assert r["truncated"] is False


def test_us_84_t_1_criterion_8_symlink_outside_not_followed(tmp_path):
    """Criterion 8: A symlink pointing outside the repo is not followed."""
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    make_repo(repo, ["src/main.c"])
    make_repo(outside, ["CMakeLists.txt"])
    try:
        os.symlink(outside, repo / "link")
    except OSError:
        pytest.skip("symlinks not supported on this system")
    r = run(repo)
    assert r["matches"] == set()


def test_us_84_t_1_criterion_9_truncated_at_file_limit(tmp_path):
    """Criterion 9: Walking stops at the file limit and sets truncated = True."""
    make_repo(tmp_path, [f"file{i}.txt" for i in range(10)])
    assert run(tmp_path, max_files=5)["truncated"] is True
    assert run(tmp_path)["truncated"] is False


# ---------- extra detection cases ----------

def test_depth_limit(tmp_path):
    make_repo(tmp_path, ["CMakeLists.txt", "a/b/c/x.c", "a/b/c/d/CMakeLists.txt"])
    r = run(tmp_path, max_depth=3)
    assert r["matches"] == {("cmake", "CMakeLists.txt")}
    assert r["sources"] is True  # folder at depth 3 is still scanned
    r = run(tmp_path, max_depth=6)
    assert ("cmake", "a/b/c/d/CMakeLists.txt") in r["matches"]


def test_msbuild_extensions(tmp_path):
    make_repo(tmp_path, ["app.sln", "src/core.vcxproj", "src/main.cpp"])
    r = run(tmp_path)
    assert r["matches"] == {("msbuild", "app.sln"), ("msbuild", "src/core.vcxproj")}
    assert r["primary"] == "msbuild"


def test_package_manifests(tmp_path):
    make_repo(tmp_path, ["CMakeLists.txt", "conanfile.txt", "vcpkg.json", "main.c"])
    assert run(tmp_path)["pkgs"] == {"conanfile.txt", "vcpkg.json"}


def test_uppercase_extension_counts_as_source(tmp_path):
    make_repo(tmp_path, ["Makefile", "Main.CPP"])
    assert run(tmp_path)["sources"] is True


# ---------- pick_primary ----------

@pytest.mark.parametrize("matches, has_sources, expected", [
    ([bs("make", "Makefile"), bs("autotools", "configure.ac")], True, "autotools"),
    ([bs("cmake", "CMakeLists.txt"), bs("make", "src/Makefile")], True, "cmake"),
    ([bs("make", "Makefile"), bs("cmake", "src/CMakeLists.txt")], True, "make"),
    ([bs("cmake", "CMakeLists.txt")], False, None),
    ([], True, None),
], ids=["same depth priority wins", "shallower wins", "root beats subfolder", "no sources", "no matches"])
def test_pick_primary(matches, has_sources, expected):
    assert pick_primary(matches, has_sources) == expected