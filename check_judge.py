from judge import judge_code

test_cases = [
    ("3 5\n", "8"),
    ("-2 7\n", "5"),
    ("0 0\n", "0"),
]

solutions = [
    (
        "correct solution",
        "a, b = map(int, input().split())\nprint(a + b)",
        "accepted",
        3,
    ),
    (
        "incorrect solution",
        "print(999)",
        "wrong_answer",
        0,
    ),
    (
        "crashing solution",
        "raise ValueError('demo error')",
        "runtime_error",
        0,
    ),
]

for name, code, expected_verdict, expected_passed in solutions:
    result = judge_code(code, test_cases)

    assert result["verdict"] == expected_verdict, result
    assert result["passed"] == expected_passed, result
    assert result["total"] == 3, result

    print(
        f"PASS: {name} -> {result['verdict']} "
        f"({result['passed']}/{result['total']})"
    )