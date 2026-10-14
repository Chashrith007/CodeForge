import time
from uuid import UUID
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry
from database import get_connection

client = Redis(
    host="127.0.0.1",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry=Retry(NoBackoff(), 0),
)


def process_submission(submission_id):
    with get_connection() as connection:
        record = connection.execute(
            """
            UPDATE submissions
            SET status = 'running'
            WHERE id = %s AND status = 'received'
            RETURNING id
            """,
            (submission_id,),
        ).fetchone()

    if record is None:
        print(f"Skipped: {submission_id}", flush=True)
        return

    print(f"Running: {submission_id}", flush=True)
    time.sleep(3)

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE submissions
            SET status = 'completed'
            WHERE id = %s AND status = 'running'
            """,
            (submission_id,),
        )

    print(f"Completed: {submission_id}", flush=True)


def run_worker():
    print("Worker ready. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            try:
                item = client.blpop("codeforge:submissions", timeout=2)
            except RedisError:
                print("Redis unavailable. Retrying in 2 seconds.", flush=True)
                time.sleep(2)
                continue

            if item is None:
                continue

            queue_name, job = item

            try:
                submission_id = UUID(job)
            except ValueError:
                print(f"Skipped invalid ID: {job}", flush=True)
                continue

            process_submission(submission_id)

    except KeyboardInterrupt:
        print("Worker stopped.", flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    run_worker()