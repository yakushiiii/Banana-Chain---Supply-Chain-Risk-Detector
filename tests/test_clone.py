import os
import re
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import requests

from app.schemas.context import ScanContext
from app.services import clone
from app.services.clone import CloneError, check_repo, clone_repo, parse_github_url

# ---------- helpers ----------

class FakeResponse:
    """Stands in for requests.Response so tests never hit the real GitHub API."""

    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


def fake_get(status_code, data=None, calls=None):
    """Build a replacement for requests.get that returns a canned response."""

    def _get(url, headers=None, timeout=None):
        if calls is not None:
            calls.append({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse(status_code, data)

    return _get


def make_ctx(tmp_path, url):
    scan_id = uuid4()
    return ScanContext(scan_id=scan_id, repo_url=url, workspace_path=tmp_path / str(scan_id))


def make_fake_git(tmp_path, script):
    """Put a fake `git` executable first on PATH. Returns its folder."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text("#!/bin/sh\n" + script)
    git.chmod(0o755)
    return bin_dir


def process_is_dead(pid):
    """True if pid is gone or a zombie (killed but not yet reaped). Works on macOS and Linux."""
    out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False)
    stat = out.stdout.strip()
    return stat == "" or stat.startswith("Z")


# ---------- 1. URL parsing ----------

@pytest.mark.parametrize("url", [
    "https://github.com/torvalds/linux",
    "https://github.com/torvalds/linux.git",
    "https://github.com/torvalds/linux/",
    "  https://github.com/torvalds/linux  ",
])
def test_parse_valid_urls(url):
    assert parse_github_url(url) == ("torvalds", "linux")


def test_parse_keeps_dots_dashes_underscores_in_repo():
    assert parse_github_url("https://github.com/my-org/my_repo.v2") == ("my-org", "my_repo.v2")


@pytest.mark.parametrize("url", [
    "https://github.com/a/b; rm -rf ~",
    "https://github.com/a/b --config=x",
    "https://github.com/a/b$(whoami)",
    "https://github.com/a/b`id`",
    "https://github.com/a/b\nhttps://evil.com/x",
    "--upload-pack=touch /tmp/pwned",
    "-c core.sshCommand=touch /tmp/pwned",
    "https://github.com/a/b/tree/main",
    "https://github.com/../b",
    "https://evil.com/a/b",
    "http://github.com/a/b",
    "git@github.com:a/b.git",
    "file:///etc/passwd",
    "",
])
def test_parse_rejects_bad_urls(url):
    with pytest.raises(CloneError) as exc_info:
        parse_github_url(url)
    assert exc_info.value.error_code == 400


# ---------- 2. Hostile URLs never reach git or the network ----------

@pytest.mark.parametrize("url", [
    "https://github.com/a/b; rm -rf ~",
    "--upload-pack=touch /tmp/pwned",
    "https://github.com/a/b --config=x",
])
def test_hostile_url_never_runs_git(monkeypatch, tmp_path, url):
    def fail(*args, **kwargs):
        raise AssertionError("must not be called for a hostile URL")

    monkeypatch.setattr(clone.subprocess, "Popen", fail)
    monkeypatch.setattr(clone.subprocess, "run", fail)
    monkeypatch.setattr(clone.requests, "get", fail)

    # SimpleNamespace instead of ScanContext so Pydantic can't reject the URL first;
    # this proves clone_repo's own validation is what stops it.
    ctx = SimpleNamespace(repo_url=url, workspace_path=tmp_path / "ws", commit_sha=None)
    with pytest.raises(CloneError) as exc_info:
        clone_repo(ctx)
    assert exc_info.value.error_code == 400
    assert not (tmp_path / "ws").exists()


# ---------- 3. GitHub API check ----------

def test_check_repo_accepts_small_public_repo(monkeypatch):
    monkeypatch.setattr(clone.requests, "get", fake_get(200, {"private": False, "size": 100}))
    check_repo("octocat", "Hello-World", max_kb=500 * 1024)  # should not raise


def test_check_repo_not_found(monkeypatch):
    monkeypatch.setattr(clone.requests, "get", fake_get(404, {"message": "Not Found"}))
    with pytest.raises(CloneError) as exc_info:
        check_repo("octocat", "nope", max_kb=500 * 1024)
    assert exc_info.value.error_code == 404


def test_check_repo_private(monkeypatch):
    monkeypatch.setattr(clone.requests, "get", fake_get(200, {"private": True, "size": 10}))
    with pytest.raises(CloneError) as exc_info:
        check_repo("me", "secret", max_kb=500 * 1024)
    assert "private" in exc_info.value.message.lower()


def test_check_repo_too_large(monkeypatch):
    monkeypatch.setattr(clone.requests, "get", fake_get(200, {"private": False, "size": 6_403_541}))
    with pytest.raises(CloneError) as exc_info:
        check_repo("torvalds", "linux", max_kb=500 * 1024)
    assert exc_info.value.error_code == 413
    assert "6403541" in exc_info.value.message


def test_check_repo_at_exact_limit_is_allowed(monkeypatch):
    monkeypatch.setattr(clone.requests, "get", fake_get(200, {"private": False, "size": 1024}))
    check_repo("a", "b", max_kb=1024)  # equal to the limit should pass


@pytest.mark.parametrize("status", [403, 429])
def test_check_repo_rate_limited(monkeypatch, status):
    monkeypatch.setattr(clone.requests, "get", fake_get(status))
    with pytest.raises(CloneError) as exc_info:
        check_repo("a", "b", max_kb=1024)
    assert exc_info.value.error_code == status


def test_check_repo_network_error(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("no network")

    monkeypatch.setattr(clone.requests, "get", boom)
    with pytest.raises(CloneError) as exc_info:
        check_repo("a", "b", max_kb=1024)
    assert exc_info.value.error_code == 503


def test_check_repo_calls_correct_endpoint_without_token(monkeypatch):
    calls = []
    monkeypatch.setattr(clone.requests, "get", fake_get(200, {"private": False, "size": 1}, calls))
    check_repo("octocat", "Hello-World", max_kb=1024)
    assert calls[0]["url"] == "https://api.github.com/repos/octocat/Hello-World"
    assert "Authorization" not in calls[0]["headers"]
    assert calls[0]["timeout"] is not None


def test_check_repo_sends_token(monkeypatch):
    calls = []
    monkeypatch.setattr(clone.requests, "get", fake_get(200, {"private": False, "size": 1}, calls))
    check_repo("octocat", "Hello-World", max_kb=1024, token="abc123")
    assert calls[0]["headers"]["Authorization"] == "Bearer abc123"


# ---------- 4. Successful clone (real network, tiny repo) ----------

def test_small_public_repo_clones_and_records_sha(monkeypatch, tmp_path):
    # Skip the API call (avoids rate limits in CI); the git clone itself is real.
    monkeypatch.setattr(clone, "check_repo", lambda *a, **k: None)
    ctx = make_ctx(tmp_path, "https://github.com/octocat/Hello-World")

    dest = clone_repo(ctx)

    assert Path(dest) == ctx.workspace_path
    assert (ctx.workspace_path / "README").exists()
    assert re.fullmatch(r"[0-9a-f]{40}", ctx.commit_sha)


# ---------- 5. Failures clean up, timeouts kill the clone ----------

def test_failed_clone_raises_and_cleans_up(monkeypatch, tmp_path):
    monkeypatch.setattr(clone, "check_repo", lambda *a, **k: None)
    # Fake git: creates the destination folder, then fails like a real clone error would.
    bin_dir = make_fake_git(tmp_path, 'for last; do :; done\nmkdir -p "$last"\necho "fatal: boom" >&2\nexit 128\n')
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    ctx = make_ctx(tmp_path, "https://github.com/octocat/Hello-World")

    with pytest.raises(CloneError) as exc_info:
        clone_repo(ctx)

    assert exc_info.value.error_code == 502
    assert "fatal: boom" in exc_info.value.message
    assert not ctx.workspace_path.exists()


def test_hung_clone_is_killed_at_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(clone, "check_repo", lambda *a, **k: None)
    pid_file = tmp_path / "child.pid"
    # Fake git that hangs and starts a hanging child, like git-remote-https on a stalled network.
    bin_dir = make_fake_git(tmp_path, f'sleep 15 &\necho $! > "{pid_file}"\nsleep 15\n')
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    ctx = make_ctx(tmp_path, "https://github.com/octocat/Hello-World")

    start = time.monotonic()
    with pytest.raises(CloneError) as exc_info:
        clone_repo(ctx, timeout=1)
    elapsed = time.monotonic() - start

    assert exc_info.value.error_code == 504
    assert elapsed < 10, "clone_repo should return right after the timeout"
    assert not ctx.workspace_path.exists()

    child_pid = int(pid_file.read_text())
    for _ in range(20):  # give the OS a moment to finish killing it
        if process_is_dead(child_pid):
            break
        time.sleep(0.1)
    assert process_is_dead(child_pid), "git's child process should be killed too"