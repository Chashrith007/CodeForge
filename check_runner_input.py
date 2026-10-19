from runner import run_code

solution = """
a, b = map(int, input().split())
print(a + b)
"""

cases = [
    ("3 5\n", "8"),
    ("-2 7\n", "5"),
    ("0 0\n", "0"),
]

for test_input, expected in cases:
    result = run_code(solution, test_input)

    assert result["status"] == "completed", result
    assert result["exit_code"] == 0, result

    actual = result["output"].strip()
    assert actual == expected, result

    print(f"PASS: {test_input.strip()} -> {actual}")