from runner import run_code


def judge_code(code, test_cases, *, runner=run_code):
    if not test_cases:
        raise ValueError("A problem must have at least one test case.")

    passed = 0
    total = len(test_cases)

    for test_input, expected_output in test_cases:
        result = runner(code, test_input)

        if result["status"] != "completed":
            return {
                "verdict": result["status"],
                "passed": passed,
                "total": total,
            }

        actual = result["output"].strip()
        expected = expected_output.strip()

        if actual != expected:
            return {
                "verdict": "wrong_answer",
                "passed": passed,
                "total": total,
            }

        passed += 1

    return {
        "verdict": "accepted",
        "passed": passed,
        "total": total,
    }