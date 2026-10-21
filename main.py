from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from database import get_connection
from problems import PROBLEMS, get_public_problem

app = FastAPI()

queue_client = Redis(
    host="127.0.0.1",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry=Retry(NoBackoff(), 0),
)


class SubmissionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=10000)
    problem_id: str | None = Field(default=None, max_length=100)
    stdin: str = Field(default="", max_length=16384)

    @field_validator("stdin")
    @classmethod
    def validate_stdin(cls, value):
        if len(value.encode("utf-8")) > 16384:
            raise ValueError("Input must not exceed 16384 UTF-8 bytes.")
        return value


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/about")
def about():
    return {"name": "CodeForge", "purpose": "Run and judge Python code"}


@app.get("/greet")
def greet(name: str = "Guest"):
    return {"message": f"Hello, {name}!"}


@app.get("/square")
def square(number: int):
    return {"number": number, "square": number * number}


@app.get("/problems")
def list_problems():
    return [
        {"id": problem_id, "title": problem["title"]}
        for problem_id, problem in PROBLEMS.items()
    ]


@app.get("/problems/{problem_id}")
def get_problem(problem_id: str):
    if problem_id not in PROBLEMS:
        raise HTTPException(
            status_code=404,
            detail="Problem not found",
        )

    return get_public_problem(problem_id)


@app.get("/submissions/{submission_id}")
def get_submission(submission_id: UUID):
    with get_connection() as connection:
        record = connection.execute(
            """
            SELECT id,
                   status,
                   char_length(code) AS characters,
                   output,
                   exit_code,
                   problem_id,
                   verdict,
                   tests_passed,
                   tests_total
            FROM submissions
            WHERE id = %s
            """,
            (submission_id,),
        ).fetchone()

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Submission not found",
        )

    return record


@app.post("/submissions")
def submit_code(submission: SubmissionRequest):
    if submission.problem_id is not None:
        if submission.problem_id not in PROBLEMS:
            raise HTTPException(
                status_code=404,
                detail="Problem not found",
            )

        if submission.stdin != "":
            raise HTTPException(
                status_code=422,
                detail="Challenge submissions use predefined test input.",
            )

    submission_id = uuid4()

    with get_connection() as connection:
        record = connection.execute(
            """
            INSERT INTO submissions (id, code, problem_id, stdin)
            VALUES (%s, %s, %s, %s)
            RETURNING id,
                      status,
                      char_length(code) AS characters,
                      problem_id
            """,
            (
                submission_id,
                submission.code,
                submission.problem_id,
                submission.stdin,
            ),
        ).fetchone()

    try:
        queue_client.rpush(
            "codeforge:submissions",
            str(submission_id),
        )
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail={
                "message": (
                    "Submission saved, but queue delivery "
                    "could not be confirmed."
                ),
                "id": str(submission_id),
            },
        )

    return record