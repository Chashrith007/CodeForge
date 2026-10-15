import subprocess
from uuid import uuid4

container_name = f"codeforge-demo-{uuid4().hex}"

command = [
    "docker", "run",
    "--name", container_name,
    "--pull", "never",
    "--network", "none",
    "--memory", "128m",
    "--memory-swap", "128m",
    "--cpus", "0.5",
    "--pids-limit", "32",
    "--read-only",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--user", "65534:65534",
    "python:3.13-slim",
    "timeout", "--kill-after=1s", "5s",
    "python", "-c", "import time; time.sleep(30)",
]

try:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60,
        shell=False,
    )
    print("Output:", result.stdout.strip())
    print("Errors:", result.stderr.strip())
    print("Exit code:", result.returncode)

except subprocess.TimeoutExpired:
    print("Docker command exceeded the 60-second diagnostic deadline.")

finally:
    try:
        cleanup = subprocess.run(
            ["docker", "rm", "--force", container_name],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        if cleanup.returncode == 0:
            print("Container removed.")
        else:
            print("Cleanup could not be confirmed:", cleanup.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"Check container {container_name}: cleanup failed ({type(error).__name__}).")