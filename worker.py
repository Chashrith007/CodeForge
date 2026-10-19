import time
from uuid import UUID

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from database import get_connection
from judge import judge_code
from problems import PROBLEMS
from runner import run_code


client = Redis(
    host="127.0.0.1",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry=Retry(NoBackoff(), 0),
)


def execute_submission(record):
    problem_id = record["problem_id"]

    if problem_id is None:
        result = run_code(record["code"])

        return {
            **result,
            "verdict": None,
            "tests_passed": None,
            "tests_total": None,
        }

    problem = PROBLEMS.get(problem_id)

    if problem is None:
        raise ValueError(f"Unknown problem: {problem_id}")

    judged = judge_code(record["code"], problem["test_cases"])
    verdict = judged["verdict"]

    if verdict in ("accepted", "wrong_answer"):
        status = "completed"
    else:
        status = verdict

    return {
        "status": status,
        "output": None,
        "exit_code": None,
        "verdict": verdict,
        "tests_passed": judged["passed"],
        "tests_total": judged["total"],
    }


def process_submission(submission_id):
    with get_connection() as connection:
        record = connection.execute(
            """
            UPDATE submissions
            SET status = 'running',
                output = NULL,
                exit_code = NULL,
                verdict = NULL,
                tests_passed = NULL,
                tests_total = NULL
            WHERE id = %s AND status = 'received'
            RETURNING id, code, problem_id
            """,
            (submission_id,),
        ).fetchone()

    if record is None:
        print(f"Skipped: {submission_id}", flush=True)
        return

    print(f"Running: {submission_id}", flush=True)

    try:
        result = execute_submission(record)
    except Exception as error:
        print(
            f"Execution failed for {submission_id}: {error}",
            flush=True,
        )

        result = {
            "status": "runner_error",
            "output": None,
            "exit_code": None,
            "verdict": (
                "runner_error"
                if record["problem_id"] is not None
                else None
            ),
            "tests_passed": None,
            "tests_total": None,
        }

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE submissions
            SET status = %s,
                output = %s,
                exit_code = %s,
                verdict = %s,
                tests_passed = %s,
                tests_total = %s
            WHERE id = %s AND status = 'running'
            """,
            (
                result["status"],
                result["output"],
                result["exit_code"],
                result["verdict"],
                result["tests_passed"],
                result["tests_total"],
                submission_id,
            ),
        )

    print(
        f"Finished: {submission_id} | "
        f"status={result['status']} | "
        f"verdict={result['verdict']}",
        flush=True,
    )


def run_worker():
    print("Worker ready. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            try:
                item = client.blpop(
                    "codeforge:submissions",
                    timeout=2,
                )
            except RedisError:
                print(
                    "Redis unavailable. Retrying in 2 seconds.",
                    flush=True,
                )
                time.sleep(2)
                continue

            if item is None:
                continue

            queue_name, job = item

            try:
                submission_id = UUID(job)
            except ValueError:
                print(f"Skipped invalid ID: {job}", flush=True)
                continue

            process_submission(submission_id)

    except KeyboardInterrupt:
        print("Worker stopped.", flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    run_worker()