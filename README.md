# CodeForge

CodeForge is a code execution platform under development.

## Current functionality

A FastAPI application that validates code submissions, saves them in
PostgreSQL, and retrieves them by UUID. Records survive API and database
restarts. Code execution is not implemented yet.

## Local setup on Windows

Prerequisites: Python, Docker Desktop running with Linux containers,
and Docker Compose. Run all commands from the project folder.

Create a local configuration file by copying .env.example to .env.
Replace the password placeholder in .env with your own password.

Create a Python virtual environment:

```powershell
py -m venv .venv
```

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start PostgreSQL:

```powershell
docker compose up -d db
```

Check readiness; repeat after a few seconds if it is still starting:

```powershell
docker compose exec db pg_isready -U codeforge -d codeforge
```

For a new database only, create the table:

```powershell
Get-Content -Raw schema.sql | docker compose exec -T db psql -U codeforge -d codeforge -v ON_ERROR_STOP=1
```

Skip table creation if the submissions table already exists.

Start the development server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs to explore the API.

Press Ctrl+C in the server terminal to stop it.