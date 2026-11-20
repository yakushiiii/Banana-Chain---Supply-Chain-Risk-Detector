import os
import re
import shutil
import signal
import subprocess

import requests

MAX_MB = 500
GITHUB_URL = re.compile(r"https://github[.]com/([A-Za-z0-9-]+)[/]([A-Za-z0-9-._]+?)(?:[.]git)?/?")
TIMEOUT = 120

class CloneError(Exception):
    """Exception raised for failed repo clone"""
    def __init__(self, message, error_code):    
        self.message = message
        self.error_code = error_code    
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} (Error Code: {self.error_code})"
    ##Call using this: raise CloneError("Git repo clone failed.", 400)

def parse_github_url(url):
    cleaned_url= GITHUB_URL.fullmatch(url.strip())
    if not cleaned_url:
        raise(CloneError(f"Invalid Github repo: {url!r}.", 400))
    owner = cleaned_url.group(1)
    repo = cleaned_url.group(2)
    return (owner, repo)

def check_repo(owner, repo, max_kb, token=None):
    endpoint = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-Github-Api-Version": "2022-11-28"
    }

    if token: 
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(endpoint, headers = headers, timeout = 10)
    except requests.exceptions.RequestException as e:
        raise CloneError("Couldn't reach the service", 503) from e

    if (response.status_code == 200):
        data = response.json()
        if data.get("private") == True:
            raise CloneError("Repo is private. Banana Chain can only work with public repos", 400)
        if data.get("size", 0) > max_kb:
            raise CloneError(f"Repo is {data['size']} KB, limit is {max_kb} KB", 413)
    elif (response.status_code == 404):
        raise CloneError("Repo private or not found", 404)
    elif (response.status_code == 403 or response.status_code == 429):
        raise CloneError("Rate limited", response.status_code)
    else:
        raise CloneError("Bad response from upstream", response.status_code)
    return data

def clone_repo(ctx, max_mb=MAX_MB, timeout=TIMEOUT, token=None):

    owner, repo = parse_github_url(str(ctx.repo_url))
    check_repo(owner, repo, max_mb * 1024, token)

    dest = str(ctx.workspace_path)

    cmd = ["git", "clone", "--depth", "1", "--single-branch", "--no-tags", "--no-recurse-submodules", "--", f"https://github.com/{owner}/{repo}.git", dest]

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        _, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as e:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()

        shutil.rmtree(dest, ignore_errors=True)
        raise CloneError(f"Clone timed out after {timeout}s", 504) from e

    if proc.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise CloneError(f"failed: {stderr[:500]}", 502)

    sha_cmd = ["git", "-C", dest, "rev-parse", "HEAD"]
    sha_result = subprocess.run(sha_cmd, env=env, capture_output=True, text=True, timeout=timeout, check=False)

    if sha_result.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise CloneError(f"Could not read commit SHA: {sha_result.stderr[:200]}", 500)
    
    ctx.commit_sha = sha_result.stdout.strip()

    return dest

    



    
        