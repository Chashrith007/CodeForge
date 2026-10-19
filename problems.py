PROBLEMS = {
    "add-two-integers": {
        "title": "Add Two Integers",
        "description": (
            "Read two space-separated integers and print their sum."
        ),
        "input_format": "One line containing two integers a and b.",
        "output_format": "Print one integer: a + b.",
        "example_input": "3 5\n",
        "example_output": "8\n",
        "starter_code": (
            "a, b = map(int, input().split())\n"
            "# Print the sum below.\n"
        ),
        "test_cases": [
            ("3 5\n", "8\n"),
            ("-2 7\n", "5\n"),
            ("0 0\n", "0\n"),
            ("1000000 2000000\n", "3000000\n"),
            ("-10 -20\n", "-30\n"),
        ],
    }
}


def get_public_problem(problem_id):
    problem = PROBLEMS[problem_id]

    return {
        "id": problem_id,
        "title": problem["title"],
        "description": problem["description"],
        "input_format": problem["input_format"],
        "output_format": problem["output_format"],
        "example_input": problem["example_input"],
        "example_output": problem["example_output"],
        "starter_code": problem["starter_code"],
    }