"""Shared cloud admission and delivery settings. No credentials belong here."""
import os

from fastapi import HTTPException

TOPIC = "codeforge-submissions"
DAILY_LIMIT = 10
MINUTE_LIMIT = 2
STALE_SECONDS = 360  # Longer than the configured 300-second function lifetime.


def is_cloud():
    return bool(os.getenv("VERCEL"))


def check_admission(connection):
    # A transaction-scoped lock works with Neon's pooled connection endpoint.
    # It covers both the count and the INSERT in the caller's transaction.
    connection.execute("SELECT pg_advisory_xact_lock(187640321)")
    counts = connection.execute(
        """
        SELECT count(*) AS daily,
               count(*) FILTER (
                   WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '1 minute'
               ) AS recent
        FROM submissions
        WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
        """
    ).fetchone()
    if counts["daily"] >= DAILY_LIMIT:
        raise HTTPException(429, "The demo has reached its 10 submissions per 24 hours limit.")
    if counts["recent"] >= MINUTE_LIMIT:
        raise HTTPException(429, "Please wait a minute before submitting more code.")
