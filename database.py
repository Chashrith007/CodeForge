import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


if not os.getenv("VERCEL"):
    load_dotenv(Path(__file__).resolve().parent / ".env")


def get_connection():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg.connect(
            database_url,
            row_factory=dict_row,
            connect_timeout=10,
        )

    if os.getenv("VERCEL"):
        raise RuntimeError("DATABASE_URL is not configured.")

    return psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        row_factory=dict_row,
        connect_timeout=5,
    )
