import time
from uuid import UUID

from database import get_connection


def process_submission(submission_id: UUID):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE submissions
            SET status = 'running'
            WHERE id = %s AND status = 'received'
            RETURNING id
            """,
            (submission_id,),
        )
        record = cursor.fetchone()

    if record is None:
        print(f"Skipped: {submission_id}")
        return

    print(f"Running: {submission_id}")
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

    print(f"Completed: {submission_id}")