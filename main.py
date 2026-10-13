from redis import Redis
from redis.exceptions import RedisError
from database import get_connection
from uuid import UUID, uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

queue_client = Redis(
    host="127.0.0.1",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)

class SubmissionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=10000)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/about")
def about():
    return {"name": "CodeForge", "purpose": "Run code"}

@app.get("/greet")
def greet(name: str = "Guest"):
    return {"message": f"Hello, {name}!"}

@app.get("/square")
def square(number: int):
    return {"number": number, "square": number * number}


@app.get("/submissions/{submission_id}")
def get_submission(submission_id: UUID):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, status, char_length(code) AS characters
            FROM submissions
            WHERE id = %s
            """,
            (submission_id,),
        )
        record = cursor.fetchone()

    if record is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    return record

@app.post("/submissions")
def submit_code(submission: SubmissionRequest):
    submission_id = uuid4()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO submissions (id, code)
            VALUES (%s, %s)
            RETURNING id, status, char_length(code) AS characters
            """,
            (submission_id, submission.code),
        )
        record = cursor.fetchone()

    try:
        queue_client.rpush("codeforge:submissions", str(submission_id))
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Submission saved, but queue delivery could not be confirmed.",
                "id": str(submission_id),
            },
        )

    return record