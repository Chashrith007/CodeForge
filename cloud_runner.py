"""Execute one program in a fresh Vercel Sandbox; never execute it in the API.

The cloud VM runs a trusted supervisor as root and the submitted program as
an unprivileged child. The program gets a 128 MiB address-space limit (not
Docker's physical-memory limit). The VM itself has a separate 2 GiB allocation.
This module does not load local credentials or change the local Docker runner.
"""

import base64
import json

from vercel.sandbox import NetworkPolicy, SandboxResources
from vercel.sandbox import sync as sandbox


OUTPUT_LIMIT = 16_384
INPUT_LIMIT = 16_384

# This fixed supervisor is sent to the cloud VM. Submitted source is a JSON
# argument, never interpolated into the supervisor or into a shell command.
_SUPERVISOR = r'''
import base64
import ctypes
import json
import os
import resource
import selectors
import signal
import subprocess
import sys
import tempfile
import time

LIMIT = 16_384
SECONDS = 5
MEMORY = 128 * 1024 * 1024

if os.geteuid() != 0:
    raise RuntimeError("The trusted supervisor must run as root.")

payload = json.loads(sys.argv[1])

def restrict_child():
    # Remove privileges before executing user source. no_new_privs also
    # prevents gaining privileges through setuid executables such as sudo.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Could not set no_new_privs")
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)

def kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

output = bytearray()
status = None

with tempfile.TemporaryDirectory(prefix="codeforge-") as workdir:
    os.chown(workdir, 65534, 65534)
    with tempfile.TemporaryFile() as input_file:
        input_file.write(payload["stdin"].encode("utf-8"))
        input_file.seek(0)
        started = time.monotonic()
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", "-u", "-c", payload["code"]],
            stdin=input_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=workdir,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": workdir},
            shell=False,
            start_new_session=True,
            preexec_fn=restrict_child,
        )
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining_time = SECONDS - (time.monotonic() - started)
                    if remaining_time <= 0:
                        status = "timed_out"
                        break
                    ready = selector.select(min(remaining_time, 0.05))
                    if not ready:
                        continue
                    chunk = os.read(process.stdout.fileno(), 4096)
                    if not chunk:
                        selector.unregister(process.stdout)
                        continue
                    remaining_bytes = LIMIT - len(output)
                    output.extend(chunk[:remaining_bytes])
                    if len(chunk) > remaining_bytes:
                        status = "output_limit"
                        break

            if status is None:
                try:
                    process.wait(timeout=max(0, SECONDS - (time.monotonic() - started)))
                except subprocess.TimeoutExpired:
                    status = "timed_out"
        finally:
            kill_group(process)
            process.wait(timeout=2)
            process.stdout.close()

        returncode = process.returncode
        if status == "timed_out":
            # Our convention, assigned by the supervisor's wall-clock deadline.
            returncode = 124
        elif status is None:
            if returncode == 0:
                status = "completed"
            elif returncode == -signal.SIGXCPU:
                status = "timed_out"
                returncode = 124
            elif returncode == -signal.SIGKILL:
                status = "killed"
            else:
                status = "runtime_error"
        if returncode < 0:
            returncode = 128 - returncode

# Base64 keeps the captured byte limit exact while crossing the JSON boundary.
print(json.dumps({
    "status": status,
    "output_base64": base64.b64encode(output).decode("ascii"),
    "exit_code": returncode,
    "python_version": sys.version.split()[0],
}), flush=True)
'''


def run_code_cloud(code, stdin_text=""):
    """Return the same status/output/exit_code fields as the Docker runner.

    SDK, setup and cleanup failures raise exceptions for the worker to handle.
    A fresh VM per call keeps separate challenge test cases isolated.
    """
    if not isinstance(code, str) or not 1 <= len(code) <= 10000:
        raise ValueError("Code must contain 1 to 10000 characters.")
    if not isinstance(stdin_text, str):
        raise ValueError("Standard input must be text.")
    if len(stdin_text.encode("utf-8")) > INPUT_LIMIT:
        raise ValueError("Standard input exceeds the 16 KiB limit.")

    payload = json.dumps({"code": code, "stdin": stdin_text}, ensure_ascii=False)

    with sandbox.create_sandbox(
        execution_time_limit=30,
        persistent=False,
        resources=SandboxResources(vcpus=1, memory=2048),
        network_policy=NetworkPolicy.deny_all(),
        region="iad1",
    ) as box:
        completed = box.run_process(
            "python3",
            ["-I", "-B", "-u", "-c", _SUPERVISOR, payload],
            sudo=True,
            capture_output=True,
            check=False,
            kill_after=15,
        )
        if completed.returncode != 0:
            # Do not turn infrastructure errors into a successful code result.
            raise RuntimeError(
                f"Cloud supervisor failed (exit {completed.returncode})."
            )
        result = json.loads(completed.stdout or "")
        raw_output = base64.b64decode(result["output_base64"], validate=True)
        if len(raw_output) > OUTPUT_LIMIT:
            raise RuntimeError("Cloud result exceeded the output limit.")
        if result["status"] not in {
            "completed", "runtime_error", "timed_out", "output_limit", "killed"
        }:
            raise RuntimeError("Cloud runner returned an unknown status.")
        if type(result["exit_code"]) is not int:
            raise RuntimeError("Cloud runner returned an invalid exit code.")

    # The context manager attempts stop + destroy before a result is returned.
    return {
        "status": result["status"],
        "output": raw_output.decode("utf-8", errors="replace"),
        "exit_code": result["exit_code"],
        "python_version": result["python_version"],
    }
