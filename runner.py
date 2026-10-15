import subprocess
import threading
import time
from uuid import uuid4

OUTPUT_LIMIT = 16_384  # Keep at most 16 KiB of combined stdout and stderr.
DOCKER_DEADLINE = 60  # Includes Docker startup, unlike the inner five-second limit.


def run_code(code):
    name = f"codeforge-run-{uuid4().hex}"
    output = bytearray()
    overflow = threading.Event()
    read_failed = threading.Event()
    process = None
    reader = None
    reason = None

    command = [
        "docker", "run", "--name", name, "--pull", "never",
        "--network", "none",
        "--memory", "128m", "--memory-swap", "128m",
        "--cpus", "0.5", "--pids-limit", "32",
        "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        "--log-driver", "none",
        "python:3.13-slim",
        "timeout", "--kill-after=1s", "5s",
        "python", "-I", "-B", "-u", "-c", code,
    ]

    def collect_output():
        try:
            while True:
                chunk = process.stdout.read1(4096)
                if not chunk:
                    break
                remaining = OUTPUT_LIMIT - len(output)
                output.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    overflow.set()
                    break
        except OSError:
            read_failed.set()

    try:
        started = time.monotonic()
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
        )
        reader = threading.Thread(target=collect_output, daemon=True)
        reader.start()

        while process.poll() is None:
            if overflow.is_set():
                reason = "output_limit"
                break
            if read_failed.is_set():
                reason = "runner_error"
                break
            if time.monotonic() - started > DOCKER_DEADLINE:
                reason = "runner_timeout"
                break
            time.sleep(0.05)

    finally:
        # Stopping the Docker CLI alone does not guarantee the container stopped.
        try:
            if process is not None and process.poll() is None:
                process.kill()
            cleanup = subprocess.run(
                ["docker", "rm", "--force", name],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            if cleanup.returncode != 0:
                raise RuntimeError(f"Cleanup not confirmed for {name}: {cleanup.stderr.strip()}")
        finally:
            if process is not None:
                process.wait(timeout=5)
            if reader is not None:
                reader.join(timeout=5)
                if reader.is_alive():
                    raise RuntimeError(f"Output reader did not stop for {name}")
            if process is not None and process.stdout is not None:
                process.stdout.close()

    if overflow.is_set():
        reason = "output_limit"
    elif read_failed.is_set():
        reason = "runner_error"

    if reason is None:
        if process.returncode == 0:
            reason = "completed"
        elif process.returncode == 124:
            reason = "timed_out"
        elif process.returncode == 137:
            reason = "killed"
        else:
            reason = "runtime_error"

    return {
        "status": reason,
        "output": output.decode("utf-8", errors="replace"),
        "exit_code": process.returncode,
    }
