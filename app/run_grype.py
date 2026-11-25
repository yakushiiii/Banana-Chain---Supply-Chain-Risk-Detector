"""Match the packages in an SBOM against known vulnerabilities using Grype.

Syft builds the SBOM, then Grype reads that SBOM and looks every package up in
its own vulnerability database. Needs the `grype` command installed, the same
way `syft` is.
"""

import json
import subprocess
import tempfile
from pathlib import Path

SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Negligible", "Unknown"]


class GrypeError(Exception):
    """Grype failed to run, or gave us output we couldn't read."""


def scan_sbom(sbom: dict, timeout: int = 300) -> list[dict]:
    """Scan an SBOM (the dict from run_syft.generate_sbom) and return findings.

    Each finding is one vulnerability on one package, worst severity first.
    """
    with tempfile.TemporaryDirectory() as tmp:
        sbom_path = Path(tmp) / "sbom.cdx.json"
        sbom_path.write_text(json.dumps(sbom), encoding="utf-8")
        try:
            # encoding is set explicitly because Windows defaults to cp1252,
            # which can't decode some characters in Grype's output
            result = subprocess.run(
                ["grype", f"sbom:{sbom_path}", "-o", "json"],
                capture_output=True, text=True, check=True, timeout=timeout,
                encoding="utf-8", errors="replace",
            )
        except FileNotFoundError as e:
            raise GrypeError("grype is not installed or not on PATH") from e
        except subprocess.TimeoutExpired as e:
            raise GrypeError(f"grype took longer than {timeout} seconds") from e
        except subprocess.CalledProcessError as e:
            raise GrypeError(f"grype failed: {e.stderr.strip()}") from e

    if not result.stdout:
        raise GrypeError("grype returned no output")

    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise GrypeError("grype did not return valid JSON") from e
    return parse_report(report)


def parse_report(report: dict) -> list[dict]:
    """Turn Grype's JSON report into a simple flat list."""
    findings = []
    for match in report.get("matches", []):
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})
        fix = vuln.get("fix") or {}
        findings.append({
            "purl": artifact.get("purl"),
            "name": artifact.get("name"),
            "version": artifact.get("version"),
            "vuln_id": vuln.get("id"),
            # a GHSA match usually lists its CVE here
            "aliases": [r["id"] for r in match.get("relatedVulnerabilities", []) if "id" in r],
            "severity": vuln.get("severity") or "Unknown",
            "cvss": _best_cvss(vuln.get("cvss")),
            "fixed_in": fix.get("versions") or [],
            "fix_state": fix.get("state"),
            "url": vuln.get("dataSource"),
        })
    findings.sort(key=lambda f: (_severity_rank(f["severity"]), f["name"] or "", f["vuln_id"] or ""))
    return findings


def _severity_rank(severity: str) -> int:
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return len(SEVERITY_ORDER)


def _best_cvss(entries: list | None) -> float | None:
    """Highest base score Grype listed, or None if it had none."""
    scores = [
        e["metrics"]["baseScore"]
        for e in entries or []
        if isinstance(e.get("metrics"), dict) and "baseScore" in e["metrics"]
    ]
    return max(scores) if scores else None


def format_findings(findings: list[dict]) -> str:
    """One JSON object per line (JSON Lines), ready to print or save."""
    return "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in findings)


def write_findings(findings: list[dict], path: str | Path) -> Path:
    """Save the same one-per-line text to a file (.jsonl)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_findings(findings), encoding="utf-8")
    return path


# Higher number = worse. Same ranks the old vulns.py used, plus Grype's "Negligible".
RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Negligible": 1, "Unknown": 0, "None": -1}


def rows_from_findings(sbom: dict, findings: list[dict]) -> list[dict]:
    """One row per SBOM component with a vuln count and its worst severity.

    Same row shape the old vulns.build_rows returned, so the results page and
    /api/scan keep working. Components with no purl or cpe can't be matched by
    Grype, so they stay "Not checked".
    """
    by_purl: dict = {}
    by_name_version: dict = {}
    for f in findings:
        by_purl.setdefault(f["purl"], []).append(f)
        by_name_version.setdefault((f["name"], f["version"]), []).append(f)

    rows = []
    for c in sbom.get("components", []):
        row = {
            "name": c.get("name"),
            "version": c.get("version"),
            "type": c.get("type"),
            "purl": c.get("purl"),
            "vuln_count": None,
            "severity": "Not checked",
            "rank": -2,
        }
        if c.get("purl") or c.get("cpe"):
            # purl first; fall back to name+version in case the purl text differs
            matches = by_purl.get(c.get("purl")) or by_name_version.get(
                (c.get("name"), c.get("version")), []
            )
            worst = max((m["severity"] for m in matches), key=lambda s: RANK.get(s, 0)) if matches else "None"
            row.update(vuln_count=len(matches), severity=worst, rank=RANK.get(worst, 0))
        rows.append(row)
    return rows