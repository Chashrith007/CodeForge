from database import get_connection

with get_connection() as connection:
    connection.execute("""
        ALTER TABLE submissions
        ADD COLUMN IF NOT EXISTS problem_id TEXT,
        ADD COLUMN IF NOT EXISTS verdict TEXT,
        ADD COLUMN IF NOT EXISTS tests_passed INTEGER,
        ADD COLUMN IF NOT EXISTS tests_total INTEGER;
    """)

print("Judging columns are ready.")