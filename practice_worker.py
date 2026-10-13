import time
from redis import Redis

client = Redis(
    host="127.0.0.1",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=None,
)

print("Worker ready. Press Ctrl+C to stop.")

try:
    while True:
        queue_name, job = client.blpop(
            "codeforge:practice:worker",
            timeout=0,
        )

        print(f"Running: {job}")
        time.sleep(3)
        print(f"Completed: {job}")

except KeyboardInterrupt:
    print("Worker stopped.")