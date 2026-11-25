import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from app.schemas import BuildResult

BUILD_COMMANDS = {
    "cmake": ["cmake -S . -B _build", "cmake --build _build"],
    "make": ["make"]
}

IMAGE_NAME = "banana-builder"

def choose_commands(detection):
    if not detection.has_c_cpp_sources:
        return (None, "skipped")

    if detection.primary not in BUILD_COMMANDS:
        return (None, "unsupported")
    
    return (BUILD_COMMANDS[detection.primary], None)

def docker_args(name, folder, commands):
    return ["docker", "run", "--rm", 
            "--network", "none", 
            "--memory", "2g", 
            "--cpus", "2", 
            "--pids-limit", "512", 
            "--cap-drop", "ALL", 
            "--security-opt", "no-new-privileges", 
            "--user", "builder",
            "--name", name, 
            "-v", f"{folder}:/src", 
            IMAGE_NAME, 
            "sh", "-c", " && ".join(commands)]

def run_build(workspace_path, detection, timeout=600):
    commands, status = choose_commands(detection)
    if status:
        return BuildResult(status=status)

    copy_dir = Path(tempfile.mkdtemp(prefix="banana-build-")) / "src"
    shutil.copytree(workspace_path, copy_dir, symlinks=True)
    log_path = copy_dir.parent / "build.log"

    name = f"banana-build-{uuid.uuid4().hex[:12]}"
    args = docker_args(name, copy_dir, commands)

    start = time.monotonic()

    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        subprocess.run(["docker", "kill", name], capture_output=True,check=False)
        output = (e.output or b"").decode(errors="replace")
        log_path.write_text(output)
        shutil.rmtree(copy_dir, ignore_errors=True)
        return BuildResult(status="timeout", duration_seconds=(time.monotonic() - start), commands=commands, log_path=str(log_path), log_tail=output[-2000:])
    except FileNotFoundError:
        shutil.rmtree(copy_dir, ignore_errors=True)
        return BuildResult(status="failed", commands=commands, log_tail="Docker is not installed or not on PATH")

    duration_seconds = time.monotonic() - start

    output = result.stdout
    log_path.write_text(output)
    status = "success" if result.returncode == 0 else "failed"
    shutil.rmtree(copy_dir, ignore_errors=True)
    
    return BuildResult(
        status=status, 
        exit_code=result.returncode, 
        duration_seconds=duration_seconds,
        commands=commands,
        log_path=str(log_path),
        log_tail=output[-2000:]
        )
