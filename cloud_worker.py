"""Private queue subscriber. Vercel discovers it through pyproject.toml."""
import asyncio
import logging
from uuid import UUID

from vercel.queue import Message, RetryAfter, subscribe

from cloud_runner import run_code_cloud
from cloud_settings import STALE_SECONDS, TOPIC
from database import get_connection
from judge import judge_code
from problems import PROBLEMS

logger = logging.getLogger(__name__)


def failure_result(problem_id):
    return {
        "status": "runner_error", "output": None, "exit_code": None,
        "verdict": "runner_error" if problem_id is not None else None,
        "tests_passed": None, "tests_total": None,
    }


def execute(record):
    if record["problem_id"] is None:
        return {
            **run_code_cloud(record["code"], record["stdin"]),
            "verdict": None, "tests_passed": None, "tests_total": None,
        }
    problem = PROBLEMS[record["problem_id"]]
    judged = judge_code(record["code"], problem["test_cases"], runner=run_code_cloud)
    verdict = judged["verdict"]
    return {
        "status": "completed" if verdict in ("accepted", "wrong_answer") else verdict,
        "output": None, "exit_code": None, "verdict": verdict,
        "tests_passed": judged["passed"], "tests_total": judged["total"],
    }


def save_result(submission_id, result):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE submissions
            SET status = %s, output = %s, exit_code = %s, verdict = %s,
                tests_passed = %s, tests_total = %s
            WHERE id = %s AND status = 'running'
            """,
            (result["status"], result["output"], result["exit_code"],
             result["verdict"], result["tests_passed"], result["tests_total"],
             submission_id),
        )


def process_cloud_submission(submission_id):
    interrupted = False
    with get_connection() as connection:
        # Hold the row lock only during the claim, never during cloud execution.
        record = connection.execute(
            """
            SELECT id, code, problem_id, stdin, status,
                   (cloud_started_at IS NULL OR cloud_started_at <
                    CURRENT_TIMESTAMP - make_interval(secs => %s)) AS stale
            FROM submissions WHERE id = %s FOR UPDATE
            """,
            (STALE_SECONDS, submission_id),
        ).fetchone()
        if record is None:
            logger.warning("Queue referenced a missing submission: %s", submission_id)
            return
        if record["status"] == "running":
            if not record["stale"]:
                # Do not run code twice while the first delivery may still run.
                raise RetryAfter(STALE_SECONDS)
            interrupted = True
        elif record["status"] != "received":
            return  # Terminal result: duplicate delivery is harmless.
        else:
            connection.execute(
                """
                UPDATE submissions
                SET status = 'running', cloud_started_at = CURRENT_TIMESTAMP,
                    output = NULL, exit_code = NULL, verdict = NULL,
                    tests_passed = NULL, tests_total = NULL
                WHERE id = %s
                """,
                (submission_id,),
            )

    if interrupted:
        # A killed worker cannot safely promise that its result was saved.
        # Report failure instead of charging another execution to the quota.
        result = failure_result(record["problem_id"])
    else:
        try:
            result = execute(record)
        except Exception as error:
            # Log the exception type, never credential-bearing SDK error text.
            logger.error("Cloud execution failed for %s (%s)", submission_id, type(error).__name__)
            result = failure_result(record["problem_id"])

    # DB failures propagate so the queue can redeliver instead of acknowledging.
    save_result(submission_id, result)


@subscribe(
    topic=TOPIC,
    consumer_group="codeforge-runner",
    retry_after=STALE_SECONDS,
    max_concurrency=1,
    max_attempts=3,
)
async def handle_submission(message: Message[dict[str, str]]) -> None:
    try:
        submission_id = UUID(message.payload["submission_id"])
    except (KeyError, TypeError, ValueError, AttributeError):
        logger.warning("Ignored invalid submission queue payload")
        return
    await asyncio.to_thread(process_cloud_submission, submission_id)
