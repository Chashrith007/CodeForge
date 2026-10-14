import argparse
from uuid import UUID

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from database import get_connection

parser = argparse.ArgumentParser(
    description="Recover a submission after stopping all workers."
)
parser.add_argument("submission_id", type=UUID)
parser.add_argument("--workers-stopped", action="store_true", required=True)
args = parser.parse_args()

client = Redis(
    host="127.0.0.1",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry=Retry(NoBackoff(), 0),
)

try:
    client.ping()

    with get_connection() as connection:
        record = connection.execute(
            """
            UPDATE submissions
            SET status = 'received'
            WHERE id = %s AND status IN ('received', 'running')
            RETURNING id
            """,
            (args.submission_id,),
        ).fetchone()

    if record is None:
        raise SystemExit(
            "Not recovered: submission is missing or has another status."
        )

    client.rpush("codeforge:submissions", str(args.submission_id))
    print(f"Recovery queued: {args.submission_id}")

finally:
    client.close()
    