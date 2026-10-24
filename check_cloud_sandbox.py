from pathlib import Path

from dotenv import load_dotenv
from vercel.sandbox import NetworkPolicy
from vercel.sandbox import sync as sandbox


load_dotenv(Path(__file__).resolve().parent / ".env.local")

with sandbox.create_sandbox(
    execution_time_limit=30,
    persistent=False,
    network_policy=NetworkPolicy.deny_all(),
) as box:
    result = box.run_process(
        "python3",
        ["-c", "print(1 + 1)"],
        capture_output=True,
        check=True,
        kill_after=5,
    )

    print("Output:", result.stdout.strip())
    print("Exit code:", result.returncode)

print("Sandbox cleaned up.")