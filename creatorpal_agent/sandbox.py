import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


class AnalyticsSandbox:
    def __init__(
        self, backend="restricted", timeout_seconds=3, docker_image="creatorpal-analytics"
    ):
        if backend not in {"restricted", "docker"}:
            raise ValueError("Unknown analytics backend")
        self.backend, self.timeout_seconds, self.docker_image = (
            backend,
            timeout_seconds,
            docker_image,
        )

    def execute(self, program, rows):
        payload = json.dumps({"program": program, "rows": rows}, allow_nan=False)
        if len(program) > 6000 or len(payload) > 100_000:
            return {"status": "error", "error_type": "InputBudgetExceeded"}
        with tempfile.TemporaryDirectory(prefix="creatorpal-analysis-") as directory:
            if self.backend == "docker":
                import uuid

                name = "creatorpal-analysis-" + uuid.uuid4().hex[:12]
                command = [
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    name,
                    "-i",
                    "--network=none",
                    "--read-only",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges",
                    "--pids-limit=16",
                    "--memory=256m",
                    "--cpus=0.5",
                    "--user=65534:65534",
                    self.docker_image,
                ]
                environment = None  # Only the Docker client needs its host connection settings.
            else:
                if os.name != "posix":
                    return {"status": "error", "error_type": "DockerRequiredOnWindows"}
                command = [
                    sys.executable,
                    "-I",
                    "-S",
                    str(Path(__file__).with_name("sandbox_worker.py")),
                ]
                environment = {"PATH": os.defpath, "LANG": "C.UTF-8"}
            try:
                result = subprocess.run(
                    command,
                    input=payload,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    cwd=directory,
                    env=environment,
                )
                if result.returncode:
                    return {"status": "error", "error_type": "ExecutionTerminated"}
                return json.loads(result.stdout)
            except subprocess.TimeoutExpired:
                return {"status": "error", "error_type": "Timeout"}
            except (OSError, json.JSONDecodeError):
                return {"status": "error", "error_type": "BackendUnavailable"}
            finally:
                if self.backend == "docker":
                    try:
                        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=5)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
