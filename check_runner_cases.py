from runner import run_code

cases = [
    ("success", "print(1 + 1)", "completed", "2"),
    (
        "python error",
        "raise ValueError('demo error')",
        "runtime_error",
        "ValueError: demo error",
    ),
    ("timeout", "import time; time.sleep(30)", "timed_out", ""),
]

for name, code, expected_status, expected_text in cases:
    print(f"Testing: {name}", flush=True)

    result = run_code(code)

    assert result["status"] == expected_status, result
    assert expected_text in result["output"], result

    print(
        f"PASS: {name} | "
        f"status={result['status']} | "
        f"exit_code={result['exit_code']}",
        flush=True,
    )