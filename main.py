from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

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
    return {
        "status": "received",
        "characters": len(submission.code),
    }
