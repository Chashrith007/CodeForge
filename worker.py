from uuid import UUID
from jobs import process_submission
from redis import Redis

client = Redis(
    host="127.0.0.1",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=None,
)

print("Worker ready. Press Ctrl+C to stop.")

try:
    while True:
        queue_name, job = client.blpop(
            "codeforge:submissions",
            timeout=0,
        )

        process_submission(UUID(job))

except KeyboardInterrupt:
    print("Worker stopped.")