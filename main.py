from fastapi import FastAPI

app = FastAPI()

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
