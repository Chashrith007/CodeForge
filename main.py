from uuid import uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
submissions = {}

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


@app.post("/submissions")
def submit_code(submission: SubmissionRequest):
    submission_id = str(uuid4())

    record = {
        "id": submission_id,
        "status": "received",
        "characters": len(submission.code),
    }

    submissions[submission_id] = record
    return record

@app.get("/submissions/{submission_id}")
def get_submission(submission_id: str):
    if submission_id not in submissions:
        raise HTTPException(status_code=404, detail="Submission not found")

    return submissions[submission_id]    
