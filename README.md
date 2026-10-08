# CodeForge

CodeForge is a code execution platform under development.

## Current functionality

A local FastAPI application with health, about, greeting, and square endpoints.
Code execution is not implemented yet.

## Local setup on Windows

Create a Python virtual environment:

```powershell
py -m venv .venv
```

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the development server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs to explore the API.

Press Ctrl+C in the server terminal to stop it.