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

## Background processing

Start PostgreSQL and Redis:

```powershell
docker compose up -d db redis
```

Run the API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Run the worker in another terminal:

```powershell
.\.venv\Scripts\python.exe worker.py
```

POST /submissions saves a submission and sends its ID to Redis.
The worker changes its status from received to running to completed.
Processing currently simulates work for three seconds; it does not execute code.

## Manual recovery

If queue delivery fails, the API returns 503 with the saved submission ID.

Stop ALL workers before recovery. Ensure Redis is running.
Replace YOUR_ID below with the saved ID:

```powershell
.\.venv\Scripts\python.exe recover_submission.py YOUR_ID --workers-stopped
```

Then restart the worker.

The flag acknowledges that workers are stopped; it does not check them.

## Current limitations

Queue delivery and database writes are separate operations.
A worker crash after removing an item can strand the submission.
Recovery is operator-assisted, not automatic.
Recovery after a Redis delivery failure has been tested.
Recovery after a crash during processing has not yet been tested.