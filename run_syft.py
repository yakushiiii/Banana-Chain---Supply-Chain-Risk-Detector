import json, subprocess

def generate_sbom(path):
    result = subprocess.run(
        ["syft", f"dir:{path}", "-o", "cyclonedx-json"],
        capture_output=True, text=True, check=True,
    ) #stores everything about run in result
    return json.loads(result.stdout) #printed output is the JSON (json.loads doesn't accept mimetype)