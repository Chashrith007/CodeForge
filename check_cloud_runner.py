"""Explicit live test: creates short-lived Vercel sandboxes using free quota."""

from pathlib import Path

from dotenv import load_dotenv

from cloud_runner import OUTPUT_LIMIT, run_code_cloud


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env.local")

    cases = [
        ("success", "print(1 + 1)", "", "completed", "2\n", 0),
        (
            "standard input",
            'name = input(); print("Hello,", name)',
            "Sam\n",
            "completed",
            "Hello, Sam\n",
            0,
        ),
        ("runtime error", "raise ValueError('demo error')", "", "runtime_error", None, 1),
        ("timeout", "while True: pass", "", "timed_out", "", 124),
        ("output limit", "print('x' * 20000)", "", "output_limit", "x" * OUTPUT_LIMIT, None),
        # Choosing exit code 124 does not mean our supervisor timed it out.
        ("explicit exit", "import sys; sys.exit(124)", "", "runtime_error", "", 124),
        (
            "unprivileged user",
            "import os; print(os.getuid(), os.getgid())",
            "",
            "completed",
            "65534 65534\n",
            0,
        ),
    ]

    for name, code, stdin, status, output, exit_code in cases:
        print(f"Testing: {name}", flush=True)
        result = run_code_cloud(code, stdin)
        assert result["status"] == status, (
            f"{name}: expected {status}, got {result['status']}"
        )
        if output is not None:
            assert result["output"] == output, f"{name}: unexpected output"
        else:
            assert "ValueError: demo error" in result["output"], "Missing error traceback"
        if exit_code is not None:
            assert result["exit_code"] == exit_code, f"{name}: unexpected exit code"
        print(
            f"PASS: {name} | status={result['status']} | "
            f"exit_code={result['exit_code']} | Python {result['python_version']}",
            flush=True,
        )

    print("All 7 cloud-runner checks passed. Each sandbox cleanup completed.")


if __name__ == "__main__":
    main()
