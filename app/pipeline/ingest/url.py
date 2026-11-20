import re
from urllib.parse import urlsplit

OWNER_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class InvalidRepoUrl(ValueError):
    """Raised when a repository URL fails validation or normalization."""

    pass


def validate_and_normalize_github_url(raw_url: str) -> tuple[str, str, str]:
    """Validate and normalize a public GitHub repository URL.

    Args:
        raw_url: The raw URL string provided by the user.

    Returns:
        A tuple of (normalized_url, owner, repo).
        For example: ("https://github.com/pallets/flask", "pallets", "flask")

    Raises:
        InvalidRepoUrl: If the URL fails scheme, host, credential, port, or path rules.
    """
    if not raw_url or not isinstance(raw_url, str) or not raw_url.strip():
        raise InvalidRepoUrl("Repository URL cannot be empty.")

    stripped = raw_url.strip()

    try:
        parsed = urlsplit(stripped)
    except Exception as exc:
        raise InvalidRepoUrl(f"Malformed URL: {exc}") from exc

    # 1. Scheme check: HTTPS only
    if not parsed.scheme:
        raise InvalidRepoUrl("Missing URL scheme: URL must start with https://.")
    if parsed.scheme.lower() != "https":
        raise InvalidRepoUrl(
            f"Invalid scheme '{parsed.scheme}': only https:// URLs are supported."
        )

    # 2. Host check: github.com only (no lookalike domains or IPs)
    hostname = parsed.hostname
    if not hostname:
        raise InvalidRepoUrl("Missing hostname in repository URL.")
    if hostname.lower() != "github.com":
        raise InvalidRepoUrl(
            f"Invalid host '{hostname}': only public repositories on github.com are supported."
        )

    # 3. Credentials check: no user:pass@
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise InvalidRepoUrl("Embedded credentials are not allowed in repository URLs.")

    # 4. Port check: no explicit ports
    try:
        if parsed.port is not None:
            raise InvalidRepoUrl(
                f"Explicit port numbers (:{parsed.port}) are not allowed in repository URLs."
            )
    except ValueError:
        raise InvalidRepoUrl("Invalid port specification in repository URL.")

    # 5. Query string and fragment check
    if parsed.query:
        raise InvalidRepoUrl("Query parameters are not allowed in repository URLs.")
    if parsed.fragment:
        raise InvalidRepoUrl("URL fragments are not allowed in repository URLs.")

    # 6. Path check
    path = parsed.path
    if ".." in path or "//" in path:
        raise InvalidRepoUrl("Path traversal sequences and empty segments are not allowed.")

    segments = [s for s in path.split("/") if s]
    if len(segments) != 2:
        if len(segments) > 2 and segments[2] in ("tree", "blob"):
            raise InvalidRepoUrl(
                "Direct links to branches or files (/tree/ or /blob/) are not supported. "
                "Please provide the root repository URL."
            )
        raise InvalidRepoUrl(
            f"Invalid repository path '{path}': expected /<owner>/<repo> format."
        )

    owner, repo_segment = segments[0], segments[1]

    # Validate owner name
    if not OWNER_RE.match(owner):
        raise InvalidRepoUrl(
            f"Invalid repository owner '{owner}': must be 1-39 alphanumeric characters or hyphens."
        )

    # Strip optional .git suffix
    repo = repo_segment[:-4] if repo_segment.endswith(".git") else repo_segment

    # Validate repo name
    if not REPO_RE.match(repo):
        raise InvalidRepoUrl(
            f"Invalid repository name '{repo}': must be 1-100 alphanumeric characters, dots, underscores, or hyphens."
        )

    normalized_url = f"https://github.com/{owner}/{repo}"
    return normalized_url, owner, repo
