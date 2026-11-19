import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.ingest.url import InvalidRepoUrl, validate_and_normalize_github_url

client = TestClient(app)


# ---------------------------------------------------------------------------
# Acceptance Criterion 1 & 2: Valid GitHub URLs and Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_url,expected_norm,expected_owner,expected_repo",
    [
        (
            "https://github.com/pallets/flask",
            "https://github.com/pallets/flask",
            "pallets",
            "flask",
        ),
        (
            "https://github.com/pallets/flask.git",
            "https://github.com/pallets/flask",
            "pallets",
            "flask",
        ),
        (
            "https://github.com/pallets/flask/",
            "https://github.com/pallets/flask",
            "pallets",
            "flask",
        ),
        (
            "https://GITHUB.COM/pallets/flask",
            "https://github.com/pallets/flask",
            "pallets",
            "flask",
        ),
        (
            "https://github.com/org-name/repo.with_dots-and_dashes.git/",
            "https://github.com/org-name/repo.with_dots-and_dashes",
            "org-name",
            "repo.with_dots-and_dashes",
        ),
        (
            "  https://github.com/psf/requests  ",
            "https://github.com/psf/requests",
            "psf",
            "requests",
        ),
    ],
)
def test_us_86_t_1_criterion_1_valid_github_urls(
    raw_url, expected_norm, expected_owner, expected_repo
):
    """Criterion 1: Valid GitHub URLs return normalized URL, owner, and repository name."""
    norm_url, owner, repo = validate_and_normalize_github_url(raw_url)
    assert norm_url == expected_norm
    assert owner == expected_owner
    assert repo == expected_repo


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/pallets/flask",
        "https://github.com/torvalds/linux",
        "https://github.com/facebook/react",
    ],
)
def test_us_86_t_1_criterion_2_normalization_is_idempotent(url):
    """Criterion 2: Normalizing an already-normalized URL returns the exact same string."""
    norm_once, _, _ = validate_and_normalize_github_url(url)
    norm_twice, _, _ = validate_and_normalize_github_url(norm_once)
    assert norm_once == norm_twice == url


# ---------------------------------------------------------------------------
# Acceptance Criterion 3: Reject Non-HTTPS Schemes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_scheme_url",
    [
        "http://github.com/pallets/flask",
        "git://github.com/pallets/flask",
        "ssh://git@github.com/pallets/flask",
        "ftp://github.com/pallets/flask",
        "github.com/pallets/flask",
        "://github.com/pallets/flask",
    ],
)
def test_us_86_t_1_criterion_3_rejects_non_https_schemes(invalid_scheme_url):
    """Criterion 3: Non-https schemes raise InvalidRepoUrl."""
    with pytest.raises(InvalidRepoUrl, match="scheme"):
        validate_and_normalize_github_url(invalid_scheme_url)


# ---------------------------------------------------------------------------
# Acceptance Criterion 4: Reject Lookalike and Unauthorized Hosts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lookalike_url",
    [
        "https://github.com.evil.com/pallets/flask",
        "https://evil-github.com/pallets/flask",
        "https://notgithub.com/pallets/flask",
        "https://gitlab.com/pallets/flask",
        "https://bitbucket.org/pallets/flask",
        "https://192.168.1.1/pallets/flask",
        "https://api.github.com/pallets/flask",
    ],
)
def test_us_86_t_1_criterion_4_rejects_lookalike_hosts(lookalike_url):
    """Criterion 4: Lookalike and unauthorized hosts raise InvalidRepoUrl."""
    with pytest.raises(InvalidRepoUrl, match="host"):
        validate_and_normalize_github_url(lookalike_url)


# ---------------------------------------------------------------------------
# Acceptance Criterion 5: Reject Credentials, Ports, Query Strings, and Sub-paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "malformed_url,expected_match",
    [
        ("https://user:password@github.com/pallets/flask", "credentials"),
        ("https://user@github.com/pallets/flask", "credentials"),
        ("https://github.com:443/pallets/flask", "port"),
        ("https://github.com:8080/pallets/flask", "port"),
        ("https://github.com/pallets/flask?ref=main", "Query parameters"),
        ("https://github.com/pallets/flask#readme", "fragments"),
        ("https://github.com/pallets/flask/tree/main", "branch"),
        ("https://github.com/pallets/flask/blob/main/README.md", "branch"),
        ("https://github.com/pallets/flask/releases", "path"),
        ("https://github.com/pallets", "path"),
        ("https://github.com/", "path"),
        ("https://github.com/pallets/../evil/repo", "traversal"),
        ("https://github.com/pallets//flask", "empty"),
        (
            "https://github.com/a-very-very-very-very-very-very-long-username-that-exceeds-thirty-nine-chars/flask",
            "owner",
        ),
        ("https://github.com/pallets/invalid!repo@name", "name"),
    ],
)
def test_us_86_t_1_criterion_5_rejects_malformed_urls(malformed_url, expected_match):
    """Criterion 5: URLs with credentials, ports, queries, or invalid paths raise InvalidRepoUrl."""
    with pytest.raises(InvalidRepoUrl, match=expected_match):
        validate_and_normalize_github_url(malformed_url)


# ---------------------------------------------------------------------------
# Acceptance Criterion 6: FastAPI Maps InvalidRepoUrl to HTTP 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rejected_url",
    [
        "https://github.com.evil.com/pallets/flask",
        "http://github.com/pallets/flask",
        "https://github.com/pallets/flask?ref=main",
        "https://github.com:443/pallets/flask",
        "https://user:pass@github.com/pallets/flask",
    ],
)
def test_us_86_t_1_criterion_6_api_maps_to_http_422(rejected_url):
    """Criterion 6: Invalid URLs sent to /api/scan return HTTP 422 with JSON detail."""
    response = client.post("/api/scan", data={"url": rejected_url})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert len(data["detail"]) > 0


# ---------------------------------------------------------------------------
# Acceptance Criterion 7: Verify Comprehensive Parametrized Coverage
# ---------------------------------------------------------------------------


def test_us_86_t_1_criterion_7_empty_inputs_rejected():
    """Criterion 7: Empty or whitespace-only inputs are rejected."""
    for empty_val in ["", "   ", "\t\n"]:
        with pytest.raises(InvalidRepoUrl, match="empty"):
            validate_and_normalize_github_url(empty_val)
