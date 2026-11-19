import json
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OSV = "https://api.osv.dev/v1"

# Higher number = worse. 0 = has vulns but no severity data, -1 = no vulns.
RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Unknown": 0, "None": -1}


def _request(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _roundup(x):
    i = round(x * 100000)
    return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0


def _cvss3_score(vector):
    m = dict(p.split(":") for p in vector.split("/")[1:])
    changed = m["S"] == "C"
    cia = {"H": 0.56, "L": 0.22, "N": 0}
    pr = {"N": 0.85, "L": 0.68 if changed else 0.62, "H": 0.5 if changed else 0.27}[m["PR"]]
    iss = 1 - (1 - cia[m["C"]]) * (1 - cia[m["I"]]) * (1 - cia[m["A"]])
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if changed else 6.42 * iss
    exploit = (
        8.22
        * {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}[m["AV"]]
        * {"L": 0.77, "H": 0.44}[m["AC"]]
        * pr
        * {"N": 0.85, "R": 0.62}[m["UI"]]
    )
    if impact <= 0:
        return 0.0
    total = 1.08 * (impact + exploit) if changed else impact + exploit
    return _roundup(min(total, 10))


def _severity(vuln):
    """Turn one OSV record into Critical/High/Medium/Low/Unknown."""
    label = (vuln.get("database_specific") or {}).get("severity")
    if isinstance(label, str):
        label = label.upper()
        label = "MEDIUM" if label == "MODERATE" else label
        if label in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            return label.capitalize()
    for s in vuln.get("severity", []):
        if s.get("type") == "CVSS_V3":
            try:
                score = _cvss3_score(s["score"])
            except (KeyError, ValueError):
                continue
            if score >= 9:
                return "Critical"
            if score >= 7:
                return "High"
            if score >= 4:
                return "Medium"
            return "Low"
    return "Unknown"


def _worst(severities):
    return max(severities, key=RANK.get) if severities else "None"


def build_rows(sbom):
    """Return (rows, ok). One row per Syft component with vuln count + worst severity.
    ok is False if OSV could not be reached; rows then show vuln_count None."""
    components = sbom.get("components", [])
    rows = [
        {
            "name": c.get("name"),
            "version": c.get("version"),
            "type": c.get("type"),
            "purl": c.get("purl"),
            "vuln_count": None,
            "severity": "Not checked",
            "rank": -2,
        }
        for c in components
    ]

    # Only components with a purl can be looked up (files usually have none).
    checkable = [i for i, c in enumerate(components) if c.get("purl")]
    if not checkable:
        return rows, True

    try:
        ids_per_row = {}
        for start in range(0, len(checkable), 500):
            chunk = checkable[start:start + 500]
            queries = [{"package": {"purl": components[i]["purl"]}} for i in chunk]
            results = _request(f"{OSV}/querybatch", {"queries": queries})["results"]
            for i, res in zip(chunk, results):
                ids_per_row[i] = [v["id"] for v in res.get("vulns", [])]

        all_ids = sorted({v for ids in ids_per_row.values() for v in ids})
        with ThreadPoolExecutor(max_workers=8) as pool:
            details = list(pool.map(lambda v: _request(f"{OSV}/vulns/{v}"), all_ids))
        sev_by_id = {v: _severity(d) for v, d in zip(all_ids, details)}
    except Exception as e:
        print("OSV lookup failed:", e)
        return rows, False

    for i in checkable:
        ids = ids_per_row.get(i, [])
        sev = _worst([sev_by_id[v] for v in ids])
        rows[i].update(vuln_count=len(ids), severity=sev, rank=RANK[sev])
    return rows, True